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

    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Define time range
    start_date = pd.to_datetime("2024-01-01")
    end_date = pd.to_datetime(date.today())

    # Create a complete date range
    all_dates = pd.date_range(start=start_date, end=end_date)

    # Prepare color codes
    color_map = {
        "active": "green",
        "battery": "red",
        "card": "orange",
        "both": "purple"
    }

    # Initialize result table
    sensors = df["Sensor_ID"].unique()
    pivot = pd.DataFrame(index=sensors, columns=all_dates, data=None)

    for sensor in sensors:
        s_df = df[df["Sensor_ID"] == sensor].sort_values("date")
        active_periods = []
        active = False
        start_time = None

        for _, row in s_df.iterrows():
            if row["mode"] == "start":
                start_time = row["date"]
                active = True
            elif row["mode"] == "end" and active and start_time is not None:
                active_periods.append((start_time, row["date"]))
                active = False
                start_time = None

        # If still active (no end)
        if active and start_time is not None:
            active_periods.append((start_time, end_date))

        # Mark active (green)
        for s, e in active_periods:
            mask = (pivot.columns >= s) & (pivot.columns <= e)
            pivot.loc[sensor, mask] = "active"

        # Mark change battery / card
        for _, row in s_df.iterrows():
            d = row["date"]
            if d in pivot.columns:
                current = pivot.loc[sensor, d]
                if row["mode"] == "change battery":
                    if current == "card":
                        pivot.loc[sensor, d] = "both"
                    else:
                        pivot.loc[sensor, d] = "battery"
                elif row["mode"] == "change card":
                    if current == "battery":
                        pivot.loc[sensor, d] = "both"
                    else:
                        pivot.loc[sensor, d] = "card"

    # Map to colors
    color_pivot = pivot.replace(color_map).fillna("white")

    # Convert to numerical values for heatmap display
    color_to_num = {v: i for i, v in enumerate(color_map.values())}
    num_pivot = color_pivot.replace(color_to_num)

    # Custom color palette
    palette = sns.color_palette(["white", "green", "red", "orange", "purple"])

    fig, ax = plt.subplots(figsize=(12, 4))
    sns.heatmap(num_pivot, cmap=palette, cbar=False, ax=ax, linewidths=0.5)

    ax.set_title("Sensor Activity Timeline")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sensor ID")
    ax.set_xticks(range(0, len(all_dates), max(1, len(all_dates)//10)))
    ax.set_xticklabels([d.strftime("%d-%b") for d in all_dates[::max(1, len(all_dates)//10)]], rotation=45, ha='right')

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









