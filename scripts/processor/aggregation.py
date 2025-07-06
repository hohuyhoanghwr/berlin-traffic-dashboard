import pandas as pd

# def aggregate_kpi_by_segment(df: pd.DataFrame, value_col="q_kfz_det_hr") -> pd.DataFrame:
#     # Group by street, direction, time
#     grouped = df.groupby(["STRASSE", "RICHTUNG", "tag", "hour"])[value_col].mean().reset_index()
#     grouped = grouped.rename(columns={value_col: f"{value_col}_avg"})

#     # Merge back to original enriched data (broadcast KPI to all matching detectors)
#     df = pd.merge(
#         df,
#         grouped,
#         on=["STRASSE", "RICHTUNG", "tag", "hour"],
#         how="left"
#     )
#     return df