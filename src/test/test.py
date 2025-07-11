import pandas as pd
df = pd.read_excel(r"D:\Study\HWR Berlin\Semester 2\Enterprise Architecture for Big Data\0. Big Data Group Project\Git\berlin-traffic-dashboard\data\raw\Stammdaten_Verkehrsdetektion_2022_07_20.xlsx", sheet_name="Stammdaten_TEU_20220720")
print(df.info())
print(df.head())