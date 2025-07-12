# # scripts/traffic_map_builder.py

# import pandas as pd
# import folium
# from pyproj import Transformer
# import branca.colormap as cm

# class TrafficMapBuilder:
#     def __init__(self, excel_path: str):
#         self.excel_path = excel_path
#         self.df_mq = None
#         self.folium_map = None

#     def load_excel_metadata(self, sheet_name: str = "Stammdaten_TEU_20220720"):
#         df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
#         df = df.dropna(subset=["LÄNGE (WGS84)", "BREITE (WGS84)"])
#         df["lon"] = df["LÄNGE (WGS84)"]
#         df["lat"] = df["BREITE (WGS84)"]
#         self.df_mq = df

#     def build_folium_map(self, zoom_start: int = 11, center=None, show_detectors: bool = False):
#         if self.df_mq is None:
#             self.load_excel_metadata()
        
#         if center is None:
#             lat_center = self.df_mq["lat"].mean()
#             lon_center = self.df_mq["lon"].mean()
#             center = [lat_center, lon_center]

#         m = folium.Map(location=center, zoom_start=zoom_start, tiles="CartoDB positron")

#         # Optional: plot detector points
#         if show_detectors:
#             for _, row in self.df_mq.iterrows():
#                 tooltip = f"{row['DET_ID15']}<br>{row['STRASSE']}<br>{row['RICHTUNG']}"
#                 folium.CircleMarker(
#                     location=[row["lat"], row["lon"]],
#                     radius=1,
#                     color="blue",
#                     fill=True,
#                     fill_opacity=0.6,
#                     tooltip=tooltip
#                 ).add_to(m)

#         self.folium_map = m
#         return m
    
#     def add_street_layer(self, gdf_road_kpi, value_col="q_kfz_det_hr_avg"):
#         import branca.colormap as cm

#         if "geometry" not in gdf_road_kpi.columns:
#             raise ValueError("GeoDataFrame must contain a 'geometry' column with LineString.")

#         # Color scale
#         min_val = gdf_road_kpi[value_col].min()
#         max_val = gdf_road_kpi[value_col].max()
#         colormap = cm.linear.YlOrRd_09.scale(min_val, max_val)
        
#          # Add styling columns
#         gdf_road_kpi["color"] = gdf_road_kpi[value_col].apply(colormap)
#         gdf_road_kpi["tooltip_text"] = gdf_road_kpi.apply(
#             lambda row: f'{row.get("name_road_segment", "Unnamed Street")}<br>'
#             f'{value_col}: {row[value_col]:.0f}',
#             axis=1
#             )

#         # Define style function for GeoJson
#         def style_function(feature):
#             return {
#             "color": feature["properties"]["color"],
#             "weight": 5,
#             "opacity": 0.8
#             }
            
#         # Define tooltip field
#         tooltip = folium.GeoJsonTooltip(fields=["tooltip_text"], aliases=[""])

#         # One big GeoJson
#         folium.GeoJson(
#         data=gdf_road_kpi.__geo_interface__,
#         style_function=style_function,
#         tooltip=tooltip
#         ).add_to(self.folium_map)

#         colormap.caption = f"{value_col} scale"
#         colormap.add_to(self.folium_map)