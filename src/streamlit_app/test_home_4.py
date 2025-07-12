# src/streamlit_app/Home.py

import streamlit as st
import pandas as pd
import geopandas as gpd
import json
import os
import sys
import time # For potential sleep in rerun loop
from datetime import date, timedelta # For date range validation
# Removed branca.colormap as it's not directly used for JS color calculation anymore

# Add the project root to the sys.path to allow imports from utils
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(PROJECT_ROOT)

# Import functions from your db_utils.py
from src.streamlit_app.utils.db_utils import get_db_connection, fetch_road_segments, fetch_kpi_data

# --- UI setup ---
st.set_page_config(page_title="Berlin Traffic Map", layout="wide")
st.title("🛣️ Berlin Traffic Dashboard")

# --- Data Loading (from Database) ---

# Load road segments (static map base) - This is cached and loaded once
@st.cache_data(show_spinner="Loading road segments from database...")
def load_road_segments_cached():
    """Loads road segments using db_utils."""
    return fetch_road_segments()

road_segments_gdf = load_road_segments_cached()

if road_segments_gdf.empty:
    st.error("Could not load road segments from the database. Please ensure your ETL pipeline has run successfully.")
    st.stop()

# Get unique timestamps for animation range
@st.cache_data(ttl=3600, show_spinner="Fetching all available timestamps from DB...")
def get_all_available_timestamps():
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT measurement_timestamp FROM traffic_kpis ORDER BY measurement_timestamp")
            timestamps = [ts[0] for ts in cursor.fetchall()]
            # Convert to pandas Timestamps and sort
            return sorted(list(set(pd.to_datetime(timestamps))))
    except Exception as e:
        st.error(f"Error fetching all available timestamps: {e}")
        return []

all_available_timestamps = get_all_available_timestamps()

if not all_available_timestamps:
    st.warning("No traffic KPI data found in the database. Please run your ETL pipeline to populate 'traffic_kpis'.")
    st.stop()

# Extract min/max dates from available timestamps for date picker limits
min_available_date = all_available_timestamps[0].date()
max_available_date = all_available_timestamps[-1].date()

# --- Sidebar Filters ---
st.sidebar.header("Data Filters")

kpi_options = {
    "Vehicle Count": "vehicle_count",
    "Average Speed (km/h)": "average_speed"
}
selected_kpi_display = st.sidebar.selectbox(
    "Select KPI",
    options=list(kpi_options.keys()),
    key="kpi_selector"
)
selected_kpi_type = kpi_options[selected_kpi_display]

vehicle_options = {
    "All Vehicles": "all",
    "Passenger Cars": "cars",
    "Trucks": "trucks"
}
selected_vehicle_display = st.sidebar.selectbox(
    "Select Vehicle Type",
    options=list(vehicle_options.keys()),
    key="vehicle_selector"
)
selected_vehicle_type = vehicle_options[selected_vehicle_display]

st.sidebar.markdown("---")
st.sidebar.header("Time Range Selection (Max 1 Month)")

# Default to the latest month available
default_start_date = (max_available_date - timedelta(days=29)) if (max_available_date - timedelta(days=29)) >= min_available_date else min_available_date
default_end_date = max_available_date

start_date_selection = st.sidebar.date_input(
    "Start Date",
    value=default_start_date,
    min_value=min_available_date,
    max_value=max_available_date,
    key="start_date_selector"
)

end_date_selection = st.sidebar.date_input(
    "End Date",
    value=default_end_date,
    min_value=min_available_date,
    max_value=max_available_date,
    key="end_date_selector"
)

# Validate date range
if end_date_selection < start_date_selection:
    st.sidebar.error("End date cannot be before start date.")
    st.stop()

if (end_date_selection - start_date_selection).days > 30: # Max 1 month (approx 30 days)
    st.sidebar.error("Date range cannot exceed 1 month (approx. 30 days).")
    st.stop()

# Filter available timestamps based on selected date range
filtered_timestamps = [
    ts for ts in all_available_timestamps
    if start_date_selection <= ts.date() <= end_date_selection
]

if not filtered_timestamps:
    st.warning("No data available for the selected date range. Please adjust your dates.")
    st.stop()

