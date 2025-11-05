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

    # Ensure 'date' is datetime and create full range
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp(date.today())
    full_range = pd.date_range(start=start_date, end=end_date)

    # Pivot the data (Sensor_ID x Date)
    pivot = df.pivot_table(
        index="Sensor_ID",
        columns="date",
        values="mode",
        aggfunc="count",
        fill_value=0
    )

    # Reindex columns to fill missing days
    pivot = pivot.reindex(columns=full_range, fill_value=0)

    # Build heatmap
    fig, ax = plt.subplots(figsize=(12, 4))
    sns.heatmap(
        pivot,
        cmap="YlOrRd",
        linewidths=0.5,
        ax=ax,
        cbar_kws={'label': 'Activity count'}
    )

    ax.set_title("Sensor Activity Heatmap (since Jan 2024)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sensor ID")

    # Rotate x-ticks and make them readable
    ax.set_xticks(range(0, len(full_range), max(len(full_range)//10, 1)))
    ax.set_xticklabels(
        [d.strftime("%b %d") for d in full_range[::max(len(full_range)//10, 1)]],
        rotation=45,
        ha="right"
    )

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






