# streamlit_app/Home.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(ROOT_DIR, "data", "processed", "kpi_enriched_dec_2024.parquet")
SNAPSHOT_DIR = os.path.join(ROOT_DIR, "data", "road_kpi_snapshots")
MAP_PATH = os.path.join(ROOT_DIR, "data", "raw", "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx")

import streamlit as st
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium
from scripts.traffic_map_builder import TrafficMapBuilder
import time

# UI setup
st.set_page_config(page_title="Berlin Traffic Map", layout="wide")
st.title("🛣️ Berlin Traffic Detector Map")

# Load metadata for slider
# Using st.cache_data for this initial data load as it's static
@st.cache_data
def load_initial_data(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    # Ensure 'tag' is datetime for consistency
    if not pd.api.types.is_datetime64_any_dtype(df['tag']):
        df['tag'] = pd.to_datetime(df['tag'])
    return df

df = load_initial_data(DATA_PATH)
df["timestamp"] = df["tag"].dt.strftime("%Y-%m-%d") + " " + df["hour"].astype(str).str.zfill(2) + ":00"
unique_times = sorted(df["timestamp"].unique())

# --- Initialize session state ---
if "selected_time" not in st.session_state:
    st.session_state["selected_time"] = unique_times[0]

# Time slider directly under map — clean layout
# The value for the slider is taken from session state, ensuring it's always in sync
selected = st.select_slider(
    "Select Hour",
    options=unique_times,
    value=st.session_state["selected_time"], # Use session state for initial value
    key="time_slider"
)
# Update session state with the new selection
st.session_state["selected_time"] = selected

# Use the selected_time from session state for snapshot loading
current_selected_time = st.session_state["selected_time"]

# --- Load snapshot based on selected_time in session ---
# Replace colons for a valid filename
safe_ts = current_selected_time.replace(":", "-")
snapshot_path = os.path.join(SNAPSHOT_DIR, f"road_kpi_{safe_ts}.geojson")

# --- Load GeoJSON snapshot ---
# st.cache_data ensures this function only re-runs if `path` changes
@st.cache_data(show_spinner="Loading pre-generated snapshot...")
def load_snapshot(path: str) -> gpd.GeoDataFrame:
    try:
        return gpd.read_file(path)
    except Exception as e:
        st.error(f"Error loading snapshot from {path}: {e}")
        # Return an empty GeoDataFrame or handle gracefully
        return gpd.GeoDataFrame()

start = time.time()
gdf_road_kpi = load_snapshot(snapshot_path)
st.write(f"Loaded in {time.time() - start:.2f} seconds")

# --- Determine map view from last interaction ---
# Initialize last_map_interaction if it doesn't exist
if "last_map_interaction" not in st.session_state:
    st.session_state["last_map_interaction"] = {}

last_view = st.session_state.get("last_map_interaction", {})
zoom = last_view.get("zoom", 12)
center = last_view.get("center", [52.52, 13.405])
if isinstance(center, dict):
    center = [center["lat"], center["lng"]]

# --- Build and display map ---
builder = TrafficMapBuilder(MAP_PATH)
builder.build_folium_map(zoom_start=zoom, center=center, show_detectors=False)
builder.add_street_layer(gdf_road_kpi, value_col="q_kfz_det_hr_avg")

map_container = st.container()
with map_container:
    st.markdown("### 📍 Detector Locations (from Stammdaten Excel)")
    # IMPORTANT FIX: Change the key to include the selected_time.
    # This forces Streamlit to re-render the map whenever the time slider changes,
    # because the key becomes different.
    st_data = st_folium(
        builder.folium_map,
        width=1000,
        height=500,
        key=f"map_{current_selected_time}" # Dynamic key for forced refresh
    )

# Save current interaction
if st_data and "zoom" in st_data and "center" in st_data:
    st.session_state["last_map_interaction"] = {
        "zoom": st_data["zoom"],
        "center": st_data["center"]
    }