# --- Animation Speed Slider (appears before Load Map button) ---
st.sidebar.markdown("---")
st.sidebar.header("Animation Speed")

animation_speed = st.sidebar.slider(
    "Speed (seconds per frame)",
    min_value=0.1,
    max_value=3.0,
    value=0.5, # Default speed
    step=0.1,
    key="animation_speed_slider"
)

# --- Load ALL KPI data for the selected filters and date range ---
# Moved outside the conditional block so it's always defined and can be cleared
@st.cache_data(show_spinner=f"Preparing data for animation ({selected_kpi_display}, {selected_vehicle_type}, {start_date_selection} to {end_date_selection})...")
def fetch_all_kpi_snapshots(
    _road_segments_gdf: gpd.GeoDataFrame, # Renamed to _road_segments_gdf to prevent hashing
    available_timestamps_in_range: list[pd.Timestamp],
    kpi_type: str,
    vehicle_type: str,
    kpi_display_name: str # Pass display name to determine color scale
) -> dict:
    """
    Fetches KPI data for all available timestamps within the given range and merges with road segments,
    then converts to a dictionary of GeoJSON objects for client-side animation.
    """
    all_geojson_data = {}
    total_timestamps = len(available_timestamps_in_range)
    
    _road_segments_gdf['segment_id'] = _road_segments_gdf['segment_id'].astype(int)

    # Define legend ranges for JS based on KPI type (still useful for the legend)
    legend_ranges = []
    if kpi_type == "vehicle_count":
        legend_ranges = [
            {'value': '2000+', 'color': '#A50026'}, # Dark Red
            {'value': '1001-2000', 'color': '#D73027'}, # Red
            {'value': '501-1000', 'color': '#F46D43'}, # Orange-Red
            {'value': '201-500', 'color': '#FDAE61'}, # Orange
            {'value': '101-200', 'color': '#FEE08B'}, # Light Orange
            {'value': '51-100', 'color': '#D9EF8B'}, # Yellow-Green
            {'value': '21-50', 'color': '#A6D96A'}, # Light Green
            {'value': '0-20', 'color': '#66BD63'}  # Dark Green (for lowest values)
        ]
    elif kpi_type == "average_speed":
        legend_ranges = [
            {'value': '70+ km/h', 'color': '#1A9850'}, # Dark Green (fast)
            {'value': '61-70 km/h', 'color': '#66BD63'}, # Green
            {'value': '51-60 km/h', 'color': '#A6D96A'}, # Light Green
            {'value': '41-50 km/h', 'color': '#D9EF8B'}, # Yellow-Green
            {'value': '31-40 km/h', 'color': '#FEE08B'}, # Light Orange
            {'value': '21-30 km/h', 'color': '#FDAE61'}, # Orange
            {'value': '1-20 km/h', 'color': '#F46D43'}, # Orange-Red
            {'value': '0 km/h', 'color': '#D73027'} # Red (for 0 or very low speed)
        ]
    else:
        legend_ranges = [{'value': 'N/A', 'color': '#808080'}]


    for i, ts in enumerate(available_timestamps_in_range):
        kpi_df_single_ts = fetch_kpi_data(
            segment_ids=_road_segments_gdf['segment_id'].tolist(),
            selected_date=ts,
            selected_hour=ts.hour,
            kpi_type=kpi_type,
            vehicle_type=vehicle_type
        )
        
        kpi_df_single_ts['segment_id'] = kpi_df_single_ts['segment_id'].astype(int)

        current_map_data_gdf = _road_segments_gdf.merge(kpi_df_single_ts, on='segment_id', how='left')
        
        current_map_data_gdf['kpi_value'] = current_map_data_gdf['kpi_value'].fillna(0)
        current_map_data_gdf['kpi_value'] = current_map_data_gdf['kpi_value'].astype(float)
        
        # DEBUG: Check data after merge and fillna
        # print(f"DEBUG (Python): Data for {ts} after merge and fillna:")
        # print(current_map_data_gdf[['segment_id', 'kpi_value', 'tooltip_content']].head())
        # print(f"DEBUG (Python): kpi_value dtypes after fillna and astype: {current_map_data_gdf['kpi_value'].dtype}")
        # print(f"DEBUG (Python): Sample kpi_values: {current_map_data_gdf['kpi_value'].sample(min(5, len(current_map_data_gdf))).tolist()}")


        if not current_map_data_gdf.geometry.name == 'geometry':
            current_map_data_gdf = current_map_data_gdf.set_geometry('geometry')

        current_map_data_gdf['tooltip_content'] = current_map_data_gdf.apply(
            lambda row: f"<b>Road:</b> {row['name_road_segment']}<br><b>{kpi_display_name}:</b> {row['kpi_value']:.2f}",
            axis=1
        )
        
        geojson_dict = json.loads(current_map_data_gdf.to_json())
        
        # Ensure kpi_value is explicitly set in properties for JS to use
        for feature in geojson_dict['features']:
            segment_id = feature['properties']['segment_id']
            original_row = current_map_data_gdf.loc[current_map_data_gdf['segment_id'] == segment_id].iloc[0]
            feature['properties']['kpi_value'] = original_row['kpi_value']
            feature['properties']['tooltip_content'] = original_row['tooltip_content']
        
        all_geojson_data[ts.strftime("%Y-%m-%d %H:%M:%S")] = geojson_dict
    
    # Store legend ranges in the returned data for JS to use
    all_geojson_data['legend_ranges'] = legend_ranges
    return all_geojson_data


