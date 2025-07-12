# src/scripts/processor/enricher.py

import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import os

class TrafficDataEnricher:
    """
    Enriches raw traffic KPI data with detector metadata fetched from PostgreSQL.
    """
    def __init__(self, df_kpi: pd.DataFrame, db_config: dict):
        """
        Initializes the TrafficDataEnricher.

        Args:
            df_kpi (pd.DataFrame): The raw KPI DataFrame (output from kpi_loader).
            db_config (dict): Dictionary containing database connection parameters.
        """
        self.df_kpi = df_kpi
        self.db_config = db_config
        self.df_metadata = None
        self.df_enriched = None
        self.conn = None
        self.cursor = None

    def _connect_db(self):
        """Establishes a connection to the PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            print("✅ Database connection established for enricher.")
        except Exception as e:
            print(f"❌ Error connecting to database for enricher: {e}")
            self.conn = None
            self.cursor = None
            raise # Re-raise the exception to stop execution

    def _close_db(self):
        """Closes the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed for enricher.")

    def _load_metadata_from_db(self):
        """
        Loads detector metadata from the 'detector_metadata' table in PostgreSQL.
        """
        print("--- Loading Detector Metadata from Database ---")
        try:
            # SQL query to select all columns from detector_metadata
            select_query = sql.SQL("SELECT det_id15, lane, street_name, lon, lat FROM detector_metadata")
            self.cursor.execute(select_query)
            
            # Fetch all rows and column names
            columns = [desc[0] for desc in self.cursor.description]
            data = self.cursor.fetchall()
            
            self.df_metadata = pd.DataFrame(data, columns=columns)
            self.df_metadata = self.df_metadata.rename(columns={"det_id15": "detid_15"})
            print(f"✨ Successfully loaded {len(self.df_metadata)} records from detector_metadata.")
        except Exception as e:
            print(f"❌ Error loading detector metadata from DB: {e}")
            raise # Re-raise to indicate failure

    def enrich(self) -> pd.DataFrame:
        """
        Enriches the KPI DataFrame by joining with detector metadata.
        """
        print("\n--- Enriching KPI Data ---")
        try:
            self._connect_db() # Connect to DB
            self._load_metadata_from_db() # Load metadata from DB

            if self.df_metadata is None or self.df_metadata.empty:
                print("❌ No detector metadata loaded. Cannot enrich KPI data.")
                return self.df_kpi # Return original if no metadata

            # Join by detector ID
            # Ensure detid_15 in df_kpi is of the same type as in df_metadata (e.g., string)
            self.df_kpi['detid_15'] = self.df_kpi['detid_15'].astype(str)
            self.df_enriched = pd.merge(self.df_kpi, self.df_metadata, on="detid_15", how="left")

            # Drop any detectors with no location (if any remain after join)
            # The metadata should now provide lon/lat for all det_id15
            self.df_enriched = self.df_enriched.dropna(subset=["lon", "lat"])

            print(f"✨ KPI data enriched. Total records: {len(self.df_enriched)}")
            return self.df_enriched
        except Exception as e:
            print(f"Overall data enrichment failed: {e}")
            raise # Re-raise to indicate failure
        finally:
            self._close_db() # Close DB connection

# Example Usage (for testing purposes, not part of the main ETL flow)
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

    # Simulate loading raw KPI data (e.g., from kpi_loader.py)
    # In a real ETL pipeline, this would come from the kpi_loader
    from kpi_loader import TrafficKPILoader

    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "src", "data", "raw", "2024")

    det_file_paths = [
        os.path.join(RAW_DATA_DIR, f"det_val_hr_2024_{str(month).zfill(2)}.csv.gz")
        for month in range(1, 13)
    ]

    loader = TrafficKPILoader(file_paths=det_file_paths)
    df_kpi_raw = loader.load()

    # Initialize and run the enricher
    enricher = TrafficDataEnricher(df_kpi=df_kpi_raw, db_config=DB_CONFIG)
    df_enriched = enricher.enrich()

    print("\nEnriched Data Head:")
    print(df_enriched.head())
    print("\nEnriched Data Info:")
    print(df_enriched.info())
    print("\nColumns after enrichment:")
    print(df_enriched.columns)
