import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date
import plotly.graph_objects as go
import mplcursors
import calendar
import plotly.express as px

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
import plotly.express as px # <--- ADD THIS LINE TO YOUR IMPORTS AT THE TOP

# ... (Other functions and setup remain the same) ...

# -------------------------
# Heatmap (Plotly Version)
# -------------------------
def build_heatmap(df):
    if df.empty:
        st.warning("No data yet.")
        return

    import calendar

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp(date.today())
    all_days = pd.date_range(start=start_date, end=end_date)

    sensors = df['Sensor_ID'].dropna().unique()
    heatmap_data = pd.DataFrame(0, index=sensors, columns=all_days)
    hover_data = pd.DataFrame("", index=sensors, columns=all_days)

    # Colors mapping
    color_map = {
        0: '#FFFFFF',  # Inactive
        1: '#00CC66',  # Active
        2: '#FF3333',  # Battery
        3: '#FF9900',  # Card
        4: '#800080'   # Both
    }

    # Fill heatmap_data and hover_data
    for sensor in sensors:
    sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
    active = False
    start_active = None
    day_notes = {day: "" for day in all_days}

    for _, row in sdata.iterrows():
        mode = row["mode"]
        if pd.isna(row["date"]):
            continue
        d = row["date"].normalize()
        note = row["note"] if pd.notna(row["note"]) else ""

        # Accumulate notes only if note column has data
        if note:
            day_notes[d] += f"- {mode}: {note}<br>"

        if mode == "start":
            start_active = d
            active = True
        elif mode == "end" and start_active is not None:
            mask = (all_days >= start_active) & (all_days <= d)
            for day in all_days[mask]:
                if heatmap_data.loc[sensor, day] == 0:
                    heatmap_data.loc[sensor, day] = 1
            active = False
            start_active = None
        elif mode in ["change battery", "change card"]:
            if d in heatmap_data.columns:
                val = heatmap_data.loc[sensor, d]
                if mode == "change battery":
                    if val in [0, 1]:
                        heatmap_data.loc[sensor, d] = 2
                    elif val in [3]:
                        heatmap_data.loc[sensor, d] = 4
                elif mode == "change card":
                    if val in [0, 1]:
                        heatmap_data.loc[sensor, d] = 3
                    elif val in [2]:
                        heatmap_data.loc[sensor, d] = 4

    # If started but never ended
    if active and start_active is not None:
        mask = (all_days >= start_active) & (all_days <= end_date)
        for day in all_days[mask]:
            if heatmap_data.loc[sensor, day] == 0:
                heatmap_data.loc[sensor, day] = 1

    # Build hover text
    for day in all_days:
        val = heatmap_data.loc[sensor, day]
        status = {0: "Inactive", 1: "Active", 2: "Change Battery",
                  3: "Change Card", 4: "Battery & Card Change"}[val]

        text = f"<b>Date:</b> {day.strftime('%Y-%m-%d')}<br>" \
               f"<b>Sensor:</b> {sensor}<br>" \
               f"<b>Event:</b> {status}<br>"

        # Only show Notes if there is something
        if day_notes[day]:
            text += f"<b>Notes:</b><br>{day_notes[day]}"

        hover_data.loc[sensor, day] = text

    # Multi-year heatmaps
    years = sorted(set(all_days.year))
    for yr in years:
        year_days = all_days[all_days.year == yr]
        z = heatmap_data.loc[:, year_days].values
        text = hover_data.loc[:, year_days].values

        fig = go.Figure(go.Heatmap(
            z=z,
            x=year_days,
            y=sensors,
            text=text,
            hoverinfo='text',
            colorscale=[[0/4, color_map[0]], [1/4, color_map[1]], [2/4, color_map[2]],
                        [3/4, color_map[3]], [4/4, color_map[4]]],
            zmin=0,
            zmax=4,
            showscale=False  # hide legend
        ))

        # Add vertical lines to separate months
        month_starts = [d for d in year_days if d.day == 1]
        for m_start in month_starts:
            fig.add_vline(x=m_start, line=dict(color='gray', width=1))

        # Set x-axis ticks at month centers with abbreviations
        month_centers = []
        month_labels = []
        for m in range(1, 13):
            month_days = [d for d in year_days if d.month == m]
            if not month_days:
                continue
            center_day = month_days[len(month_days)//2]
            month_centers.append(center_day)
            month_labels.append(calendar.month_abbr[m])

        fig.update_xaxes(
            tickmode='array',
            tickvals=month_centers,
            ticktext=month_labels
        )

        # Add horizontal lines between sensors
        shapes = []
        for i in range(1, len(sensors)):
            shapes.append(dict(
                type="line",
                xref="x",
                yref="y",
                x0=year_days[0],
                x1=year_days[-1],
                y0=i - 0.5,
                y1=i - 0.5,
                line=dict(color="lightgray", width=1, dash="dash")
            ))
        fig.update_layout(shapes=shapes)

        fig.update_layout(
            title=f"{yr}",
            yaxis_title="Sensor ID",
            xaxis_title="Month",
            height=len(sensors)*60 + 150
        )

        st.plotly_chart(fig, use_container_width=True)

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
build_heatmap(df)