# --- "Load Map" Button ---
st.sidebar.markdown("---")
if st.sidebar.button("Load Map Data & Initialize Map", key="load_map_button"):
    st.session_state["load_triggered"] = True
    st.session_state["auto_playing"] = False # Do NOT auto-play on load, wait for user click
    st.session_state["current_animation_index"] = 0 # Reset animation to start
    # Clear the cache for fetch_all_kpi_snapshots to ensure new data is loaded
    fetch_all_kpi_snapshots.clear() 
    st.rerun() # Trigger a rerun to load data and display map
elif "load_triggered" not in st.session_state:
    st.session_state["load_triggered"] = False # Initialize if not set

# Only proceed with data loading and map rendering if "Load Map" was triggered
if st.session_state["load_triggered"]:
    all_geojson_data_with_legend = fetch_all_kpi_snapshots(
        _road_segments_gdf=road_segments_gdf,
        available_timestamps_in_range=filtered_timestamps,
        kpi_type=selected_kpi_type,
        vehicle_type=selected_vehicle_type,
        kpi_display_name=selected_kpi_display
    )
    # Extract actual GeoJSON data and legend ranges
    legend_ranges_for_js = all_geojson_data_with_legend.pop('legend_ranges')
    all_geojson_data = all_geojson_data_with_legend


    available_times_str = sorted(list(all_geojson_data.keys()))
    if not available_times_str:
        st.error("No valid KPI data prepared for animation in the selected range. Please check your data or filters.")
        st.stop()

    # --- Initialize/Update session state for animation controls ---
    st.session_state["animation_start_index"] = 0
    st.session_state["animation_end_index"] = len(available_times_str) - 1
    st.session_state["animation_speed"] = animation_speed # Use the speed from the slider
    
    if "current_animation_index" not in st.session_state:
        st.session_state["current_animation_index"] = 0
    # auto_playing is already set to False when "Load Map" is clicked

    # --- Generate HTML for the Client-Side Map and Animation ---
    def create_map_html(
        geojson_data_all_times: dict,
        available_times_list: list,
        start_idx: int,
        end_idx: int,
        speed: float,
        initial_current_idx: int,
        initial_zoom: int = 12,
        initial_center: list = [52.52, 13.405],
        auto_play_on_load: bool = False,
        kpi_display_name: str = "KPI Value", # Pass display name for legend
        legend_ranges_data: list = [] # Pass legend ranges directly
    ) -> str:
        geojson_json_str = json.dumps(geojson_data_all_times)
        times_json_str = json.dumps(available_times_list)
        legend_ranges_json_str = json.dumps(legend_ranges_data) # New: pass legend ranges as JSON

        # Re-introducing getColor function into JS
        color_scale_js = ""
        # Use the improved color scales from previous iteration here
        if selected_kpi_type == "vehicle_count": # Use selected_kpi_type from outer scope
            color_scale_js = """
            function getColor(value) {
                return value > 2000 ? '#A50026' : // Dark Red
                       value > 1000  ? '#D73027' : // Red
                       value > 500  ? '#F46D43' : // Orange-Red
                       value > 200  ? '#FDAE61' : // Orange
                       value > 100  ? '#FEE08B' : // Light Orange
                       value > 50   ? '#D9EF8B' : // Yellow-Green
                       value > 20   ? '#A6D96A' : // Light Green
                                      '#66BD63'; // Dark Green (for lowest values)
            }
            """
        elif selected_kpi_type == "average_speed": # Use selected_kpi_type from outer scope
            color_scale_js = """
            function getColor(value) {
                return value > 70 ? '#1A9850' : // Dark Green (fast)
                       value > 60 ? '#66BD63' : // Green
                       value > 50 ? '#A6D96A' : // Light Green
                       value > 40 ? '#D9EF8B' : // Yellow-Green
                       value > 30 ? '#FEE08B' : // Light Orange
                       value > 20 ? '#FDAE61' : // Orange
                       value > 10 ? '#F46D43' : // Orange-Red
                       value > 0  ? '#D73027' : // Red (for 0 or very low speed)
                                    '#A50026'; // Very dark red for zero speed
            }
            """
        else:
            color_scale_js = """
            function getColor(value) {
                return '#808080'; // Default to grey if KPI type is unknown
            }
            """

        # Legend ranges are now passed directly from Python
        legend_ranges_js = f"const legendRanges = {legend_ranges_json_str};"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Berlin Traffic Map Animation</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                body {{ margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
                #map {{ height: 500px; width: 100%; border-radius: 8px; }}
                .map-controls {{
                    position: absolute;
                    bottom: 10px;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 1000;
                    background: rgba(255, 255, 255, 0.9);
                    padding: 10px 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    display: flex;
                    flex-direction: column;
                    gap: 5px;
                    align-items: center;
                    width: calc(100% - 40px);
                    max-width: 400px;
                    box-sizing: border-box;
                }}
                .map-controls #timeDisplay {{
                    font-size: 1.1em;
                    font-weight: bold;
                    color: #333;
                    text-align: center;
                    width: 100%;
                }}
                .progress-container {{
                    width: 100%;
                    background-color: #f3f3f3;
                    border-radius: 5px;
                    overflow: hidden;
                }}
                .progress-bar {{
                    height: 10px;
                    width: 0%;
                    background-color: #4CAF50;
                    border-radius: 5px;
                    transition: width 0.1s linear;
                }}

                html, body {{
                    margin: 0;
                    padding: 0;
                    overflow: hidden; /* Prevent scrollbars from appearing */
                }}
                .info.legend {{
                    background: white;
                    padding: 6px 8px;
                    line-height: 18px;
                    color: #555;
                    border-radius: 5px;
                    box-shadow: 0 0 15px rgba(0,0,0,0.2);
                }}
                .info.legend i {{
                    width: 18px;
                    height: 18px;
                    float: left;
                    margin-right: 8px;
                    opacity: 0.7;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div class="map-controls">
                <span id="timeDisplay"></span>
                <div class="progress-container">
                    <div id="progressBar" class="progress-bar"></div>
                </div>
            </div>

            <script>
                // DEBUG: Start of JavaScript execution
                console.log("JS: Script loaded.");

                // Global variables for Leaflet map and animation state
                let map;
                let geoJsonLayer;
                let animationInterval;
                let currentAnimationIndex; // This will be updated by Streamlit

                // Data passed from Streamlit
                const allGeoJsonData = {geojson_json_str};
                const availableTimes = {times_json_str};
                const animationStartIndex = {start_idx};
                const animationEndIndex = {end_idx};
                const animationSpeed = {speed} * 1000; // Convert seconds to milliseconds
                const autoPlayOnLoad = {json.dumps(auto_play_on_load)}; // Controls initial animation state
                const initialCurrentIndexFromPython = {initial_current_idx}; // Initial index from Streamlit
                const kpiDisplayName = "{kpi_display_name}"; // Correctly defined here

                // DEBUG: Check received data and flags
                console.log("JS: Received allGeoJsonData keys:", Object.keys(allGeoJsonData));
                console.log("JS: Received availableTimes (first 5):", availableTimes.slice(0, 5));
                console.log("JS: autoPlayOnLoad:", autoPlayOnLoad);
                console.log("JS: initialCurrentIndexFromPython:", initialCurrentIndexFromPython);
                console.log("JS: kpiDisplayName:", kpiDisplayName);

                // DOM elements
                const timeDisplay = document.getElementById('timeDisplay');
                const progressBar = document.getElementById('progressBar');

                // Function to save map view to localStorage
                function saveMapView() {{
                    if (map) {{
                        const view = {{
                            center: map.getCenter(),
                            zoom: map.getZoom()
                        }};
                        localStorage.setItem('lastMapView', JSON.stringify(view));
                        // console.log("JS: Map view saved:", view); // Debug saving
                    }}
                }}

                // Color scale functions (injected from Python)
                {color_scale_js}

                // Legend ranges (injected from Python)
                {legend_ranges_js}

                // Style function for GeoJSON features
                function styleFeature(feature) {{
                    const value = feature.properties.kpi_value; // Use the raw KPI value
                    // DEBUG: Check KPI value and color being applied
                    console.log("JS Style: feature segment_id:", feature.properties.segment_id, "KPI value:", value, "Calculated Color:", getColor(value)); 
                    return {{
                        color: getColor(value), // Use the JS getColor function
                        weight: 6, // Increased weight for better visibility
                        opacity: 0.9, // Increased opacity for better visibility
                    }};
                }}

                // Function to bind tooltips to features
                function onEachFeature(feature, layer) {{
                    if (feature.properties && feature.properties.tooltip_content) {{
                        layer.bindTooltip(feature.properties.tooltip_content, {{permanent: false, direction: 'auto', sticky: true}});
                    }}
                }}

                // Function to update the map layer with new GeoJSON data
                function updateMapLayer() {{
                    try {{
                        // DEBUG: Trace updateMapLayer execution
                        console.log("JS: updateMapLayer called. currentAnimationIndex:", currentAnimationIndex, "Time:", availableTimes[currentAnimationIndex]);

                        if (currentAnimationIndex < availableTimes.length) {{
                            const currentTime = availableTimes[currentAnimationIndex];
                            const currentData = allGeoJsonData[currentTime];

                            if (map.hasLayer(geoJsonLayer)) {{
                                map.removeLayer(geoJsonLayer);
                                // console.log("JS: Removed old geoJsonLayer."); // Debug layer removal
                            }}
                            geoJsonLayer = L.geoJson(currentData, {{
                                style: styleFeature,
                                onEachFeature: onEachFeature
                            }}).addTo(map);
                            // console.log("JS: Added new geoJsonLayer for time:", currentTime); // Debug layer addition

                            updateDisplayElements();
                        }} else {{
                            console.warn("JS: currentAnimationIndex out of bounds:", currentAnimationIndex);
                        }}
                    }} catch (e) {{
                        console.error("JS: Error updating map layer:", e);
                    }}
                }}

                // Function to update time display and progress bar
                function updateDisplayElements() {{
                    if (timeDisplay) {{
                        timeDisplay.textContent = availableTimes[currentAnimationIndex];
                    }} else {{
                        console.warn("JS: timeDisplay element not found.");
                    }}

                    if (progressBar) {{
                        const totalFrames = animationEndIndex - animationStartIndex + 1;
                        const currentFrame = currentAnimationIndex - animationStartIndex;
                        const progress = (currentFrame / totalFrames) * 100;
                        progressBar.style.width = progress + '%';
                    }} else {{
                        console.warn("JS: progressBar element not found.");
                    }}
                }}

                // Function to start the animation
                function startAnimation() {{
                    // DEBUG: Trace startAnimation call
                    console.log("JS: startAnimation called. autoPlayOnLoad:", autoPlayOnLoad);

                    if (animationInterval) {{
                        clearInterval(animationInterval); // Clear any existing interval
                        console.log("JS: Cleared existing animation interval.");
                    }}
                    
                    // Ensure currentAnimationIndex is within bounds when starting
                    if (currentAnimationIndex < animationStartIndex || currentAnimationIndex > animationEndIndex) {{
                        currentAnimationIndex = animationStartIndex;
                        console.log("JS: Reset currentAnimationIndex to start:", currentAnimationIndex);
                    }}

                    updateMapLayer(); // Display the first frame immediately

                    animationInterval = setInterval(() => {{
                        currentAnimationIndex++;
                        if (currentAnimationIndex <= animationEndIndex) {{
                            updateMapLayer();
                        }} else {{
                            // STOP animation at the end time frame (instead of looping)
                            stopAnimation();
                            console.log("JS: Animation reached end and stopped.");
                        }}
                    }}, animationSpeed);
                    console.log("JS: Animation interval set with speed:", animationSpeed);
                }}

                // Function to stop the animation
                function stopAnimation() {{
                    // DEBUG: Trace stopAnimation call
                    console.log("JS: stopAnimation called.");
                    clearInterval(animationInterval);
                    animationInterval = null;
                }}

                // Function to add the legend to the map
                function addLegend(mapInstance) {{
                    const legend = L.control({{position: 'topright'}});

                    legend.onAdd = function (map) {{
                        const div = L.DomUtil.create('div', 'info legend');
                        let labels = [`<b>${{kpiDisplayName}} scale</b>`]; 

                        for (let i = 0; i < legendRanges.length; i++) {{
                            labels.push(
                                '<i style="background:' + legendRanges[i].color + '"></i> ' +
                                legendRanges[i].value
                            );
                        }}

                        div.innerHTML = labels.join('<br>');
                        return div;
                    }};

                    legend.addTo(mapInstance);
                    // console.log("JS: Legend added to map."); // Debug legend addition
                }}

                // Initialize map and animation when the script loads
                // This block runs once when the iframe content is first loaded
                (function() {{
                    // DEBUG: IIFE (Immediately Invoked Function Expression) started
                    console.log("JS: IIFE started.");

                    // This check is mainly for robustness against unexpected iframe behavior,
                    // but `st.components.v1.html` typically reloads the entire iframe content.
                    if (map) {{
                        console.warn("JS: Map object already exists. Removing old map instance.");
                        map.remove(); // Dispose of the old map instance to prevent duplicates
                        map = null;
                    }}
                    
                    try {{
                        // Restore last map view from localStorage
                        const lastMapView = JSON.parse(localStorage.getItem('lastMapView')) || {{}};
                        const initialCenterLat = lastMapView.center ? lastMapView.center.lat : {initial_center[0]};
                        const initialCenterLng = lastMapView.center ? lastMapView.center.lng : {initial_center[1]};
                        const initialZoom = lastMapView.zoom ? lastMapView.zoom : {initial_zoom};

                        map = L.map('map').setView([initialCenterLat, initialCenterLng], initialZoom);
                        console.log("JS: Map initialized with view:", [initialCenterLat, initialCenterLng], initialZoom);

                        // The s, z, x, y are placeholders that Leaflet automatically replaces.
                        // This is the correct way to specify tile layer URLs in Leaflet.
                        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png', {{
                            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CartoDB</a>'
                        }}).addTo(map);

                        // Save map view on move and zoom
                        map.on('moveend', saveMapView);
                        map.on('zoomend', saveMapView);
                        // console.log("JS: Map event listeners added."); // Debug listeners

                        // Set initial animation index based on Streamlit's session state
                        currentAnimationIndex = initialCurrentIndexFromPython;
                        if (currentAnimationIndex < animationStartIndex || currentAnimationIndex > animationEndIndex) {{
                            currentAnimationIndex = animationStartIndex;
                            console.log("JS: Adjusted initial currentAnimationIndex to start:", currentAnimationIndex);
                        }}

                        // Add initial GeoJSON layer
                        const initialGeoJson = allGeoJsonData[availableTimes[currentAnimationIndex]];
                        if (initialGeoJson) {{
                            geoJsonLayer = L.geoJson(initialGeoJson, {{
                                style: styleFeature,
                                onEachFeature: onEachFeature
                            }}).addTo(map);
                            console.log("JS: Initial GeoJSON layer added.");
                        }} else {{
                            console.error("JS: Initial GeoJSON data is undefined for index", currentAnimationIndex, "and time", availableTimes[currentAnimationIndex]);
                        }}
                        
                        updateDisplayElements(); // Update time and progress bar
                        addLegend(map); // Add the legend

                        // Start animation if autoPlayOnLoad is true
                        if (autoPlayOnLoad) {{
                            console.log("JS: autoPlayOnLoad is true. Starting animation.");
                            startAnimation();
                        }} else {{
                            console.log("JS: autoPlayOnLoad is false. Animation not starting automatically.");
                        }}

                    }} catch (e) {{
                        console.error("JS: Error initializing map:", e);
                    }}
                }})(); // Immediately invoked function expression
            </script>
        </body>
        </html>
        """
        return html_content

    # --- Handle animation state from JavaScript (if playing) ---
    # This flag is passed to JS to control whether animation starts on load
    auto_play_on_load_flag = st.session_state.get("auto_playing", False)

    # --- Render the custom HTML component ---
    # The key for the HTML component now includes current_animation_index and animation_speed
    # This key change will force Streamlit to re-render the iframe when filters change
    # or when animation state is explicitly changed by buttons.
    map_html_key = (
        f"animated_map_"
        f"{st.session_state['animation_start_index']}_"
        f"{st.session_state['animation_end_index']}_"
        f"{st.session_state['animation_speed']}_"
        f"{st.session_state['current_animation_index']}_"
        f"{selected_kpi_type}_"
        f"{selected_vehicle_type}_"
        f"{auto_play_on_load_flag}" # Include auto_play_on_load_flag in key to force re-render on button click
    )

    # DEBUG: Print final map_html_key before rendering
    print(f"DEBUG (Python): Final map_html_key before rendering: {map_html_key}")
    print(f"DEBUG (Python): auto_play_on_load_flag sent to JS: {auto_play_on_load_flag}")

    map_html = create_map_html(
        geojson_data_all_times=all_geojson_data,
        available_times_list=available_times_str,
        start_idx=st.session_state["animation_start_index"],
        end_idx=st.session_state["animation_end_index"],
        speed=st.session_state["animation_speed"],
        initial_current_idx=st.session_state["current_animation_index"],
        auto_play_on_load=auto_play_on_load_flag,
        kpi_display_name=selected_kpi_display, # Pass the display name for the legend
        legend_ranges_data=legend_ranges_for_js # Pass the legend ranges to JS
    )

    st.markdown("### 📍 Animated Traffic Map")
    st.components.v1.html(map_html, height=550, scrolling=False)

    # --- Streamlit Buttons to control animation state ---
    st.sidebar.markdown("---")
    st.sidebar.header("Manual Animation Control")

    col1_sidebar, col2_sidebar = st.sidebar.columns(2)

    with col1_sidebar:
        # Buttons are enabled only after data is loaded and map is ready
        start_button_disabled = st.session_state.get("auto_playing", False) or not available_times_str
        if st.button("Start Animation", key="start_animation_btn", disabled=start_button_disabled):
            st.session_state["auto_playing"] = True
            # When auto_playing changes, the map_html_key changes, forcing a re-render
            # The JS will then pick up autoPlayOnLoad=True and start animation
            st.rerun()

    with col2_sidebar:
        stop_button_disabled = not st.session_state.get("auto_playing", False)
        if st.button("Stop Animation", key="stop_animation_btn", disabled=stop_button_disabled):
            st.session_state["auto_playing"] = False
            # When auto_playing changes, the map_html_key changes, forcing a re-render
            # The JS will then pick up autoPlayOnLoad=False and stop animation
            st.rerun()

    # REMOVED: The continuous st.rerun() loop for animation.
    # Animation is now purely client-side.
    # if st.session_state["auto_playing"]:
    #     time.sleep(0.1)
    #     st.rerun()
else:
    st.info("Select KPI, Vehicle Type, and a Date Range (max 1 month), then click 'Load Map Data & Initialize Map' to view the map.")
