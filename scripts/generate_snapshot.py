import pandas as pd
import os
import sys
from processor.osm_matcher_2 import StreetMatcher
from pymongo import MongoClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Configuration for MongoDB (replace with your connection details)
MONGO_URI = "mongodb://localhost:27017/" # For local testing
DB_NAME = "traffic_dashboard"
COLLECTION_NAME = "road_kpi_snapshots"

# Establish MongoDB Connection
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print(f"Connected to MongoDB: {MONGO_URI}, Database: {DB_NAME}, Collection: {COLLECTION_NAME}")

    # Optional: Clear existing data before inserting new snapshots
    # This is useful during development to ensure a clean slate
    collection.delete_many({})
    print(f"Cleared existing data in collection: {COLLECTION_NAME}")

    # # Try creating a simple index first
    # collection.create_index("timestamp")
    # print("Created index on timestamp.")
    
    # Create indexes for efficient querying
    collection.create_index([
        ("timestamp", 1),
        ("vehicle_type", 1),
        ("kpi_type", 1)
    ])
    print("Created compound index on timestamp, vehicle_type, kpi_type.")

except Exception as e:
    print(f"Error connecting to MongoDB or delete many or creating index: {e}")
    sys.exit(1) # Exit if cannot connect to DB


# Paths relative to project root
DATA_PATH = os.path.join(ROOT_DIR,"src","data", "processed", "kpi_enriched_dec_2024.parquet")
SAVE_DIR = "data/road_kpi_snapshots"

# Create output directory if not exists
# os.makedirs(SAVE_DIR, exist_ok=True)

# Load data and generate timestamp
df = pd.read_parquet(DATA_PATH)
df["timestamp"] = df["tag"].dt.strftime("%Y-%m-%d") + " " + df["hour"].astype(str).str.zfill(2) + ":00"
unique_times = df["timestamp"].unique()

KPI_COMBINATIONS = {
    "all_number_of_vehicles": "q_kfz_det_hr",
    "all_avg_speed": "v_kfz_det_hr",
    "cars_number_of_vehicles": "q_pkw_det_hr",
    "cars_avg_speed": "v_pkw_det_hr",
    "trucks_number_of_vehicles": "q_lkw_det_hr",
    "trucks_avg_speed": "v_lkw_det_hr",
}

# Prepare matcher once
matcher = StreetMatcher()
matcher.load_osm_network()

print(f"Generating and saving {len(unique_times) * len(KPI_COMBINATIONS)} snapshots to MongoDB...")

# Generate and save each snapshot
for ts_str in unique_times:
    df_ts_selected = df[df["timestamp"] == ts_str].copy()
    
    for combo_key, kpi_column_name in KPI_COMBINATIONS.items():
        parts = combo_key.split('_', 1) # Split only on the first underscore
        vehicle_type = parts[0]
        kpi_type = parts[1]

        # Ensure the KPI column exists in the filtered DataFrame for this timestamp
        if kpi_column_name not in df_ts_selected.columns:
            print(f"Warning: KPI column '{kpi_column_name}' not found for {ts_str}, combo '{combo_key}'. Skipping this combination.")
            continue # Skip this snapshot if the required data column is missing
        
        gdf_matched = matcher.match_detectors_to_segments(df_ts_selected)
        
        # Aggregate the specific KPI column for this combination
        try:
            gdf_road_kpi = matcher.aggregate_kpi_by_osm_segment(gdf_matched,kpi_col=kpi_column_name)
        except ValueError as e:
            print(f"Error aggregating KPI for {ts_str}, combo '{combo_key}': {e}. Skipping.")
            continue # Skip if aggregation fails (e.g., kpi_col not found in gdf_matched)
        
        # Simplify geometry for faster rendering
        if 'geometry' in gdf_road_kpi.columns and not gdf_road_kpi['geometry'].empty:
            gdf_road_kpi["geometry"] = gdf_road_kpi["geometry"].simplify(0.0001, preserve_topology=True)
        else:
            print(f"Warning: No valid geometry found for {ts_str}, combo '{combo_key}'. Skipping insertion.")
            continue # Skip insertion if no geometry or empty GeoDataFrame
        
        # Convert to GeoJSON dictionary and prepare for MongoDB
        if not gdf_road_kpi.empty:
            geojson_dict = gdf_road_kpi.__geo_interface__ # This gives a dict suitable for GeoJSON spec
            snapshot_document = {
                "timestamp": ts_str,
                "vehicle_type": vehicle_type,
                "kpi_type": kpi_type,
                "features": geojson_dict["features"] # Extract just the features list
            }
            # Insert into MongoDB
            try:
                collection.insert_one(snapshot_document)
                print(f"Inserted snapshot for: {ts_str} | Vehicle: {vehicle_type} | KPI: {kpi_type}")
                print("---------------------------------")
            except Exception as e:
                print(f"Error inserting document for {ts_str}, combo '{combo_key}': {e}")
                print("---------------------------------")
        else:
            print(f"No data to insert for {ts_str}, combo '{combo_key}'. GeoDataFrame was empty after aggregation.")

print("\nMongoDB data generation complete!")
client.close() # Close connection when done
