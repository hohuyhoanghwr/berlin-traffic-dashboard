# src/scripts/processor/kpi_loader.py

import pandas as pd
import os
import gzip # Import gzip for handling .gz files

class TrafficKPILoader:
    """
    Loads and cleans raw traffic KPI data from detector files (det_val_hr_YYYY_MM.csv.gz).
    """
    def __init__(self, file_paths: list[str]):
        """
        Initializes the TrafficKPILoader.

        Args:
            file_paths (list[str]): A list of full paths to the raw det_val_hr_YYYY_MM.csv.gz files.
        """
        self.file_paths = file_paths
        self.df = None

    def _clean(self):
        """
        Performs cleaning and initial transformation on the loaded DataFrame.
        - Converts 'tag' to datetime.
        - Renames 'stunde' to 'hour'.
        - Filters data quality (optional, currently commented out as per previous versions).
        """
        # Ensure 'tag' is datetime
        if not pd.api.types.is_datetime64_any_dtype(self.df['tag']):
            self.df['tag'] = pd.to_datetime(self.df['tag'], format="%d.%m.%Y")

        # Rename 'stunde' to 'hour' for consistency
        if 'stunde' in self.df.columns:
            self.df['hour'] = self.df['stunde']
            self.df.drop(columns=['stunde'], inplace=True)

        # Create a combined timestamp column for easier processing later
        # This will be used to form the `measurement_timestamp` in the database
        self.df['timestamp_combined'] = self.df.apply(
            lambda row: row['tag'].replace(hour=int(row['hour'])), axis=1
        )

        # Filter by quality if desired (currently commented out)
        # self.df = self.df[self.df["qualitaet"] >= 0.75]

    def load(self) -> pd.DataFrame:
        """
        Loads data from all specified .csv.gz files, concatenates them, and cleans.

        Returns:
            pd.DataFrame: A concatenated and cleaned DataFrame containing all raw KPI data.
        """
        all_dfs = []
        print(f"\n--- Loading and cleaning {len(self.file_paths)} raw DET data files ---")
        for file_path in self.file_paths:
            if not os.path.exists(file_path):
                print(f"⚠️ Warning: File not found: {file_path}. Skipping.")
                continue

            print(f"Processing: {os.path.basename(file_path)}")
            try:
                # Open the gzipped file and read as CSV
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    df_single = pd.read_csv(f, sep=';')
                    all_dfs.append(df_single)
            except Exception as e:
                print(f"❌ Error reading {os.path.basename(file_path)}: {e}. Skipping.")

        if not all_dfs:
            print("❌ No data loaded from any files. Returning empty DataFrame.")
            return pd.DataFrame()

        self.df = pd.concat(all_dfs, ignore_index=True)
        self._clean()
        print("--- Raw DET data loading complete ---")
        return self.df

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Define the directory where your downloaded det_val_hr files are
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "src", "data", "raw", "2024")

    # Get all det_val_hr files for 2024
    det_file_paths = [
        os.path.join(RAW_DATA_DIR, f"det_val_hr_2024_{str(month).zfill(2)}.csv.gz")
        for month in range(1, 13)
    ]

    loader = TrafficKPILoader(file_paths=det_file_paths)
    df_kpi_raw = loader.load()
        
    print("\nLoaded KPI Data Head:")
    print(df_kpi_raw.head())
    print("\nLoaded KPI Data Info:")
    print(df_kpi_raw.info())
    print("\nUnique timestamps (first 5):")
    print(df_kpi_raw['timestamp_combined'].unique()[:5])
