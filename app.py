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
# -------------------------xxxx

SCOPE = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
SHEET_ID = "1LcT1Oh6oRdDAhcggbXclkwQRk8MC1ICKyemnjoeULOE"
SENSOR_SHEET_ID = "1iGLU0_1sUeNLyYQdaZHLgbvIi6FMyartXS5s3sPFJfo"

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
    
def load_sensors():
    """Load sensor list from Google Sheets"""
    sheet = client.open_by_key(SENSOR_SHEET_ID).worksheet("Sheet1") # <-- CHANGE IS HERE
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        return df.set_index("Sensor_ID").to_dict(orient="index")
    return {}
# -------------------------
# Save Sheet
# -------------------------
def save_sheet(df):
    set_with_dataframe(sheet, df)

def save_sensors(sensor_info):
    """Save updated sensor list to Google Sheets"""
    sheet = client.open_by_key(SENSOR_SHEET_ID).worksheet("Sheet1")
    set_with_dataframe(sheet, sensor_info)
    
# -------------------------
# Heatmap
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
    start_date = pd.Timestamp("2025-01-01")
    end_date = pd.Timestamp(date.today())
    all_days = pd.date_range(start=start_date, end=end_date)

    sensors = filtered_df['Sensor_ID'].dropna().unique()
    heatmap_data = pd.DataFrame(0, index=sensors, columns=all_days)
    hover_data = pd.DataFrame("", index=sensors, columns=all_days)

    #Map sensor metadata (Location/Type) for easy lookup
    sensor_metadata = filtered_df.groupby('Sensor_ID').agg({
        'Location': lambda x: x.iloc[0], # Get the first non-null location
        'Type': lambda x: x.iloc[0]       # Get the first non-null type
    }).to_dict(orient='index')

    # Define Mappings (Paste TYPE_MAPPING and GREEN_SHADES here)
    TYPE_MAPPING = {
        "Camera": 8,
        "IR": 9,
        "BT": 10,
        "US": 11,
        "Radar": 12
    }
    
    # Colors mapping
    color_map = {
        0: '#e5e5e5',  # Inactive
        1: '#00CC66',  # Active
        2: '#FF3333',  # Battery
        3: '#FF9900',  # Card
        4: '#800080',   # Both
        5: '#3399FF', #Location
        6: '#FCDC4D', #Manual Count
        7: '#D496A7', #Other Event
        8: '#50c878',  # Medium Green (Camera)
        9: '#03C03C',  # Lighter Green (IR)
        10: '#808000',  # Lightest Green (BT)
        11: '#388E3C',  # Darker Green (US)
        12: '#1B5E20'   # Darkest Green (Radar)
    }

    
    # Fill heatmap_data and hover_data
    for sensor in sensors:
        sdata = filtered_df[filtered_df["Sensor_ID"] == sensor].sort_values("date")
        sensor_type = sensor_metadata.get(sensor, {}).get('Type', 'Unknown')
        active_value = TYPE_MAPPING.get(sensor_type, 1) # Default to 1 if type is missing/unknown
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
    
            if mode == "Start":
                start_active = d
                active = True
            elif mode == "End" and start_active is not None:
                mask = (all_days >= start_active) & (all_days <= d)
                for day in all_days[mask]:
                    if heatmap_data.loc[sensor, day] == 0:
                        heatmap_data.loc[sensor, day] = active_value
                active = False
                start_active = None
            elif mode == "Change Location":
                heatmap_data.loc[sensor, d] = 5
            elif mode == "Manual Count":
                heatmap_data.loc[sensor, d] = 6
            elif mode == "Other Event":
                heatmap_data.loc[sensor, d] = 7
            elif mode in ["Change Battery", "Change Card"]:
                if d in heatmap_data.columns:
                    val = heatmap_data.loc[sensor, d]
                    if mode == "Change Battery":
                        if val in [0, 1]:
                            heatmap_data.loc[sensor, d] = 2
                        elif val in [3]:
                            heatmap_data.loc[sensor, d] = 4
                    elif mode == "Change Card":
                        if val in [0, 1]:
                            heatmap_data.loc[sensor, d] = 3
                        elif val in [2]:
                            heatmap_data.loc[sensor, d] = 4
    
        # If started but never ended
        if active and start_active is not None:
            mask = (all_days >= start_active) & (all_days <= end_date)
            for day in all_days[mask]:
                if heatmap_data.loc[sensor, day] == 0:
                    heatmap_data.loc[sensor, day] = active_value


        # Build hover text
        for day in all_days:
            val = heatmap_data.loc[sensor, day]
            status = {0: "Inactive", 1: "Active", 2: "Change Battery",
                      3: "Change Card", 4: "Battery & Card Change", 5:"Change Location", 6:"Manual Count", 7:"Other Event",
                      8: "Camera Active", 9: "IR Active", 10: "BT Active", 11: "US Active", 12: "Radar Active"}[val]

            #status = status_map.get(val, "Unknown")

            # 💡 Access Location and Type from the new metadata dict
            metadata = sensor_metadata.get(sensor, {})
            location = metadata.get('Location', 'N/A')
            sensor_type = metadata.get('Type', 'N/A')
            
            # --- UPDATED HOVER TEXT ---
            text = f"<b>Date:</b> {day.strftime('%Y-%m-%d')}<br>" \
                   f"<b>Location:</b> {location}<br>" \
                   f"<b>Type:</b> {sensor_type}<br>" \
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
            colorscale = [[i/12, color_map[i]] for i in range(13)],
            zmin=0,
            zmax=12,
            showscale=False,  # hide legend
            #pattern_shape=pattern_array.values
        ))

        # Define sensor types and their icons
        icon_map = {
            "Camera": "📷",
            "BT": "📶",
            "IR": "💥",
            "Radar": "📡"
        }
        
        # Loop through each type
        for stype, icon in icon_map.items():
            type_sensors = [s for s in sensors if sensor_metadata.get(s, {}).get('Type') == stype]
            
            highlight_x = []
            highlight_y = []
            highlight_text = []
            
            for sensor in type_sensors:
                sensor_row = heatmap_data.loc[sensor]
                active_days = sensor_row[sensor_row > 0]  # non-zero = active
                if not active_days.empty:
                    first_day = active_days.index[0]
                    highlight_x.append(first_day)
                    highlight_y.append(sensor)
                    highlight_text.append(icon)
            
            # Add icons to figure
            fig.add_trace(go.Scatter(
                x=highlight_x,
                y=highlight_y,
                mode="text",
                text=highlight_text,
                textposition="middle center",
                textfont=dict(size=30),  # adjust size
                showlegend=False,
                hoverinfo="none"
            ))

        # pattern
        # pattern only for North
        highlight_x = []
        highlight_y = []
        highlight_text = []
        
        for sensor in sensors:
            area = sensor_metadata.get(sensor, {}).get("Area", "")
            if area != "North":
                continue  # skip sensors not in North
            
            for day in all_days:
                highlight_x.append(day)
                highlight_y.append(sensor)  # sensor names
                highlight_text.append("                 /")  # your pattern
        
        fig.add_trace(go.Scatter(
            x=highlight_x,
            y=highlight_y,
            mode="text",
            text=highlight_text,
            textposition="middle center",
            textfont=dict(size=65, color="rgba(0,0,0,0.1)"),  # semi-transparent
            showlegend=False,
            hoverinfo="none"
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
sensor_info = load_sensors()

# =============================
# Initialize session_state keys safely
# =============================
for key in [
    "sensor_form", "mode_select_form", "date_input_form", "note_input_form",
    "new_id_form", "new_area_form", "new_location_form", "new_type_form",
    "record_message", "record_message_type"
]:
    if key not in st.session_state:
        if "date" in key:
            st.session_state[key] = date.today()
        else:
            st.session_state[key] = ""

# ----------------------------
# ADD NEW SENSOR (TOP)
# ----------------------------
with st.expander("➕ Add New Sensor"):
    with st.form(key="new_sensor_form", clear_on_submit=True):
        new_id = st.text_input("Sensor ID", key="new_id_form")
        new_area = st.selectbox("Area", ["","North", "South"], key="new_area_form")
        new_location = st.text_input("Location", key="new_location_form")
        new_type = st.selectbox("Type", ["", "Camera", "IR", "BT", "US", "Radar"], key="new_type_form")
        
        submitted_sensor = st.form_submit_button("Add Sensor", use_container_width=True)

    # --- Reset fields safely outside the form ---
    if submitted_sensor:
        if new_id.strip() == "":
            st.warning("⚠️ Please enter a Sensor ID.")
        elif new_id in sensor_info.keys():
            st.warning("⚠️ This Sensor ID already exists.")
        elif new_area .strip() == "":   
            st.warning("⚠️ Please enter Area.")
        elif new_location .strip() == "":   
            st.warning("⚠️ Please enter Location.")
        elif new_type .strip() == "":   
            st.warning("⚠️ Please enter Type.")
            
        else:
            new_sensor = {
                "Sensor_ID": new_id.strip(),
                "Area": new_area,
                "Location": new_location,
                "Type": new_type
            }
            sensor_df = pd.DataFrame.from_dict(load_sensors(), orient="index").reset_index().rename(columns={"index": "Sensor_ID"})
            updated_df = pd.concat([sensor_df, pd.DataFrame([new_sensor])], ignore_index=True)
            save_sensors(updated_df)
            st.success(f"✅ Sensor **{new_id}** added successfully!")
           
            # Reload sensors
            sensor_info = load_sensors()

# ----------------------------
# TABLE + ADD RECORD (ROW)
# ----------------------------
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Add a New Record")
    with st.form(key="new_record_form", clear_on_submit=True):
        sensor_options = [""] + list(sensor_info.keys())
        sensor_id = st.selectbox("Sensor ID", sensor_options, key="sensor_form")
        mode_options = ["", "Start", "End", "Change Location", "Change Battery", "Change Card", "Manual Count", "Other Event"]
        mode = st.selectbox("Event", mode_options, key="mode_select_form")
        selected_date = st.date_input("Select Date", max_value=date.today(), format="DD/MM/YYYY", key="date_input_form")
        note = st.text_input("Note (optional)", key="note_input_form")
        
        submitted_record = st.form_submit_button("Add Record", use_container_width=True)

    # --- Reset fields safely outside the form ---
    if submitted_record:
        if sensor_id == "":
            st.session_state.record_message = "⚠️ Please select a Sensor ID before adding a record."
            st.session_state.record_message_type = "warning"
        elif mode == "":
            st.session_state.record_message = "⚠️ Please select an Event."
            st.session_state.record_message_type = "warning"
        else:
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

            st.session_state.record_message = "✅ Record added successfully!"
            st.session_state.record_message_type = "success"
           

            # Reload data for heatmap
            df = load_sheet()

# --- Right column: Sensor Table ---
with col_right:
    st.subheader("Sensors Info")
    sensor_info_table = pd.DataFrame([
        {"Sensor ID": k, "Area":v["Area"], "Location": v["Location"], "Type": v["Type"]}
        for k, v in sensor_info.items()
    ])
    st.dataframe(sensor_info_table, use_container_width=True, height=410)

# ----------------------------
# HEATMAP
# ----------------------------
st.markdown("---")
st.header("Sensor Maintenance Calendar")
build_heatmap(df)


















































































































