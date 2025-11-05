import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date
import plotly.graph_objects as go

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
def build_heatmap_plotly(df):
    if df.empty:
        st.warning("No data yet.")
        return

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp(date.today())
    all_days = pd.date_range(start=start_date, end=end_date)

    sensors = df['Sensor_ID'].dropna().unique()
    z = []
    hover_text = []

    # Colors mapping
    color_map = {
        0: 'white',
        1: 'green',
        2: 'red',
        3: 'orange',
        4: 'purple'
    }

    # Build z matrix and hover text
    for sensor in sensors:
        row_vals = []
        row_hover = []
        sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
        active = False
        start_active = None
        for d in all_days:
            val = 0
            note = ""
            # find if there is a matching row
            rows_on_day = sdata[sdata['date'].dt.date == d.date()]
            if not rows_on_day.empty:
                for _, r in rows_on_day.iterrows():
                    if r['mode'] == 'start':
                        active = True
                        start_active = r['date']
                        val = 1
                        note = r.get('note', '')
                    elif r['mode'] == 'end' and active:
                        active = False
                        val = 1
                        note = r.get('note', '')
                    elif r['mode'] == 'change battery':
                        val = 2
                        note = r.get('note', '')
                    elif r['mode'] == 'change card':
                        val = 3 if val !=2 else 4
                        note = r.get('note', '')
            elif active:
                val = 1
            row_vals.append(val)
            hover_text_str = f"Date: {d.date()}<br>Sensor: {sensor}<br>Event: {rows_on_day['mode'].iloc[0] if not rows_on_day.empty else 'Active'}<br>Note: {note}"
            row_hover.append(hover_text_str)
        z.append(row_vals)
        hover_text.append(row_hover)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=[d.date() for d in all_days],
        y=sensors,
        hoverinfo='text',
        text=hover_text,
        colorscale=[[0, 'white'], [0.2, 'green'], [0.4, 'red'], [0.6, 'orange'], [0.8, 'purple']],
        showscale=False
    ))

    fig.update_layout(
        height=40*len(sensors)+200,
        xaxis=dict(tickangle=-45),
        yaxis=dict(autorange='reversed')
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
build_heatmap_plotly(df)  # <--- use the Plotly version
