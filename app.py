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
# Multi-year heatmaps
years = sorted(set(all_days.year))
today = pd.Timestamp(date.today())

for yr in years:
    year_days = all_days[all_days.year == yr]
    fig, ax = plt.subplots(figsize=(12, len(sensors)*0.6))

    for i, sensor in enumerate(sensors):
        sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
        for j, d in enumerate(year_days):
            val = heatmap_data.loc[sensor, d]

            # Determine if this day should be green for active period
            active_rows = sdata[sdata["mode"] == "start"]
            for _, row in active_rows.iterrows():
                start_active = row["date"]
                # check for corresponding end
                end_rows = sdata[(sdata["mode"] == "end") & (sdata["date"] >= start_active)]
                if not end_rows.empty:
                    end_active = end_rows["date"].iloc[0]
                else:
                    end_active = today

                # For current year, do not go past today
                year_end = today if yr == today.year else pd.Timestamp(f"{yr}-12-31")
                end_period = min(end_active, year_end)

                if start_active <= d <= end_period and val == 1:
                    val = 1  # keep green
                # maintenance overrides green
                maint_rows = sdata[sdata["date"] == d]
                for _, mrow in maint_rows.iterrows():
                    if mrow["mode"] == "change battery":
                        val = 2
                    elif mrow["mode"] == "change card":
                        val = 3
                    elif mrow["mode"] == "change battery and change card":
                        val = 4  # purple

            # Draw the rectangle
            if val == 1:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_active))
            elif val == 2:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_battery))
            elif val == 3:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_card))
            elif val == 4:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_both))

    # Axis settings
    ax.set_xlim(0, len(year_days))
    ax.set_ylim(0, len(sensors))
    ax.set_yticks([i + 0.5 for i in range(len(sensors))])
    ax.set_yticklabels(sensors)
    ax.set_xticks(range(0, len(year_days), max(len(year_days)//10, 1)))
    ax.set_xticklabels([d.strftime("%b %d") for d in year_days[::max(len(year_days)//10, 1)]],
                       rotation=45, ha='right')
    ax.invert_yaxis()
    ax.set_xlabel("Date")
    ax.set_ylabel("Sensor ID")
    ax.set_title(f"Sensor Heatmap {yr}")
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



















