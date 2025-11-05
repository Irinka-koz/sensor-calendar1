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

    # Colors
    color_active = "#00CC66"   # green
    color_battery = "#FF3333"  # red
    color_card = "#FF9900"     # orange
    color_both = "#800080"     # purple

    # Fill heatmap_data
    for sensor in sensors:
        sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
        active = False
        start_active = None

        for _, row in sdata.iterrows():
            mode = row["mode"]
            d = row["date"]
            if pd.isna(d):
                continue

            if mode == "start":
                start_active = d
                active = True
            elif mode == "end" and start_active is not None:
                end_active = d
                mask = (all_days >= start_active) & (all_days <= end_active)
                heatmap_data.loc[sensor, all_days[mask]] = 1
                active = False
                start_active = None
            elif mode == "change battery":
                if d in heatmap_data.columns:
                    heatmap_data.loc[sensor, d] = 2
            elif mode == "change card":
                if d in heatmap_data.columns:
                    if heatmap_data.loc[sensor, d] == 2:
                        heatmap_data.loc[sensor, d] = 4  # purple
                    else:
                        heatmap_data.loc[sensor, d] = 3  # orange

        # If started but never ended — mark until today
        if active and start_active is not None:
            mask = (all_days >= start_active) & (all_days <= end_date)
            heatmap_data.loc[sensor, all_days[mask]] = 1

    # Multi-year heatmaps
    years = sorted(set(all_days.year))
    for yr in years:
        year_days = all_days[all_days.year == yr]
        fig, ax = plt.subplots(figsize=(12, len(sensors)*0.6))
        for i, sensor in enumerate(sensors):
            for j, d in enumerate(year_days):
                val = heatmap_data.loc[sensor, d]
                if val == 1:
                    ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_active))
                elif val == 2:
                    ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_battery))
                elif val == 3:
                    ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_card))
                elif val == 4:
                    ax.add_patch(plt.Rectangle((j, i), 1, 1, color=color_both))

        ax.set_xlim(0, len(year_days))
        ax.set_ylim(0, len(sensors))
        ax.set_yticks([i + 0.5 for i in range(len(sensors))])
        ax.set_yticklabels(sensors)
        ax.set_yticklabels(heatmap_data.index)
        ax.set_title(f"Sensor activity - {yr}")

        
        # --- vertical lines for month boundaries ---
        import calendar  # make sure this import is at the top of the file
        
        year_start = pd.Timestamp(f"{yr}-01-01")
        year_end = pd.Timestamp(f"{yr}-12-31")
        if yr == date.today().year:
            year_end = pd.Timestamp(date.today())
        
        month_ends = []
        month_names = []
        for m in range(1, 13):
            last_day = pd.Timestamp(f"{yr}-{m}-{calendar.monthrange(yr, m)[1]}")
            if last_day < year_start or last_day > year_end:
                continue

            month_ends.append((last_day - year_start).days)
            month_names.append(calendar.month_abbr[m])

        for x in month_ends:
            ax.axvline(x=x, color='gray', linestyle='--', linewidth=0.5)
        
        # --- horizontal lines between sensors ---
        for y in range(len(sensors)):
            ax.axhline(y=y, color='lightgray', linestyle='--', linewidth=0.5)

        
        # x-axis month names centered between lines
        month_positions = []
        for i in range(len(month_ends)):
            if i == 0:
                start = 0
            else:
                start = month_ends[i - 1]
            end = month_ends[i]
            month_positions.append((start + end) / 2)

        ax.set_xticks(month_positions)
        ax.set_xticklabels(month_names)
        ax.tick_params(axis='x', rotation=0)

        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
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

























