import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date
import plotly.graph_objects as go
import mplcursors

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
import mplcursors  # pip install mplcursors

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
    hover_data = pd.DataFrame("", index=sensors, columns=all_days)

    # Colors
    color_active = "#00CC66"   # green
    color_battery = "#FF3333"  # red
    color_card = "#FF9900"     # orange
    color_both = "#800080"     # purple

    # Fill heatmap_data and hover_data
    for sensor in sensors:
        sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
        active = False
        start_active = None

        for _, row in sdata.iterrows():
            mode = row["mode"]
            d = row["date"]
            note = row.get("note", "")
            if pd.isna(d):
                continue

            if mode == "start":
                start_active = d
                active = True
                val = 1
            elif mode == "end" and start_active is not None:
                end_active = d
                mask = (all_days >= start_active) & (all_days <= end_active)
                heatmap_data.loc[sensor, all_days[mask]] = 1
                hover_data.loc[sensor, all_days[mask]] = f"Event: start/end\nNote: {note}"
                active = False
                start_active = None
                continue
            elif mode == "change battery":
                val = 2
            elif mode == "change card":
                val = 4 if heatmap_data.loc[sensor, d] == 2 else 3
            else:
                val = 0

            if d in heatmap_data.columns:
                heatmap_data.loc[sensor, d] = val
                hover_data.loc[sensor, d] = f"Event: {mode}\nNote: {note}"

        if active and start_active is not None:
            mask = (all_days >= start_active) & (all_days <= end_date)
            heatmap_data.loc[sensor, all_days[mask]] = 1
            hover_data.loc[sensor, all_days[mask]] = "Event: active\nNote:"

    # Multi-year heatmaps
    import calendar
    years = sorted(set(all_days.year))
    for yr in years:
        year_days = all_days[all_days.year == yr]
        fig, ax = plt.subplots(figsize=(12, len(sensors)*0.6))

        for i, sensor in enumerate(sensors):
            for j, d in enumerate(year_days):
                val = heatmap_data.loc[sensor, d]
                color = color_active if val==1 else color_battery if val==2 else color_card if val==3 else color_both if val==4 else "white"
                rect = plt.Rectangle((j, i), 1, 1, color=color)
                ax.add_patch(rect)
                rect._hover_text = hover_data.loc[sensor, d]  # attach hover info

        # Axes limits and labels
        ax.set_xlim(0, len(year_days))
        ax.set_ylim(0, len(sensors))
        ax.set_yticks([i + 0.5 for i in range(len(sensors))])
        ax.set_yticklabels(sensors)
        ax.set_title(f"{yr}", fontsize=13)

        # Vertical lines for months
        month_ends = []
        month_names = []
        year_start = pd.Timestamp(f"{yr}-01-01")
        year_end = pd.Timestamp(f"{yr}-12-31")
        if yr == date.today().year:
            year_end = pd.Timestamp(date.today())
        for m in range(1, 13):
            last_day = pd.Timestamp(f"{yr}-{m}-{calendar.monthrange(yr, m)[1]}")
            if last_day < year_start or last_day > year_end:
                continue
            month_ends.append((last_day - year_start).days)
            month_names.append(calendar.month_abbr[m])
        for x in month_ends:
            ax.axvline(x=x, color='gray', linestyle='--', linewidth=0.5)

        # Horizontal lines between sensors
        for y in range(len(sensors)):
            ax.axhline(y=y, color='lightgray', linestyle='--', linewidth=1)

        # Month labels
        month_positions = [(0 if i==0 else month_ends[i-1] + month_ends[i])/2 for i in range(len(month_ends))]
        ax.set_xticks(month_positions)
        ax.set_xticklabels(month_names)
        ax.tick_params(axis='x', rotation=0)

        plt.tight_layout()

        # -----------------
        # Add interactive hover
        # -----------------
        cursor = mplcursors.cursor(ax.patches, hover=True)
        @cursor.connect("add")
        def on_hover(sel):
            sel.annotation.set_text(sel.artist._hover_text)
            sel.annotation.get_bbox_patch().set(fc="white", alpha=0.8)

        st.pyplot(fig)
        plt.close(fig)

# -------------------------
# App UI
# -------------------------
st.set_page_config(layout="wide")  # use full width

st.title("Sensor Maintenance Calendar")

df = load_sheet()

# Define sensors
sensor_info = {
    "S1": {"Location": "Field A", "Type": "PM"},
    "S2": {"Location": "Field B", "Type": "RH"},
    "S3": {"Location": "Field A", "Type": "Temp"},
}

# =============================
# TOP ROW: TABLE + INPUT FORM
# =============================
col_left, col_center, col_right = st.columns([1,1,2])

# --- Right column: Sensor info table ---
with col_right:
    st.subheader("Sensors Info")
    sensor_info_table = pd.DataFrame([
        {"Sensor ID": k, "Location": v["Location"], "Type": v["Type"]}
        for k, v in sensor_info.items()
    ])
    st.dataframe(sensor_info_table, use_container_width=True, height=150)

# --- Left column: input form ---
with col_left:
    st.subheader("Add a New Record")

    st.write("Select Sensor")
    sensor_id = st.selectbox(
        "Sensor ID", 
        list(sensor_info.keys()), 
        key="sensor", 
        label_visibility="collapsed"
    )
    st.write("Select Event")
    mode = st.selectbox(
        "Mode", 
        ["", "start", "end", "change battery", "change card"], 
        label_visibility="collapsed"
    )
    
    selected_date = st.date_input(
        "Select Date", 
        value=date.today(), 
        format="DD/MM/YYYY", 
        max_value=date.today()
    )
    # Note input
    note = st.text_input("Note (optional)")

    if st.button("Add Record", use_container_width=True):
        # get location and type from sensor_info
        location = sensor_info[sensor_id]["Location"]
        stype = sensor_info[sensor_id]["Type"]

        new_row = {
            "Sensor_ID": sensor_id,
            "Location": location,
            "Type": stype,
            "mode": mode,
            "date": pd.to_datetime(selected_date),
            "note": note
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_sheet(df)
        st.success("✅ Record added successfully!")
        df = load_sheet()  # reload for heatmap

# =============================
# BOTTOM: FULL-WIDTH HEATMAP
# =============================
st.markdown("---")
st.header("Sensor Maintenance Calendar")
build_heatmap_plotly(df)  # <--- use the Plotly version


