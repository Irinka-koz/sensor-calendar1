import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date
import plotly.graph_objects as go
import mplcursors
import calendar

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

    # Colors mapping (same as matplotlib version)
    color_map = {
        0: 'white',
        1: '#00CC66',  # green
        2: '#FF3333',  # red
        3: '#FF9900',  # orange
        4: '#800080'   # purple
    }

    # Multi-year heatmaps
    years = sorted(set(all_days.year))
    for yr in years:
        year_days = all_days[all_days.year == yr]
        z = []
        hover_text = []

        for sensor in sensors:
            row_vals = []
            row_hover = []
            sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
            active = False
            start_active = None
            for d in year_days:
                val = 0
                note = ""
                rows_on_day = sdata[sdata['date'].dt.date == d.date()]
                event_text = "Inactive"
                if not rows_on_day.empty:
                    for _, r in rows_on_day.iterrows():
                        if r['mode'] == 'start':
                            active = True
                            start_active = r['date']
                            val = 1
                            event_text = 'Start'
                            note = r.get('note', '')
                        elif r['mode'] == 'end' and active:
                            active = False
                            val = 1
                            event_text = 'End'
                            note = r.get('note', '')
                        elif r['mode'] == 'change battery':
                            val = 2
                            event_text = 'Battery'
                            note = r.get('note', '')
                        elif r['mode'] == 'change card':
                            val = 4 if val == 2 else 3
                            event_text = 'Card'
                            note = r.get('note', '')
                elif active:
                    val = 1
                    event_text = 'Active'

                row_vals.append(val)
                hover_text_str = f"Date: {d.date()}<br>Sensor: {sensor}<br>Event: {event_text}<br>Note: {note}"
                row_hover.append(hover_text_str)
            z.append(row_vals)
            hover_text.append(row_hover)

        # Build Plotly heatmap
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=[d.date() for d in year_days],
            y=sensors,
            text=hover_text,
            hoverinfo='text',
            colorscale=[[0, color_map[0]], [0.2, color_map[1]], [0.4, color_map[2]],
                        [0.6, color_map[3]], [0.8, color_map[4]]],
            showscale=False
        ))

        # Vertical lines for month boundaries
        month_ends = []
        for m in range(1, 13):
            last_day = pd.Timestamp(f"{yr}-{m}-{calendar.monthrange(yr, m)[1]}")
            if last_day < pd.Timestamp(f"{yr}-01-01") or last_day > end_date:
                continue
            month_ends.append((last_day - pd.Timestamp(f"{yr}-01-01")).days)
            fig.add_shape(
                type="line",
                x0=month_ends[-1], x1=month_ends[-1],
                y0=-0.5, y1=len(sensors)-0.5,
                line=dict(color="gray", width=1, dash="dot")
            )

        # Horizontal lines between sensors
        for y in range(len(sensors)):
            fig.add_shape(
                type="line",
                x0=-0.5, x1=len(year_days)-0.5,
                y0=y-0.5, y1=y-0.5,
                line=dict(color="lightgray", width=1, dash="dot")
            )

        # Layout
        fig.update_layout(
            title=f"{yr}",
            xaxis=dict(tickmode='array',
                       tickvals=[(month_ends[i-1]+month_ends[i])/2 if i>0 else month_ends[0]/2 for i in range(len(month_ends))],
                       ticktext=[calendar.month_abbr[m] for m in range(1, len(month_ends)+1)],
                       tickangle=-45),
            yaxis=dict(autorange='reversed'),
            height=40*len(sensors)+200
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





