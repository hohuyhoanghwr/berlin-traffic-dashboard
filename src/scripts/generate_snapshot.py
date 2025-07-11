import pandas as pd
import os
import sys
from scripts.processor.osm_matcher import StreetMatcher

sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

# Paths relative to project root
DATA_PATH = "data/processed/kpi_enriched_dec_2024.parquet"
SAVE_DIR = "data/road_kpi_snapshots"

# Create output directory if not exists
os.makedirs(SAVE_DIR, exist_ok=True)

# Load data and generate timestamp
df = pd.read_parquet(DATA_PATH)
df["timestamp"] = df["tag"].dt.strftime("%Y-%m-%d") + " " + df["hour"].astype(str).str.zfill(2) + ":00"
unique_times = df["timestamp"].unique()

# Prepare matcher once
matcher = StreetMatcher()
matcher.load_osm_network()

# Generate and save each snapshot
for ts in unique_times:
    df_selected = df[df["timestamp"] == ts]
    gdf_matched = matcher.match_detectors_to_segments(df_selected)
    gdf_road_kpi = matcher.aggregate_kpi_by_osm_segment(gdf_matched)

    # Simplify geometry for faster rendering
    gdf_road_kpi["geometry"] = gdf_road_kpi["geometry"].simplify(0.0001, preserve_topology=True)

    # Sanitize filename (replace colon with dash)
    safe_ts = ts.replace(":", "-")
    gdf_road_kpi.to_file(f"{SAVE_DIR}/road_kpi_{safe_ts}.geojson", driver="GeoJSON")
