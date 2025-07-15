import pandas as pd
import os
from kpi_loader import TrafficKPILoader


class TrafficDataEnricher:
    def __init__(self, df_kpi: pd.DataFrame, metadata_path: str, sheet: str = "Stammdaten_TEU_20220720"):
        self.df_kpi = df_kpi
        self.metadata_path = metadata_path
        self.sheet = sheet
        self.df_metadata = None
        self.df_enriched = None
        
    def _load_metadata(self):
        self.df_metadata = pd.read_excel(self.metadata_path, sheet_name=self.sheet)

    def enrich(self) -> pd.DataFrame:
        self._load_metadata()

        # Join by detector ID
        self.df_metadata = self.df_metadata.rename(columns={"DET_ID15": "detid_15"})
        self.df_enriched = pd.merge(self.df_kpi, self.df_metadata, on="detid_15", how="left")

        # Drop any detectors with no location
        self.df_enriched = self.df_enriched.dropna(subset=["LÄNGE (WGS84)", "BREITE (WGS84)"])
        self.df_enriched["lon"] = self.df_enriched["LÄNGE (WGS84)"]
        self.df_enriched["lat"] = self.df_enriched["BREITE (WGS84)"]

        return self.df_enriched

def main():
    ROOT_DIR = os.path.abspath(os.path.join(os.getcwd(), "......",))
    metadata_path = os.path.join(ROOT_DIR, "src", "data", "raw", "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx")
    kpi_path = os.path.join(ROOT_DIR, "src", "data", "raw", "2024", "det_val_hr_2024_12.csv.gz")

    df_kpi = TrafficKPILoader(kpi_path).load()
    enricher = TrafficDataEnricher(df_kpi, metadata_path)
    enriched_df = enricher.enrich()
    
    print(enriched_df.info())
    print(enriched_df.head())
    
    enriched_df.to_parquet(os.path.join(ROOT_DIR, "src", "data", "processed", "kpi_enriched_dec_2024.parquet"), index=False)
    
if __name__ == "__main__":
    main()