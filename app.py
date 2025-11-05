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
import pandas as pd
import matplotlib.pyplot as plt
import calendar

def build_heatmap(df):
    sensors = df['sensor'].unique()
    start_date = df['start'].min().normalize()
    end_date = df['end'].max().normalize()
    all_days = pd.date_range(start_date, end_date, freq='D')

    years = sorted(set(all_days.year))
    today = pd.Timestamp.today().normalize()

    for yr in years:
        year_start = pd.Timestamp(f"{yr}-01-01")
        year_end = pd.Timestamp(f"{yr}-12-31")
        # if current year, cut to today
        if yr == today.year:
            year_end = today

        year_days = pd.date_range(year_start, year_end, freq='D')
        heatmap_data = pd.DataFrame(0, index=sensors, columns=year_days)

        for _, row in df.iterrows():
            sensor = row['sensor']
            s = row['start'].normalize()
            e = row['end'].normalize()
            if s.year < yr:
                s = year_start
            if e.year > yr:
                e = year_end
            period = pd.date_range(s, e, freq='D')
            for d in period:
                if d in heatmap_data.columns:
                    heatmap_data.loc[sensor, d] = 1

            # color overlays
            if pd.notna(row.get('change_card')):
                d = row['change_card'].normalize()
                if d in heatmap_data.columns:
                    heatmap_data.loc[sensor, d] = 2
            if pd.notna(row.get('change_batt')):
                d = row['change_batt'].normalize()
                if d in heatmap_data.columns:
                    # if both happen same day
                    if heatmap_data.loc[sensor, d] == 2:
                        heatmap_data.loc[sensor, d] = 4
                    else:
                        heatmap_data.loc[sensor, d] = 3

        # plot
        fig, ax = plt.subplots(figsize=(14, len(sensors) * 0.4))
        cmap = {
            0: 'white',      # no data
            1: 'green',      # active
            2: 'orange',     # card
            3: 'red',        # battery
            4: 'purple'      # both
        }

        for j, sensor in enumerate(heatmap_data.index):
            for i, d in enumerate(heatmap_data.columns):
                ax.add_patch(plt.Rectangle((i, j), 1, 1, color=cmap[heatmap_data.loc[sensor, d]]))

        ax.set_xlim(0, len(year_days))
        ax.set_ylim(0, len(sensors))
        ax.set_yticks(range(len(sensors)))
        ax.set_yticklabels(heatmap_data.index)
        ax.set_title(f"Sensor activity - {yr}")

        # --- vertical lines for month boundaries ---
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
        plt.show()






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


















