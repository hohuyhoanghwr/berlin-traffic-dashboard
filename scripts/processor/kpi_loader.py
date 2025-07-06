import pandas as pd


class TrafficKPILoader:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        
    def _clean(self):
        self.df = self.df[self.df["qualitaet"] >= 0.75]
        self.df["tag"] = pd.to_datetime(self.df["tag"], format="%d.%m.%Y")
        self.df["hour"] = self.df["stunde"]
        self.df.drop(columns=["stunde"], inplace=True)

    def load(self) -> pd.DataFrame:
        self.df = pd.read_csv(self.csv_path, sep=';')
        self._clean()
        return self.df