# src/scripts/processor/osm_matcher.py

import os
import pandas as pd
import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point, LineString # Import LineString
from shapely import wkt
import psycopg2 # For connecting to PostgreSQL
from psycopg2 import sql
from psycopg2.extras import execute_values
from dotenv import load_dotenv # Import load_dotenv

class StreetMatcher:
    """
    Matches traffic detector locations to OpenStreetMap (OSM) road segments,
    aggregates KPIs, and loads the data into a PostgreSQL database.
    """
    def __init__(self, network_place="Berlin, Germany", cache_path=None, db_config: dict = None):
        """
        Initializes the StreetMatcher.

        Args:
            network_place (str): The place name for OSMnx to query.
            cache_path (str): Local path to cache the OSM road network graphml file.
            db_config (dict): Dictionary containing database connection parameters.
        """
        if cache_path is None:
            cache_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "..", "..", "data", "osm", "berlin_drive.graphml")
                )
        self.network_place = network_place
        self.cache_path = cache_path
        self.osm_edges = None
        self.db_config = db_config
        self.conn = None
        self.cursor = None

    def _connect_db(self):
        """Establishes a connection to the PostgreSQL database."""
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(**self.db_config)
                self.cursor = self.conn.cursor()
                print("✅ Database connection established for OSM matcher.")
            except Exception as e:
                print(f"❌ Error connecting to database for OSM matcher: {e}")
                self.conn = None
                self.cursor = None
                raise # Re-raise the exception to stop execution

    def _close_db(self):
        """Closes the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed for OSM matcher.")

    def load_osm_network(self):
        """
        Loads the OpenStreetMap road network for Berlin.
        Caches it locally as a GraphML file for faster subsequent loads.
        """
        if os.path.exists(self.cache_path):
            print("📂 Loading cached Berlin road network...")
            G = ox.load_graphml(self.cache_path)
        else:
            print("🌐 Downloading Berlin road network from OpenStreetMap (this may take a while)...")
            G = ox.graph_from_place(self.network_place, network_type='drive')
            # Ensure the directory for cache_path exists
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            ox.save_graphml(G, filepath=self.cache_path)
            print(f"✨ Berlin road network cached to {self.cache_path}")

        self.osm_edges = ox.graph_to_gdfs(G, nodes=False)
        self.osm_edges = self.osm_edges[self.osm_edges["geometry"].notnull()]
        self.osm_edges.reset_index(drop=True, inplace=True)
        self.osm_edges["osm_id_index"] = self.osm_edges.index
        print(f"Loaded {len(self.osm_edges)} OSM road segments.")

    def _to_geo(self, df: pd.DataFrame, lon_col="lon", lat_col="lat") -> gpd.GeoDataFrame:
        """
        Converts a Pandas DataFrame with lat/lon columns to a GeoDataFrame.
        """
        gdf = gpd.GeoDataFrame(
            df.copy(),
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326" # WGS84
        )
        return gdf

    def match_detectors_to_segments(self, df_enriched: pd.DataFrame) -> gpd.GeoDataFrame:
        """
        Matches enriched detector data (points) to the nearest OSM road segments (lines).
        Performs projection for accurate spatial operations.

        Args:
            df_enriched (pd.DataFrame): DataFrame with enriched KPI data, including 'lon', 'lat'.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with detectors matched to road segments,
                              including 'geometry_road_segment' and 'name_road_segment'.
        """
        if self.osm_edges is None:
            self.load_osm_network()

        print(f"--- Matching {len(df_enriched)} detectors to OSM segments ---")
        # Convert enriched DataFrame to GeoDataFrame of points
        gdf_detectors = self._to_geo(df_enriched, lon_col="lon", lat_col="lat")

        # Using EPSG:32633 (WGS 84 / UTM zone 33N) which is suitable for Berlin.
        gdf_detectors_proj = gdf_detectors.to_crs("EPSG:32633")
        osm_edges_proj = self.osm_edges.to_crs("EPSG:32633")
        
        # Perform spatial join to find nearest road segment
        gdf_matched_proj = gpd.sjoin_nearest(
            gdf_detectors_proj,
            osm_edges_proj[['geometry', 'name', 'highway']], # Use projected OSM edges
            how="left",
            max_distance=50, # Max distance in meters (adjust as needed, now in meters)
            distance_col="distance_to_road",
        )
        
        # Add the road segment geometry as a new column
        gdf_matched_proj["geometry_road_segment"] = osm_edges_proj.loc[gdf_matched_proj["index_right"], "geometry"].values

        # Filter out unmatched detectors by checking for NaN in 'index_right'
        gdf_matched_proj = gdf_matched_proj.dropna(subset=['index_right'])

        # Rename columns for clarity. geometry_right is the geometry of the matched OSM segment.
        gdf_matched_proj = gdf_matched_proj.rename(columns={
            'name': 'name_osm_segment', # 'name' from right GeoDataFrame becomes name_osm_segment
        })
        
        # Convert back to original CRS (EPSG:4326) for consistency with database and plotting later
        gdf_matched = gdf_matched_proj.to_crs("EPSG:4326")

        # Fill missing OSM street names with the 'street_name' from original metadata if available
        # 'street_name' is from the original df_enriched, which is part of gdf_matched.
        gdf_matched['name_road_segment'] = gdf_matched['name_osm_segment'].fillna(gdf_matched['street_name'])

        def flatten_name_field(value):
            if isinstance(value, list):
                return ", ".join(sorted(set(map(str, value))))
            return str(value) if pd.notnull(value) else None
        
        gdf_matched["name_road_segment"] = gdf_matched["name_road_segment"].apply(flatten_name_field)

        print(f"✨ Matched {len(gdf_matched)} detectors to road segments.")
        return gdf_matched

    def aggregate_kpi_by_osm_segment(self, gdf_matched: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Aggregates KPI values by the matched OSM road segments for a given timestamp.
        Calculates average vehicle count and average speed for 'all', 'cars', 'trucks'.

        Args:
            gdf_matched (gpd.GeoDataFrame): GeoDataFrame with detectors matched to segments.

        Returns:
            gpd.GeoDataFrame: Aggregated GeoDataFrame with KPIs per road segment.
        """
        print("--- Aggregating KPIs by OSM segment ---")

        # Define KPI columns for aggregation
        kpi_cols = {
            'q_kfz_det_hr': 'all_vehicle_count',
            'v_kfz_det_hr': 'all_average_speed',
            'q_pkw_det_hr': 'cars_vehicle_count',
            'v_pkw_det_hr': 'cars_average_speed',
            'q_lkw_det_hr': 'trucks_vehicle_count',
            'v_lkw_det_hr': 'trucks_average_speed'
        }

        # Group by the unique road segment geometry and name
        # We need to ensure geometry is hashable for groupby, so convert to WKT temporarily
        gdf_matched['geometry_wkt'] = gdf_matched['geometry_road_segment'].apply(lambda x: x.wkt)

        # Aggregate KPIs by segment
        # Use .agg for multiple aggregations
        aggregated_df = gdf_matched.groupby(['geometry_wkt', 'name_road_segment']).agg(
            **{new_name: pd.NamedAgg(column=old_name, aggfunc='mean') for old_name, new_name in kpi_cols.items()}
        ).reset_index()

        # Convert WKT back to geometry
        aggregated_gdf = gpd.GeoDataFrame(
            aggregated_df,
            geometry=aggregated_df['geometry_wkt'].apply(lambda x: wkt.loads(x) if isinstance(x, str) else x),
            crs="EPSG:4326"
        )
        aggregated_gdf = aggregated_gdf.drop(columns=['geometry_wkt'])

        print(f"✨ Aggregated KPIs for {len(aggregated_gdf)} unique road segments.")
        return aggregated_gdf

    def _insert_road_segment_if_not_exists(self, segment_geometry: LineString, segment_name: str) -> int:
        """
        Inserts a road segment into the 'road_segments' table if it doesn't exist,
        and returns its segment_id.
        """
        # Ensure geometry is in EWKT format for PostGIS
        segment_ewkt = segment_geometry.wkt # WKT is sufficient as SRID is handled by table definition

        # Check if segment already exists
        select_query = sql.SQL("SELECT segment_id FROM road_segments WHERE geometry = ST_GeomFromText(%s, 4326)")
        self.cursor.execute(select_query, (segment_ewkt,))
        result = self.cursor.fetchone()

        if result:
            return result[0] # Return existing segment_id
        else:
            # Insert new segment
            insert_query = sql.SQL("INSERT INTO road_segments (name_road_segment, geometry) VALUES (%s, ST_GeomFromText(%s, 4326)) RETURNING segment_id")
            self.cursor.execute(insert_query, (segment_name, segment_ewkt))
            segment_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return segment_id

    def _load_kpis_for_timestamp(self, gdf_aggregated: gpd.GeoDataFrame, current_timestamp: pd.Timestamp):
        """
        Transforms aggregated KPI data for a single timestamp into the
        long format required by 'traffic_kpis' table and inserts it.
        """
        print(f"--- Loading KPIs for timestamp {current_timestamp} ---")

        # Melt the DataFrame to long format for insertion into traffic_kpis
        # Columns: all_vehicle_count, all_average_speed, cars_vehicle_count, ...
        # Need to convert these into (kpi_type, vehicle_type, kpi_value)
        kpi_data_for_db = []
        for _, row in gdf_aggregated.iterrows():
            segment_id = row['segment_id'] # This needs to be available from previous step
            
            # Iterate through the KPI types and vehicle types
            for vehicle_type_prefix in ['all', 'cars', 'trucks']:
                # Vehicle Count
                kpi_data_for_db.append((
                    segment_id,
                    current_timestamp,
                    vehicle_type_prefix,
                    'vehicle_count',
                    row[f'{vehicle_type_prefix}_vehicle_count']
                ))
                # Average Speed
                kpi_data_for_db.append((
                    segment_id,
                    current_timestamp,
                    vehicle_type_prefix,
                    'average_speed',
                    row[f'{vehicle_type_prefix}_average_speed']
                ))
        
        if not kpi_data_for_db:
            print(f"No KPI data to load for {current_timestamp}.")
            return

        insert_query = sql.SQL("""
            INSERT INTO traffic_kpis (segment_id, measurement_timestamp, vehicle_type, kpi_type, kpi_value)
            VALUES %s
            ON CONFLICT (segment_id, measurement_timestamp, vehicle_type, kpi_type) DO UPDATE SET kpi_value = EXCLUDED.kpi_value
        """)

        try:
            execute_values(self.cursor, insert_query, kpi_data_for_db)
            self.conn.commit()
            print(f"✨ Successfully loaded {len(kpi_data_for_db)} KPI records for {current_timestamp}.")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error loading KPIs for {current_timestamp}: {e}")
            raise # Re-raise to indicate failure
    
    def timestamp_exists(self, timestamp):
        query = """
            SELECT 1 FROM traffic_kpis WHERE measurement_timestamp = %s LIMIT 1
        """
        self.cursor.execute(query, (timestamp,))
        return self.cursor.fetchone() is not None

    def process_and_load_to_db(self, df_enriched: pd.DataFrame):
        """
        Orchestrates the entire process: matching, aggregating, and loading to DB.

        Args:
            df_enriched (pd.DataFrame): The enriched KPI DataFrame from the enricher.
        """
        print("\n=== Starting OSM Matching and DB Loading Process ===")
        try:
            self._connect_db()
            self.load_osm_network() # Load OSM network once

            unique_timestamps = sorted(df_enriched['timestamp_combined'].unique())
            print(f"Processing {len(unique_timestamps)} unique timestamps.")

            for i, ts in enumerate(unique_timestamps):
                print(f"\nProcessing timestamp {i+1}/{len(unique_timestamps)}: {ts}")
                if self.timestamp_exists(ts):
                    print(f"Data for timestamp {ts} already exists. Skipping.")
                    continue
                
                df_single_timestamp = df_enriched[df_enriched['timestamp_combined'] == ts].copy()
                if df_single_timestamp.empty:
                    print(f"No data for timestamp {ts}. Skipping.")
                    continue

                # 1. Match detectors to segments for this timestamp
                gdf_matched = self.match_detectors_to_segments(df_single_timestamp)

                if gdf_matched.empty:
                    print(f"No segments matched for timestamp {ts}. Skipping KPI aggregation and loading.")
                    continue

                # 2. Aggregate KPIs by road segment
                gdf_aggregated = self.aggregate_kpi_by_osm_segment(gdf_matched)

                if gdf_aggregated.empty:
                    print(f"No aggregated KPIs for timestamp {ts}. Skipping KPI loading.")
                    continue

                # 3. Insert/Get segment_ids and prepare for KPI loading
                # Need to add segment_id to gdf_aggregated
                segment_ids = []
                for _, row in gdf_aggregated.iterrows():
                    segment_id = self._insert_road_segment_if_not_exists(row['geometry'], row['name_road_segment'])
                    segment_ids.append(segment_id)
                gdf_aggregated['segment_id'] = segment_ids

                # 4. Load KPIs for this timestamp into the database
                self._load_kpis_for_timestamp(gdf_aggregated, ts)

        except Exception as e:
            print(f"Overall OSM matching and DB loading failed: {e}")
            raise # Re-raise to indicate failure
        finally:
            self._close_db()
        print("\n=== OSM Matching and DB Loading Process Complete ===")


