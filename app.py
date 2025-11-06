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

        # --- Filter controls ---
    st.subheader("🔍 Filter data")

    # Make sure the new columns exist
    if 'Area' not in df.columns:
        df['Area'] = 'Unknown'
    if 'Type' not in df.columns:
        df['Type'] = 'Unknown'

    # Get unique values for filters
    all_areas = sorted(df['Area'].dropna().unique().tolist())
    all_sensors = sorted(df['Sensor_ID'].dropna().unique().tolist())
    all_types = sorted(df['Type'].dropna().unique().tolist())
    

    # Create multiselect widgets
    col1, col2, col3 = st.columns(3)
    selected_areas = col1.multiselect("Select Area(s)", all_areas, default=all_areas)
    selected_sensors = col2.multiselect("Select Sensor ID(s)", all_sensors, default=all_sensors)
    selected_types = col3.multiselect("Select Type(s)", all_types, default=all_types)

    # --- Apply filters ---
    filtered_df = df[
        df['Area'].isin(selected_areas) &
        df['Sensor_ID'].isin(selected_sensors) &
        df['Type'].isin(selected_types)
    ]

    if filtered_df.empty:
        st.warning("No data found for the selected filters.")
        return


    filtered_df['date'] = pd.to_datetime(filtered_df['date'], errors='coerce')
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp(date.today())
    all_days = pd.date_range(start=start_date, end=end_date)

    sensors = filtered_df['Sensor_ID'].dropna().unique()
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
        sdata = filtered_df[filtered_df["Sensor_ID"] == sensor].sort_values("date")
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
                day_notes[d] += f"- {note}<br>"
    
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
                text += f"<b>Notes:</b>{day_notes[day]}"
    
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
            ticktext=month_labels,
            tickfont=dict(size=16)
        )
        fig.update_yaxes(
            tickfont=dict(size=16)  # y-axis label font
        )
        # Vertical lines at month ends
        shapes = []
        
        for m in range(1, 13):
            # Get all days in this month
            month_days = [d for d in year_days if d.month == m]
            if not month_days:
                continue
            last_day = month_days[-1]  # last day of the month within year_days
            shapes.append(dict(
                type="line",
                xref="x",
                yref="paper",
                x0=last_day,
                x1=last_day,
                y0=0,
                y1=1,
                line=dict(color='gray', width=1,  dash="solid")
            ))
        
        # Horizontal lines between sensors
        for i in range(1, len(sensors)):
            shapes.append(dict(
                type="line",
                xref="x",
                yref="y",
                x0=year_days[0],
                x1=year_days[-1],
                y0=i - 0.5,
                y1=i - 0.5,
                line=dict(color="black", width=1.3, dash="solid")
            ))
        
        # Apply shapes
        fig.update_layout(shapes=shapes)


        fig.update_layout(
            title=dict(
                text=f"{yr}",   # Your title
                x=0.5,          # Center horizontally (0 = left, 0.5 = center, 1 = right)
                xanchor='center',
                yanchor='top',
                font=dict(size=24)  # Optional: make it bigger
            ),
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
    "S1": {"Location": "Field A", "Type": "PM", "Area": "Carmel"},
    "S2": {"Location": "Field B", "Type": "RH", "Area": "Tzinim"},
    "S3": {"Location": "Field A", "Type": "Temp", "Area": "Tzinim"},
}

# =============================
# TOP ROW: TABLE + INPUT FORM
# =============================
col_left, col_center, col_right = st.columns([1,1,2])

# --- Right column: Sensor info table ---
with col_right:
    st.subheader("Sensors Info")
    sensor_info_table = pd.DataFrame([
        {"Sensor ID": k, "Area":v["Area"], "Location": v["Location"], "Type": v["Type"]}
        for k, v in sensor_info.items()
    ])
    st.dataframe(sensor_info_table, use_container_width=True, height=150)


# --- Initialize session_state keys at the very top ---
if "sensor" not in st.session_state:
    st.session_state.sensor = ""
if "mode_select" not in st.session_state:
    st.session_state.mode_select = ""
if "date_input" not in st.session_state:
    st.session_state.date_input = date.today()
if "note_input" not in st.session_state:
    st.session_state.note_input = ""
if "record_message" not in st.session_state:  # <-- new key to store messages
    st.session_state.record_message = None

# --- Define the reset function ---
def reset_form():
    st.session_state.sensor = ""
    st.session_state.mode_select = ""
    st.session_state.date_input = date.today()
    st.session_state.note_input = ""

# --- Left column: input form ---
with col_left:
    st.subheader("Add a New Record")

    sensor_options = [""] + list(sensor_info.keys())
    sensor_id = st.selectbox("Sensor ID", sensor_options, key="sensor", label_visibility="collapsed")

    mode_options = ["", "start", "end", "change battery", "change card"]
    mode = st.selectbox("Mode", mode_options, key="mode_select", label_visibility="collapsed")

    selected_date = st.date_input("Select Date", max_value=date.today(), format="DD/MM/YYYY", key="date_input")

    note = st.text_input("Note (optional)", key="note_input")


    # Show previous message if exists
    if st.session_state.record_message:
        if st.session_state.record_message_type == "success":
            message_placeholder.success(st.session_state.record_message)
        elif st.session_state.record_message_type == "warning":
            message_placeholder.warning(st.session_state.record_message)

    # Use on_click callback for button
    def add_record():
        if sensor_id == "":
            st.session_state.record_message = "⚠️ Please select a Sensor ID before adding a record."
            st.session_state.record_message_type = "warning"
            return
        elif mode == "":
            st.session_state.record_message = "⚠️ Please select an Event."
            st.session_state.record_message_type = "warning"
            return
        
        location = sensor_info[sensor_id]["Location"]
        stype = sensor_info[sensor_id]["Type"]
        Area = sensor_info[sensor_id]["Area"]

        new_row = {
            "Sensor_ID": sensor_id,
            "Area": Area,
            "Location": location,
            "Type": stype,
            "mode": mode,
            "date": pd.to_datetime(selected_date),
            "note": note
        }
        df = pd.concat([load_sheet(), pd.DataFrame([new_row])], ignore_index=True)
        save_sheet(df)

        # Set success message in session_state
        st.session_state.record_message = "✅ Record added successfully!"
        st.session_state.record_message_type = "success"

    # Placeholder for messages
    message_placeholder = st.empty()
        
        reset_form()  # reset widgets after success

    st.button("Add Record", use_container_width=True, on_click=add_record)


# =============================
# BOTTOM: FULL-WIDTH HEATMAP
# =============================
st.markdown("---")
st.header("Sensor Maintenance Calendar")
build_heatmap(df)









































































