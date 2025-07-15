import os
import pandas as pd
import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point


class StreetMatcher:
    def __init__(self, network_place="Berlin, Germany", cache_path=None):
        if cache_path is None:
            # Always resolve path relative to the project root
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cache_path = os.path.abspath(
                os.path.join(script_dir, "..", "..", "data", "osm", "berlin_drive.graphml")
            )
        self.network_place = network_place
        self.cache_path = cache_path
        self.osm_edges = None

    def load_osm_network(self):
        if os.path.exists(self.cache_path):
            print("📂 Loading cached Berlin road network...")
            G = ox.load_graphml(self.cache_path)
        else:
            print("🌐 Downloading Berlin road network from OpenStreetMap...")
            G = ox.graph_from_place(self.network_place, network_type='drive')
            ox.save_graphml(G, filepath=self.cache_path)

        self.osm_edges = ox.graph_to_gdfs(G, nodes=False)
        self.osm_edges = self.osm_edges[self.osm_edges["geometry"].notnull()]
        self.osm_edges.reset_index(drop=True, inplace=True)
        self.osm_edges["osm_id_index"] = self.osm_edges.index

    def _to_geo(self, df: pd.DataFrame, lon_col="lon", lat_col="lat") -> gpd.GeoDataFrame:
        gdf = gpd.GeoDataFrame(
            df.copy(),
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326"
        )
        return gdf

    def match_detectors_to_segments(self, df_enriched: pd.DataFrame) -> gpd.GeoDataFrame:
        if self.osm_edges is None:
            self.load_osm_network()

        gdf_detectors = self._to_geo(df_enriched)

        # Reproject both to EPSG:32633 for proper spatial matching
        crs_proj = "EPSG:32633"
        gdf_detectors_proj = gdf_detectors.to_crs(crs_proj)
        osm_edges_proj = self.osm_edges.to_crs(crs_proj)

        # Spatial join using projected CRS
        self.gdf_matched = gpd.sjoin_nearest(
            gdf_detectors_proj,
            osm_edges_proj,
            how="left",
            distance_col="dist_to_road"
        )
        
        # Join with OSM edge geometries (to get LINESTRING)
        gdf_road_kpi = self.gdf_matched.merge(
            self.osm_edges,  # contains geometry
            left_on="index_right",
            right_on="osm_id_index",
            how="left",
            suffixes=('_detector', '_road_segment') # Add suffixes to differentiate geometry columns
            )
        
        def flatten_name_field(value):
            if isinstance(value, list):
                # Drop duplicates and join as comma-separated
                return ", ".join(sorted(set(map(str, value))))
            return str(value) if pd.notnull(value) else None
        
        gdf_road_kpi["name_road_segment"] = gdf_road_kpi["name_road_segment"].fillna(gdf_road_kpi["STRASSE"])
        gdf_road_kpi["name_road_segment"] = gdf_road_kpi["name_road_segment"].apply(flatten_name_field)
        
        # Keep only relevant columns and rename geometry
        gdf_road_kpi = gdf_road_kpi.rename(columns={'geometry_road_segment': 'geometry'})
        gdf_road_kpi = gdf_road_kpi[["geometry","name_road_segment"] + [col for col in df_enriched.columns if col.startswith(('q_', 'v_'))]].copy()
        gdf_road_kpi = gdf_road_kpi.to_crs("EPSG:4326")  # Back to WGS84

        # Return in original CRS for compatibility with Folium (WGS84)
        return gdf_road_kpi

    def aggregate_kpi_by_osm_segment(self, gdf_matched: gpd.GeoDataFrame, kpi_col: str) -> gpd.GeoDataFrame:
        if kpi_col not in gdf_matched.columns:
            raise ValueError(f"KPI column '{kpi_col}' not found in the matched GeoDataFrame for aggregation.")
        grouped = gdf_matched.groupby(["geometry","name_road_segment"])[kpi_col].mean().reset_index()
        grouped_gdf = gpd.GeoDataFrame(grouped, geometry="geometry", crs="EPSG:4326")
        grouped_gdf = grouped_gdf.rename(columns={kpi_col: "value"})
        return grouped_gdf