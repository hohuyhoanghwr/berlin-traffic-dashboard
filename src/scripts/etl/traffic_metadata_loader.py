# src/scripts/etl/traffic_metadata_loader.py

import pandas as pd
import os
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from dotenv import load_dotenv

class TrafficMetadataLoader:
    """
    Loads static detector metadata from the Excel file (Stammdaten_Verkehrsdetektion_2022_07_20.xlsx)
    into the 'detector_metadata' table in PostgreSQL.
    """
    def __init__(self, excel_path: str, db_config: dict):
        """
        Initializes the TrafficMetadataLoader.

        Args:
            excel_path (str): Full path to the metadata Excel file.
            db_config (dict): Dictionary containing database connection parameters
                              (host, port, database, user, password).
        """
        self.excel_path = excel_path
        self.db_config = db_config
        self.conn = None
        self.cursor = None

    def _connect_db(self):
        """Establishes a connection to the PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            print("✅ Database connection established successfully.")
        except Exception as e:
            print(f"❌ Error connecting to database: {e}")
            self.conn = None # Ensure conn is None if connection fails
            self.cursor = None
            raise # Re-raise the exception to stop execution if connection fails

    def _close_db(self):
        """Closes the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

    def load_det_metadata(self):
        """
        Loads data from the 'Stammdaten_TEU_20220720' sheet (DET data)
        and inserts it into the 'detector_metadata' table.
        """
        print("\n--- Loading Detector Metadata ---")
        try:
            # Read the specific sheet
            df_det = pd.read_excel(self.excel_path, sheet_name="Stammdaten_TEU_20220720")
            
            # Rename columns to match database schema
            df_det = df_det.rename(columns={
                "DET_ID15": "det_id15",
                "SPUR": "lane",
                "STRASSE": "street_name",
                "LÄNGE (WGS84)": "lon",
                "BREITE (WGS84)": "lat"
            })

            # Select only the columns relevant for the detector_metadata table
            # Ensure the order matches the INSERT statement
            df_det = df_det[['det_id15', 'lane', 'street_name', 'lon', 'lat']]

            # Convert DataFrame to a list of tuples for batch insertion
            records = [tuple(row) for row in df_det.to_numpy()]

            # SQL query for insertion - UPDATED to include new columns
            insert_query = sql.SQL("INSERT INTO detector_metadata (det_id15, lane, street_name, lon, lat) VALUES %s ON CONFLICT (det_id15) DO NOTHING")

            # Use execute_values for efficient batch insertion
            execute_values(self.cursor, insert_query, records)
            self.conn.commit()
            print(f"✨ Successfully inserted/skipped {len(records)} records into detector_metadata.")
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Error loading detector metadata: {e}")
            raise # Re-raise to indicate failure

    def run(self):
        """Orchestrates the metadata loading process."""
        try:
            self._connect_db()
            self.load_det_metadata() # Only load detector metadata
        except Exception as e:
            print(f"Overall metadata loading failed: {e}")
        finally:
            self._close_db()

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    # Define the path to your metadata Excel file
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    METADATA_EXCEL_PATH = os.path.join(PROJECT_ROOT, "src", "data", "raw", "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx")

    # Database connection configuration
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "berlin_traffic_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD")
    }

    # IMPORTANT: Check if password is loaded
    if DB_CONFIG["password"] is None:
        print("❌ Error: DB_PASSWORD environment variable not set. Please create a .env file or set the variable.")
        exit(1)

    # Initialize and run the loader
    loader = TrafficMetadataLoader(excel_path=METADATA_EXCEL_PATH, db_config=DB_CONFIG)
    loader.run()
