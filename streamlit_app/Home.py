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

# Load metadata only for slider
df = pd.read_parquet(DATA_PATH)
df["timestamp"] = df["tag"].dt.strftime("%Y-%m-%d") + " " + df["hour"].astype(str).str.zfill(2) + ":00"
unique_times = sorted(df["timestamp"].unique())
selected_time = st.select_slider("Select Hour", options=unique_times)

# Sanitize timestamp for file naming
safe_ts = selected_time.replace(":", "-")
snapshot_path = os.path.join(SNAPSHOT_DIR, f"road_kpi_{safe_ts}.geojson")

@st.cache_data(show_spinner="Loading pre-generated snapshot...")
def load_snapshot(path: str) -> gpd.GeoDataFrame:
    return gpd.read_file(path)

# Load snapshot
start = time.time()
gdf_road_kpi = load_snapshot(snapshot_path)
st.write(f"Loaded in {time.time() - start:.2f} seconds")


# --- Determine map view from last interaction ---
last_view = st.session_state.get("last_map_interaction", {})
zoom = last_view.get("zoom", 12)
center = last_view.get("center", [52.52, 13.405])

if isinstance(center, dict):
    center = [center["lat"], center["lng"]]

# Build map
builder = TrafficMapBuilder(MAP_PATH)
builder.build_folium_map(zoom_start=zoom, center=center,show_detectors=False)
builder.add_street_layer(gdf_road_kpi, value_col="q_kfz_det_hr_avg")

st.markdown("### 📍 Detector Locations (from Stammdaten Excel)")

st_data = st_folium(builder.folium_map, width=1200, height=500, key="map")

# --- Save current map interaction back to session_state ---
if st_data and "zoom" in st_data and "center" in st_data:
    st.session_state["last_map_interaction"] = {
        "zoom": st_data["zoom"],
        "center": st_data["center"]
    }
