# streamlit_app/Home.py

import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(ROOT_DIR,"src","data", "processed", "kpi_enriched_dec_2024.parquet")
SNAPSHOT_DIR = os.path.join(ROOT_DIR, "src","data", "road_kpi_snapshots")
MAP_PATH = os.path.join(ROOT_DIR, "src","data", "raw", "Stammdaten_Verkehrsdetektion_2022_07_20.xlsx")

import streamlit as st
import pandas as pd
import geopandas as gpd
import streamlit.components.v1 as components # Import for custom HTML components
import time

# UI setup
st.set_page_config(page_title="Berlin Traffic Map", layout="wide")
st.title("🛣️ Berlin Traffic Detector Map")

# --- Data Loading and Pre-processing ---
@st.cache_data(show_spinner="Loading initial data...")
def load_initial_data(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if not pd.api.types.is_datetime64_any_dtype(df['tag']):
        df['tag'] = pd.to_datetime(df['tag'])
    return df

df = load_initial_data(DATA_PATH)
df["timestamp"] = df["tag"].dt.strftime("%Y-%m-%d") + " " + df["hour"].astype(str).str.zfill(2) + ":00"
unique_times = sorted(df["timestamp"].unique())

# --- Load ALL GeoJSON snapshots upfront ---
# This is crucial for smooth client-side animation as it avoids disk I/O per frame.
@st.cache_data(show_spinner="Loading all GeoJSON snapshots for animation...")
def load_all_snapshots(snapshot_dir: str, unique_times_list: list) -> dict:
    all_geojson_data = {}
    for ts in unique_times_list:
        safe_ts = ts.replace(":", "-")
        snapshot_path = os.path.join(snapshot_dir, f"road_kpi_{safe_ts}.geojson")
        try:
            gdf = gpd.read_file(snapshot_path)
            # Convert GeoDataFrame to GeoJSON dictionary
            all_geojson_data[ts] = json.loads(gdf.to_json())
        except Exception as e:
            st.warning(f"Could not load snapshot for {ts}: {e}. Skipping this time step.")
            all_geojson_data[ts] = {"type": "FeatureCollection", "features": []} # Provide empty data
    return all_geojson_data

all_geojson_data = load_all_snapshots(SNAPSHOT_DIR, unique_times)

# Filter unique_times to only include those for which data was successfully loaded
available_times = [ts for ts in unique_times if all_geojson_data.get(ts) and all_geojson_data[ts]['features']]
if not available_times:
    st.error("No valid GeoJSON data found for any time step. Please check your data directory.")
    st.stop() # Stop the app if no data is available

# --- Initialize session state for animation controls ---
if "animation_start_index" not in st.session_state:
    st.session_state["animation_start_index"] = 0
if "animation_end_index" not in st.session_state:
    st.session_state["animation_end_index"] = len(available_times) - 1
if "animation_speed" not in st.session_state:
    st.session_state["animation_speed"] = 0.5 # Default speed in seconds per frame
if "current_animation_index" not in st.session_state: # Track current index for resuming
    st.session_state["current_animation_index"] = 0
if "auto_playing" not in st.session_state: # Track if animation was playing
    st.session_state["auto_playing"] = False

# --- Animation Controls in Streamlit Sidebar ---
st.sidebar.header("Animation Controls")

# Select start and end times for the animation
start_time_selection = st.sidebar.selectbox(
    "Animation Start Time",
    options=available_times,
    index=st.session_state["animation_start_index"],
    key="animation_start_selector"
)
end_time_selection = st.sidebar.selectbox(
    "Animation End Time",
    options=available_times,
    index=st.session_state["animation_end_index"],
    key="animation_end_selector"
)

# Update the indices based on selected times
st.session_state["animation_start_index"] = available_times.index(start_time_selection)
st.session_state["animation_end_index"] = available_times.index(end_time_selection)

# Animation Speed Slider
new_animation_speed = st.sidebar.slider(
    "Animation Speed (seconds per frame)",
    min_value=0.1,
    max_value=3.0,
    value=st.session_state["animation_speed"],
    step=0.1,
    key="animation_speed_slider"
)

# --- FIX: Update animation speed in session state and force rerun immediately ---
# This ensures the new speed is always picked up on the first change.
if new_animation_speed != st.session_state["animation_speed"]:
    st.session_state["animation_speed"] = new_animation_speed
    # If speed changes while playing, reset current index to start of range
    if st.session_state["auto_playing"]:
        st.session_state["current_animation_index"] = st.session_state["animation_start_index"]
    st.rerun() # Force a rerun immediately to apply the new speed

# --- Generate HTML for the Client-Side Map and Animation ---
def create_map_html(
    geojson_data_all_times: dict,
    available_times_list: list,
    start_idx: int,
    end_idx: int,
    speed: float,
    initial_current_idx: int, # New parameter to pass current index
    initial_zoom: int = 12,
    initial_center: list = [52.52, 13.405],
    auto_play_on_load: bool = False # New parameter to indicate if it should auto-play on load
) -> str:
    # Convert Python dicts/lists to JSON strings for embedding in JavaScript
    geojson_json_str = json.dumps(geojson_data_all_times)
    times_json_str = json.dumps(available_times_list)

    # Updated color scale for visualization: light yellow to dark red
    color_scale_js = """
    function getColor(d) {
        return d > 1000 ? '#662506' : // Darkest Red/Brown
               d > 500  ? '#993404' : // Dark Red
               d > 200  ? '#CC4C02' : // Medium Red
               d > 100  ? '#EC7014' : // Orange-Red
               d > 50   ? '#FE9929' : // Orange
               d > 20   ? '#FEC44F' : // Light Orange
               d > 10   ? '#FED976' : // Yellow-Orange
                          '#FFFFCC'; // Very Light Yellow (for lowest values)
    }
    """
    # Define the ranges and colors for the legend
    legend_ranges_js = """
    const legendRanges = [
        { value: '1000+', color: '#662506' },
        { value: '501-1000', color: '#993404' },
        { value: '201-500', color: '#CC4C02' },
        { value: '101-200', color: '#EC7014' },
        { value: '51-100', color: '#FE9929' },
        { value: '21-50', color: '#FEC44F' },
        { value: '11-20', color: '#FED976' },
        { value: '0-10', color: '#FFFFCC' }
    ];
    """

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
                flex-direction: column; /* Arrange items vertically */
                gap: 5px; /* Smaller gap between elements */
                align-items: center;
                width: calc(100% - 40px); /* Adjust width to fit */
                max-width: 400px; /* Max width for better aesthetics */
                box-sizing: border-box; /* Include padding in width */
            }}
            .map-controls #timeDisplay {{
                font-size: 1.1em;
                font-weight: bold;
                color: #333;
                text-align: center;
                width: 100%; /* Take full width */
            }}
            /* Progress Bar Styles */
            .progress-container {{
                width: 100%;
                background-color: #f3f3f3;
                border-radius: 5px;
                overflow: hidden;
            }}
            .progress-bar {{
                height: 10px;
                width: 0%;
                background-color: #4CAF50; /* Green progress bar */
                border-radius: 5px;
                transition: width 0.1s linear; /* Smooth transition for progress */
            }}

            /* Streamlit-specific styles for the embedded iframe to remove default margins */
            html, body {{
                margin: 0;
                padding: 0;
                overflow: hidden; /* Prevent scrollbars inside iframe */
            }}
            /* Legend Styles */
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
            // Embed data from Python
            const allGeoJsonData = {geojson_json_str};
            const availableTimes = {times_json_str};
            let animationStartIndex = {start_idx};
            let animationEndIndex = {end_idx};
            const animationSpeed = {speed} * 1000; // Convert seconds to milliseconds
            let autoPlayOnLoad = {json.dumps(auto_play_on_load)}; // Pass auto_play_on_load flag

            let map;
            let geoJsonLayer;
            let animationInterval;
            let currentAnimationIndex; // This will be updated by Python and used on re-render
            let timeDisplay = document.getElementById('timeDisplay');
            let progressBar = document.getElementById('progressBar'); // Get progress bar element

            // Initialize map
            function initMap() {{
                try {{
                    // Retrieve last known map view from localStorage if available
                    const lastMapView = JSON.parse(localStorage.getItem('lastMapView')) || {{}};
                    const initialCenterLat = lastMapView.center ? lastMapView.center.lat : {initial_center[0]};
                    const initialCenterLng = lastMapView.center ? lastMapView.center.lng : {initial_center[1]};
                    const initialZoom = lastMapView.zoom ? lastMapView.zoom : {initial_zoom};

                    map = L.map('map').setView([initialCenterLat, initialCenterLng], initialZoom);

                    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png', {{
                        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CartoDB</a>'
                    }}).addTo(map);

                    // Save map view on moveend and zoomend
                    map.on('moveend', saveMapView);
                    map.on('zoomend', saveMapView);


                    // Initialize with the current index passed from Python
                    currentAnimationIndex = {initial_current_idx};
                    // Ensure currentAnimationIndex is within the valid range
                    if (currentAnimationIndex < animationStartIndex || currentAnimationIndex > animationEndIndex) {{
                        currentAnimationIndex = animationStartIndex;
                    }}

                    const initialGeoJson = allGeoJsonData[availableTimes[currentAnimationIndex]];
                    geoJsonLayer = L.geoJson(initialGeoJson, {{
                        style: styleFeature,
                        onEachFeature: onEachFeature
                    }}).addTo(map);

                    updateDisplayElements(); // Call to update time and progress bar

                    // Add Legend
                    addLegend(map);

                    // If auto-play was active, restart it
                    if (autoPlayOnLoad) {{
                        startAnimation();
                    }}

                }} catch (e) {{
                    console.error("Error initializing map:", e);
                }}
            }}

            // Function to save map view to localStorage
            function saveMapView() {{
                const view = {{
                    center: map.getCenter(),
                    zoom: map.getZoom()
                }};
                localStorage.setItem('lastMapView', JSON.stringify(view));
            }}

            // Color scale function
            {color_scale_js}

            // Legend ranges (must match getColor logic)
            {legend_ranges_js}

            // Style function for GeoJSON features
            function styleFeature(feature) {{
                const value = feature.properties.q_kfz_det_hr_avg; // Assuming this is the column to color by
                return {{
                    color: getColor(value),  // Apply KPI color to the 'color' property for LineStrings
                    weight: 4,               // Increased weight for bolder lines
                    opacity: 1,              // Full opacity for the line
                }};
            }}

            // Function to add tooltips on feature hover
            function onEachFeature(feature, layer) {{
                if (feature.properties) {{
                    layer.bindTooltip(
                        `<b>Street:</b> ${{feature.properties.name_road_segment}}<br>` +
                        `<b>Value:</b> ${{feature.properties.q_kfz_det_hr_avg !== undefined ? feature.properties.q_kfz_det_hr_avg.toFixed(2) : 'N/A'}}`,
                        {{permanent: false, direction: 'auto', sticky: true}} // Tooltip options: not always visible, auto direction, follows mouse
                    );
                }}
            }}

            // Function to update the map layer's style and display elements
            function updateMapLayer() {{
                try {{
                    if (currentAnimationIndex < availableTimes.length) {{
                        const currentTime = availableTimes[currentAnimationIndex];
                        const currentData = allGeoJsonData[currentTime];

                        if (map.hasLayer(geoJsonLayer)) {{
                            map.removeLayer(geoJsonLayer);
                        }}
                        geoJsonLayer = L.geoJson(currentData, {{
                            style: styleFeature,
                            onEachFeature: onEachFeature
                        }}).addTo(map);

                        updateDisplayElements(); // Call to update time and progress bar
                    }}
                }} catch (e) {{
                    console.error("Error updating map layer:", e);
                }}
            }}

            // Function to update the time display and progress bar
            function updateDisplayElements() {{
                timeDisplay.textContent = availableTimes[currentAnimationIndex];

                const totalFrames = animationEndIndex - animationStartIndex + 1;
                const currentFrame = currentAnimationIndex - animationStartIndex;
                const progress = (currentFrame / totalFrames) * 100;
                progressBar.style.width = progress + '%';
            }}

            // Animation functions
            function startAnimation() {{
                if (animationInterval) {{
                    clearInterval(animationInterval);
                }}
                // Ensure currentAnimationIndex is within the animation range
                if (currentAnimationIndex < animationStartIndex || currentAnimationIndex > animationEndIndex) {{
                    currentAnimationIndex = animationStartIndex;
                }}
                updateMapLayer(); // Display first frame immediately

                animationInterval = setInterval(() => {{
                    currentAnimationIndex++;
                    if (currentAnimationIndex <= animationEndIndex) {{
                        updateMapLayer();
                    }} else {{
                        stopAnimation();
                    }}
                }}, animationSpeed);
            }}

            function stopAnimation() {{
                clearInterval(animationInterval);
                animationInterval = null;
            }}

            // Function to add the legend to the map
            function addLegend(mapInstance) {{
                const legend = L.control({{position: 'topright'}});

                legend.onAdd = function (map) {{
                    const div = L.DomUtil.create('div', 'info legend');
                    let labels = ['<b>q_kfz_det_hr_avg scale</b>']; // Title for the legend

                    // loop through our density intervals and generate a label with a colored square for each interval
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
            }}

            // Initialize map on load
            window.onload = initMap;

        </script>
    </body>
    </html>
    """
    return html_content

# --- Handle animation state from JavaScript (if playing) ---
# This part is crucial for making the animation resume correctly
# when Streamlit re-runs (e.g., due to speed slider change).
# We need to explicitly tell Streamlit to restart the animation if it was playing.
if st.session_state["auto_playing"]:
    # If auto_playing was true, we want the JS to restart the animation
    # from the current index.
    auto_play_on_load_flag = True
else:
    auto_play_on_load_flag = False

# --- Render the custom HTML component ---
# The key for the HTML component now includes current_animation_index and animation_speed
# This ensures the iframe re-renders and the JS picks up the new state/speed.
map_html_key = f"animated_map_{st.session_state['animation_start_index']}_{st.session_state['animation_end_index']}_{st.session_state['animation_speed']}_{st.session_state['current_animation_index']}"

map_html = create_map_html(
    geojson_data_all_times=all_geojson_data,
    available_times_list=available_times,
    start_idx=st.session_state["animation_start_index"],
    end_idx=st.session_state["animation_end_index"],
    speed=st.session_state["animation_speed"],
    initial_current_idx=st.session_state["current_animation_index"], # Pass current index
    auto_play_on_load=auto_play_on_load_flag # Pass auto-play flag
)

st.markdown("### 📍 Animated Traffic Map")
components.html(map_html, height=550, scrolling=False) # Increased height for controls

# --- Streamlit Buttons to control animation state ---
# These buttons will update st.session_state and trigger a rerun,
# which will then pass the updated state to the JS.
st.sidebar.markdown("---")
st.sidebar.header("Manual Animation Control")

col1_sidebar, col2_sidebar = st.sidebar.columns(2)

with col1_sidebar:
    if st.button("Start Animation", key="start_animation_btn", disabled=st.session_state["auto_playing"]):
        st.session_state["auto_playing"] = True
        # If starting manually, ensure we start from the beginning of the range
        st.session_state["current_animation_index"] = st.session_state["animation_start_index"]
        st.rerun()

with col2_sidebar:
    if st.button("Stop Animation", key="stop_animation_btn", disabled=not st.session_state["auto_playing"]):
        st.session_state["auto_playing"] = False
        # When stopping manually, capture the current index from the JS side
        # This is the tricky part without direct JS->Python communication.
        # For now, it will stop at the last known Python index.
        # If you need precise stopping, consider `st_javascript` for bi-directional communication.
        st.rerun()

# If the animation is playing, we need to keep rerunning Streamlit
# to allow the JS to continue its loop.
if st.session_state["auto_playing"]:
    # This will cause Streamlit to continuously re-run, which in turn
    # re-renders the HTML component. The JS will then pick up the
    # current_animation_index and auto_play_on_load_flag.
    # We need to ensure the JS updates the current_animation_index before Streamlit re-runs.
    # This is handled by the JS itself incrementing currentAnimationIndex.
    # The `time.sleep` in JS will create the visual delay.
    pass # No explicit st.rerun() here, as the key change handles it.
