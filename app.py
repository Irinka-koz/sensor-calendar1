import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date

import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials  # <-- this is required
# -------------------------
# Google Sheets Setup
# -------------------------

SCOPE = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
SHEET_ID = "1LcT1Oh6oRdDAhcggbXclkwQRk8MC1ICKyemnjoeULOE"

creds = Credentials.from_service_account_info(dict(st.secrets["google_service_account"]), scopes=SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# -------------------------
# Load Sheet
# -------------------------
def load_sheet():
    df = get_as_dataframe(sheet, evaluate_formulas=True, header=0)
    df = df.dropna(how='all')  # remove empty rows
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

# -------------------------
# Save Sheet
# -------------------------
def save_sheet(df):
    set_with_dataframe(sheet, df)

# -------------------------
# Heatmap
# -------------------------
def build_heatmap(df):
    if df.empty:
        st.warning("No data yet.")
        return

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp(date.today())
    all_days = pd.date_range(start=start_date, end=end_date)

    sensors = df['Sensor_ID'].dropna().unique()
    heatmap_data = pd.DataFrame(0, index=sensors, columns=all_days)

    # Define color codes
    color_active = "#00CC66"   # green
    color_battery = "#FF3333"  # red
    color_card = "#FF9900"     # orange

    for sensor in sensors:
        sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
        active = False
        start_active = None

        for _, row in sdata.iterrows():
            mode = row["mode"]
            d = row["date"]

            if mode == "start":
                start_active = d
                active = True

            elif mode == "end" and start_active is not None:
                end_active = d
                heatmap_data.loc[sensor, start_active:end_active] = 1
                active = False
                start_active = None

            elif mode == "change battery":
                heatmap_data.loc[sensor, d] = 2  # red

            elif mode == "change card":
                if heatmap_data.loc[sensor, d] == 2:
                    heatmap_data.loc[sensor, d] = 3  # both (half red/orange)
                else:
                    heatmap_data.loc[sensor, d] = 4  # orange

        # If started but never ended — mark until today
        if active and start_active is not None:
            heatmap_data.loc[sensor, start_active:end_date] = 1

    # Create figure
    fig, ax = plt.subplots(figsize=(12, len(sensors) * 0.6))

    # Draw colored rectangles
    for i, sensor in enumerate(sensors):
        for j, d in enumerate(all_days):
            val = heatmap_data.loc[sensor, d]
            if val == 1:
                color = color_active
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color))
            elif val == 2:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_battery))
            elif val == 4:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_card))
            elif val == 3:
                # Half red, half orange
                ax.add_patch(plt.Rectangle((j, i), 0.5, 1, color=color_battery))
                ax.add_patch(plt.Rectangle((j+0.5, i), 0.5, 1, color=color_card))

    # Axis settings
    ax.set_xlim(0, len(all_days))
    ax.set_ylim(0, len(sensors))
    ax.set_yticks([i + 0.5 for i in range(len(sensors))])
    ax.set_yticklabels(sensors)
    ax.set_xticks(range(0, len(all_days), max(len(all_days)//10, 1)))
    ax.set_xticklabels([d.strftime("%b %d") for d in all_days[::max(len(all_days)//10, 1)]],
                       rotation=45, ha='right')
    ax.invert_yaxis()
    ax.set_xlabel("Date")
    ax.set_ylabel("Sensor ID")
    ax.set_title("Sensor Operation and Maintenance Heatmap")

    st.pyplot(fig)


# -------------------------
# App UI
# -------------------------
st.title("Sensor Maintenance Log & Heatmap (Google Sheets)")

df = load_sheet()

sensor_info = {
    "S1": {"Location": "Field A", "Type": "PM"},
    "S2": {"Location": "Field B", "Type": "RH"},
    "S3": {"Location": "Field A", "Type": "Temp"},
}

st.header("Add a New Record")
sensor_id = st.selectbox("Select Sensor ID", list(sensor_info.keys()))
location = sensor_info[sensor_id]["Location"]
stype = sensor_info[sensor_id]["Type"]
st.write(f"**Location:** {location}")
st.write(f"**Type:** {stype}")

mode = st.selectbox("Select Mode", ["start", "end", "change battery", "change card"])
selected_date = st.date_input("Select Date", value=date.today())

if st.button("Add Record"):
    new_row = {
        "Sensor_ID": sensor_id,
        "Location": location,
        "Type": stype,
        "mode": mode,
        "date": pd.to_datetime(selected_date)
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_sheet(df)
    st.success("Record added successfully!")
    df = load_sheet()  # reload for heatmap

st.header("Sensor Activity Heatmap")
build_heatmap(df)







