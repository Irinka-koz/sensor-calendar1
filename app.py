import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date

CSV_FILE = calendar.csv

# -------------------------
# Load CSV
# -------------------------
def load_csv():
    try:
        df = pd.read_csv(CSV_FILE, sep=",")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["Sensor_ID", "Location", "Type", "mode", "date"])
        df.to_csv(CSV_FILE, sep=",", index=False)
    df["Date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


# -------------------------
# Save CSV
# -------------------------
def save_csv(df):
    df.to_csv(CSV_FILE, sep=",", index=False)


# -------------------------
# Heatmap Builder
# -------------------------
def build_heatmap(df):
    if df.empty:
        st.warning("No data available yet.")
        return

    # Count actions per day per sensor
    pivot = df.pivot_table(index="date", columns="Sensor_ID", values="mode", aggfunc="count", fill_value=0)

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.heatmap(pivot.T, cmap="YlOrRd", linewidths=0.5, ax=ax)
    ax.set_title("Sensor Activity Heatmap")
    st.pyplot(fig)


# -------------------------
# Streamlit UI
# -------------------------
st.title("Sensor Maintenance Log and Heatmap")

df = load_csv()

# Define known sensors
sensor_info = {
    "S1": {"Location": "Field A", "Type": "PM"},
    "S2": {"Location": "Field B", "Type": "RH"},
    "S3": {"Location": "Field A", "Type": "Temp"},
}

st.header("Add a New Record")

# Select sensor
sensor_id = st.selectbox("Select Sensor ID", options=list(sensor_info.keys()))

# Auto-fill location and type
location = sensor_info[sensor_id]["Location"]
stype = sensor_info[sensor_id]["Type"]

st.write(f"**Location:** {location}")
st.write(f"**Type:** {stype}")

# Choose mode (only one)
mode = st.selectbox("Select Mode", options=["start", "end", "change battery", "change card"])

# Pick date
selected_date = st.date_input("Select Date", value=date.today())

# Add record button
if st.button("Add Record"):
    new_row = {
        "Sensor_ID": sensor_id,
        "Location": location,
        "Type": stype,
        "Mode": mode,
        "Date": selected_date,
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_csv(df)
    st.success("Record added successfully!")

# Show updated heatmap
st.header("Sensor Activity Heatmap")
build_heatmap(df)

