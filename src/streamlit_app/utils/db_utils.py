# src/streamlit_app/utils/db_utils.py

import os
import pandas as pd
import geopandas as gpd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import streamlit as st
from sqlalchemy import create_engine

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

# Check if password is loaded (essential for local development)
if DB_CONFIG["password"] is None:
    st.error("Database password not set. Please ensure DB_PASSWORD is in your .env file.")
    st.stop() # Stop Streamlit app execution if credentials are missing

@st.cache_resource # Cache the database connection itself
def get_db_connection():
    """
    Establishes and caches a connection to the PostgreSQL database.
    Uses st.cache_resource to ensure the connection is reused across reruns.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Streamlit: Database connection established.") # For debugging in console
        return conn
    except Exception as e:
        st.error(f"❌ Streamlit: Error connecting to database: {e}")
        st.stop() # Stop app if connection fails
        return None

@st.cache_data(ttl=3600) # Cache data for 1 hour
def fetch_road_segments() -> gpd.GeoDataFrame:
    """
    Fetches all unique road segments from the 'road_segments' table.
    Caches the result to avoid re-fetching on every rerun.
    """
    conn = get_db_connection()
    if conn is None:
        return gpd.GeoDataFrame() # Return empty if no connection
    
    # Build the connection string
    db_url = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)
    engine = create_engine(db_url)
    

    print("Fetching road segments from DB...") # For debugging in console
    try:
        # Use gpd.read_postgis for direct GeoDataFrame loading
        # Ensure 'geometry' column is correctly handled by PostGIS
        gdf_segments = gpd.read_postgis(
            "SELECT segment_id, name_road_segment, geometry FROM road_segments",
            engine,
            geom_col='geometry',
            crs="EPSG:4326" # Specify the CRS of the geometry column in the DB
        )
        print(f"✨ Fetched {len(gdf_segments)} road segments.")
        return gdf_segments
    except Exception as e:
        st.error(f"❌ Error fetching road segments: {e}")
        return gpd.GeoDataFrame()
    finally:
        # Do NOT close the connection here if using st.cache_resource,
        # as it will be managed by Streamlit's caching mechanism.
        pass

@st.cache_data(ttl=600) # Cache data for 10 minutes (KPIs might update more frequently)
def fetch_kpi_data(
    segment_ids: list[int],
    selected_date: pd.Timestamp,
    selected_hour: int,
    kpi_type: str,
    vehicle_type: str
) -> pd.DataFrame:
    """
    Fetches aggregated KPI data for specific segments, date, hour, KPI type, and vehicle type.
    """
    conn = get_db_connection()
    print("DB connection:", conn)
    if conn is None:
        print("No DB connection, returning empty DataFrame")
        return pd.DataFrame()

    print(f"Fetching KPI data for {selected_date.date()} {selected_hour:02d}:00, KPI: {kpi_type}, Vehicle: {vehicle_type}...") # For debugging
    try:
        print("About to create cursor...")
        try:
            with conn.cursor() as test_cursor:
                test_cursor.execute("SELECT 1")
        except psycopg2.InterfaceError:
            print("⚠️ Streamlit: Cached database connection is stale, attempting to reconnect.")
            # If the connection is stale, clear the cache and get a new one
            get_db_connection.clear()
            conn = get_db_connection()
            if conn is None:
                print("❌ Streamlit: Failed to reconnect to the database. Returning empty DataFrame.")
                return pd.DataFrame()
            # Construct the timestamp for the query
        with conn.cursor() as cursor:
            print('created cursor, now preparing query...')
            dt = selected_date.replace(hour=selected_hour, minute=0, second=0, microsecond=0)
            if dt.tzinfo is None:
                query_timestamp = dt.tz_localize('UTC')
            else:
                query_timestamp = dt.tz_convert('UTC')

            # Use IN clause for segment_ids for efficiency
            # Use sql.SQL and sql.Literal to safely parameterize the query
            query = sql.SQL("""
                SELECT segment_id, kpi_value
                FROM traffic_kpis
                WHERE segment_id = ANY(%s)
                  AND measurement_timestamp = %s
                  AND kpi_type = %s
                  AND vehicle_type = %s
            """)
            
            cursor.execute(query, (segment_ids, query_timestamp, kpi_type, vehicle_type))
            print("Query executed, fetching results...")
            
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            df_kpis = pd.DataFrame(data, columns=columns)
            print(f"✨ Fetched {len(df_kpis)} KPI records.")
            return df_kpis
    except Exception as e:
        st.error(f"❌ Error fetching KPI data: {e}")
        return pd.DataFrame()
    finally:
        pass # Connection managed by st.cache_resource

# Example usage (for testing, not part of the main app flow)
if __name__ == "__main__":
    # This block won't run directly in Streamlit, but can be used for local testing
    print("--- Testing db_utils.py functions ---")
    
    # Test connection
    conn = get_db_connection()
    if conn:
        print("Connection test successful.")
        conn.close() # Close connection for this test run

    # Test fetching road segments
    segments_gdf = fetch_road_segments()
    print("\nRoad Segments Head:")
    print(segments_gdf.head())
    print("\nRoad Segments Info:")
    print(segments_gdf.info())

    # Test fetching KPI data (using a dummy date and hour)
    if not segments_gdf.empty:
        sample_segment_ids = segments_gdf['segment_id'].head(5).tolist()
        # Use a timestamp that you know exists in your data
        test_date = pd.Timestamp('2024-01-01') # Adjust to a date in your loaded data
        test_hour = 0 # Adjust to an hour in your loaded data
        test_kpi_type = 'vehicle_count'
        test_vehicle_type = 'all'

        kpis_df = fetch_kpi_data(sample_segment_ids, test_date, test_hour, test_kpi_type, test_vehicle_type)
        print("\nSample KPI Data Head:")
        print(kpis_df.head())
        print("\nSample KPI Data Info:")
        print(kpis_df.info())
    else:
        print("No road segments to test KPI fetching.")

    print("\n--- db_utils.py testing complete ---")
