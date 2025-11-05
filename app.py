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

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp(date.today())
    all_days = pd.date_range(start=start_date, end=end_date)

    sensors = df['Sensor_ID'].dropna().unique()
    # Now we store both the VALUE (for color) and the HOVER TEXT
    heatmap_data = pd.DataFrame(0, index=sensors, columns=all_days)
    hover_data = pd.DataFrame("", index=sensors, columns=all_days) 

    # Colors mapping (for value 0 to 4)
    # 0: Inactive/Empty, 1: Active, 2: Battery, 3: Card, 4: Both
    # Note: Plotly uses a continuous color scale or explicit color mapping.
    
    # Fill heatmap_data and hover_data (Logic remains mostly the same)
    for sensor in sensors:
        sdata = df[df["Sensor_ID"] == sensor].sort_values("date")
        active = False
        start_active = None
        
        # Temporary storage for notes to be displayed on hover
        day_notes = {day: "" for day in all_days} 

        for _, row in sdata.iterrows():
            mode = row["mode"]

            # Check for NaT/None before calling normalize()
            if pd.isna(row["date"]): 
                 continue

            
            d = row["date"].normalize() # Use only date part
            note = row["note"] if pd.notna(row["note"]) else ""
            
            #if pd.isna(d):
                #continue
                
            # Accumulate notes for that day/sensor combination
            if note:
                day_notes[d] += f"- {mode}: {note}<br>"
            else:
                day_notes[d] += f"- {mode}<br>"

            if mode == "start":
                start_active = d
                active = True
            elif mode == "end" and start_active is not None:
                end_active = d
                mask = (all_days >= start_active) & (all_days <= end_active)
                for day in all_days[mask]:
                    # Priority 1: Active
                    if heatmap_data.loc[sensor, day] == 0:
                        heatmap_data.loc[sensor, day] = 1 
                active = False
                start_active = None
            elif mode in ["change battery", "change card"]:
                if d in heatmap_data.columns:
                    current_val = heatmap_data.loc[sensor, d]
                    if mode == "change battery":
                        if current_val == 1:       # active + battery (Val: 2)
                            heatmap_data.loc[sensor, d] = 2 
                        elif current_val == 3:     # card + battery (Val: 4)
                            heatmap_data.loc[sensor, d] = 4
                        elif current_val == 0:     # only battery (Val: 2)
                            heatmap_data.loc[sensor, d] = 2
                    elif mode == "change card":
                        if current_val == 1:       # active + card (Val: 3)
                            heatmap_data.loc[sensor, d] = 3
                        elif current_val == 2:     # battery + card (Val: 4)
                            heatmap_data.loc[sensor, d] = 4
                        elif current_val == 0:     # only card (Val: 3)
                            heatmap_data.loc[sensor, d] = 3
        
        # If started but never ended — mark until today
        if active and start_active is not None:
            mask = (all_days >= start_active) & (all_days <= end_date)
            for day in all_days[mask]:
                if heatmap_data.loc[sensor, day] == 0:
                    heatmap_data.loc[sensor, day] = 1 # Active (Val: 1)
        
        # Fill hover text based on value and accumulated notes
        for day in all_days:
            val = heatmap_data.loc[sensor, day]
            status = ""
            # Map value to status text
            if val == 1: status = "Active"
            elif val == 2: status = "Change Battery"
            elif val == 3: status = "Change Card"
            elif val == 4: status = "Battery & Card Change"
            else: status = "Inactive"
            
            # Combine status and notes
            hover_text = f"<b>Date:</b> {day.strftime('%Y-%m-%d')}<br>"
            hover_text += f"<b>Sensor:</b> {sensor}<br>"
            hover_text += f"<b>Status:</b> {status}<br><br>"
            
            day_key = day.normalize()
            if day_key in day_notes and day_notes[day_key]:
                hover_text += f"<b>Events:</b><br>{day_notes[day_key]}"
            
            hover_data.loc[sensor, day] = hover_text


    # Multi-year heatmaps (Plotly handles multiple years better in one figure)
    years = sorted(set(all_days.year))
    for yr in years:
        year_days = all_days[all_days.year == yr]
        data_to_plot = heatmap_data.loc[:, year_days]
        hover_to_plot = hover_data.loc[:, year_days]

        # Use Plotly Express or Graph Objects for an interactive heatmap
        
        # Define the custom color scale and color mapping
        colorscale = [
            [0/4, '#FFFFFF'],  # Value 0: White (Inactive/Empty)
            [1/4, '#00CC66'],  # Value 1: Green (Active)
            [2/4, '#FF3333'],  # Value 2: Red (Battery)
            [3/4, '#FF9900'],  # Value 3: Orange (Card)
            [4/4, '#800080']   # Value 4: Purple (Both)
        ]
        
        fig = go.Figure(data=go.Heatmap(
            z=data_to_plot.values,
            x=data_to_plot.columns.strftime('%Y-%m-%d'),
            y=data_to_plot.index.tolist(),
            text=hover_to_plot.values, 
            hoverinfo='text', # Crucial: tells Plotly to use the 'text' array for hover
            colorscale=colorscale,
            zmin=0,
            zmax=4,
            xgap=1,  # Adjust gap for visual separation
            ygap=1,
            colorbar=dict(
                title='Status',
                tickvals=[0.5, 1.5, 2.5, 3.5], # Positions for ticks
                ticktext=['Inactive', 'Active', 'Battery', 'Card/Both'] # Simplified Legend
            )
        ))

        fig.update_layout(
            title=f"{yr}",
            xaxis_nticks=len(year_days) // 30, # Simple way to limit x-axis ticks
            xaxis={'tickangle': 45},
            yaxis={'title': 'Sensor ID'},
            height=len(sensors) * 30 + 150 # Dynamic height
        )

        # Better X-axis month labels (optional but improves clarity)
        month_starts = [d for d in year_days if d.day == 1]
        fig.update_xaxes(
            tickmode='array',
            tickvals=[d.strftime('%Y-%m-%d') for d in month_starts],
            ticktext=[calendar.month_abbr[d.month] for d in month_starts],
            showgrid=False
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





















