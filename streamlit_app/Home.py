# streamlit_app/Home.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(ROOT_DIR, "data", "processed", "kpi_enriched_dec_2024.parquet")
MAP_PATH = os.path.join(ROOT_DIR, "data", "raw", "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx")

import streamlit as st
import pandas as pd
import geopandas as gpd
from streamlit_folium import st_folium
from scripts.traffic_map_builder import TrafficMapBuilder
from scripts.processor.osm_matcher import StreetMatcher

import time

st.set_page_config(page_title="Berlin Traffic Map", layout="wide")
st.title("🛣️ Berlin Traffic Detector Map")

# Load enriched data
df = pd.read_parquet(DATA_PATH)

# Create timestamp string for filtering & Streamlit slider
df["timestamp"] = df["tag"].dt.strftime("%Y-%m-%d") + " " + df["hour"].astype(str).str.zfill(2) + ":00"
unique_times = sorted(df["timestamp"].unique())
selected_time = st.select_slider("Select Hour", options=unique_times)
df_selected = df[df["timestamp"] == selected_time]

@st.cache_data(show_spinner="Matching detectors to roads...")
def get_road_kpi(df_selected: pd.DataFrame) -> gpd.GeoDataFrame:
    matcher = StreetMatcher()
    matcher.load_osm_network()
    gdf_matched = matcher.match_detectors_to_segments(df_selected)
    gdf_road_kpi = matcher.aggregate_kpi_by_osm_segment(gdf_matched)
    
    # Simplify geometry for rendering
    gdf_road_kpi["geometry"] = gdf_road_kpi["geometry"].simplify(
        tolerance=0.0001, preserve_topology=True
    )

    return gdf_road_kpi

start = time.time()
gdf_road_kpi = get_road_kpi(df_selected)
st.write(f"Loaded in {time.time() - start:.2f} seconds")

#Simplify geometry
gdf_road_kpi["geometry"] = gdf_road_kpi["geometry"].simplify(
    tolerance=0.0001, preserve_topology=True
)

# Load and display map
builder = TrafficMapBuilder(MAP_PATH)
builder.build_folium_map(show_detectors=False)
builder.add_street_layer(gdf_road_kpi, value_col="q_kfz_det_hr_avg")

st.markdown("### 📍 Detector Locations (from Stammdaten Excel)")
st_data = st_folium(builder.folium_map, width=1400, height=800)