# Example Usage (for testing purposes, not part of the main ETL orchestration script yet)
if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    # Database connection configuration
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "berlin_traffic_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD")
    }

    if DB_CONFIG["password"] is None:
        print("❌ Error: DB_PASSWORD environment variable not set. Please create a .env file or set the variable.")
        exit(1)

    # --- Simulate previous ETL steps to get df_enriched ---
    from kpi_loader import TrafficKPILoader
    from enricher import TrafficDataEnricher

    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "src", "data", "raw", "2024")

    det_file_paths = [
        os.path.join(RAW_DATA_DIR, f"det_val_hr_2024_{str(month).zfill(2)}.csv.gz")
        for month in range(1, 13)
    ]

    print("\n--- Running KPI Loader ---")
    loader = TrafficKPILoader(file_paths=det_file_paths)
    df_kpi_raw = loader.load()

    print("\n--- Running Enricher ---")
    enricher = TrafficDataEnricher(df_kpi=df_kpi_raw, db_config=DB_CONFIG)
    df_enriched = enricher.enrich()
    # --- End Simulate previous ETL steps ---

    # Initialize and run the StreetMatcher with DB loading
    matcher = StreetMatcher(db_config=DB_CONFIG)
    matcher.process_and_load_to_db(df_enriched)

    print("\nOSM Matcher and DB Loading Example Complete.")