# streamlit_app/Home.py

import os
import json

import streamlit as st
import pandas as pd
import geopandas as gpd
import streamlit.components.v1 as components
import time
from pymongo import MongoClient # Import MongoClient
import datetime

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "traffic_dashboard")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "road_kpi_snapshots")

# UI setup
st.set_page_config(page_title="Berlin Traffic Map", layout="wide")

st.title("🛣️ Berlin Traffic Detector Map")
    
with st.spinner("🔄 Loading available timeframes from MongoDB..."):
    try:
        client = MongoClient(MONGO_URI)
        collection = client[DB_NAME][COLLECTION_NAME]

        # Fetch all distinct timestamps
        all_timestamps = collection.distinct("timestamp")
        df_timestamps = pd.to_datetime(all_timestamps)

        # Generate derived time lists
        unique_times = sorted(pd.Series(df_timestamps).dt.strftime("%Y-%m-%d %H:00").unique())
        unique_dates = sorted(pd.Series(df_timestamps).dt.date.unique())
        unique_hours = sorted(pd.Series(df_timestamps).dt.hour.unique())

        client.close()
    except Exception as e:
        st.error(f"❌ Failed to load time data from MongoDB: {e}")
        st.stop()

# --- MongoDB Data Loading Function ---
@st.cache_data(show_spinner="Fetching map data from database...") # Spinner for database fetch
def load_snapshots_from_mongodb(mongo_uri: str, db_name: str, collection_name: str,
                                 selected_vehicle_type: str, selected_kpi_type: str,
                                 time_range_times: list) -> dict:
    """
    Loads specific GeoJSON snapshots from MongoDB based on selected filters and time range.
    """
    all_geojson_data = {}
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]

        # Query MongoDB for documents matching the criteria
        # Use $in for the list of timestamps to fetch all required frames for the animation
        query = {
            "timestamp": {"$in": time_range_times},
            "vehicle_type": selected_vehicle_type,
            "kpi_type": selected_kpi_type
        }
        # Fetch documents, excluding the _id field, and sort by timestamp to ensure animation order
        cursor = collection.find(query, {"_id": 0}).sort("timestamp", 1)

        fetched_documents = list(cursor)

        if not fetched_documents:
            st.warning(f"No data found for the selected combination: Vehicle Type='{selected_vehicle_type}', KPI='{selected_kpi_type}' within the time range.")
            return {}

        for doc in fetched_documents:
            ts = doc["timestamp"]
            # MongoDB BSON documents are directly usable as Python dictionaries.
            # Convert to FeatureCollection format for Leaflet's L.geoJSON
            feature_collection = {"type": "FeatureCollection", "features": doc["features"]}
            all_geojson_data[ts] = feature_collection

        client.close() # Close connection after fetching
        # Sort the dictionary by timestamp keys to ensure correct animation order
        return {k: all_geojson_data[k] for k in sorted(all_geojson_data)}

    except Exception as e:
        st.error(f"Error loading snapshots from MongoDB: {e}")
        return {} # Return empty dict on error

# --- Streamlit Session State Initialization ---
if "animation_start_index" not in st.session_state:
    st.session_state["animation_start_index"] = 0
if "animation_end_index" not in st.session_state:
    st.session_state["animation_end_index"] = len(unique_times) - 1
if "animation_speed" not in st.session_state:
    st.session_state["animation_speed"] = 1000 # milliseconds
if "current_animation_index" not in st.session_state:
    st.session_state["current_animation_index"] = 0
if "auto_playing" not in st.session_state:
    st.session_state["auto_playing"] = False
# New session states for vehicle and KPI types
if "selected_vehicle_type" not in st.session_state:
    st.session_state["selected_vehicle_type"] = "all" # Default to 'all'
if "selected_kpi_type" not in st.session_state:
    st.session_state["selected_kpi_type"] = "number_of_vehicles" # Default to 'number_of_vehicles


# --- Sidebar Controls ---
st.sidebar.header("Map Controls")

# Define the display names and internal keys for vehicle types and KPIs
VEHICLE_TYPE_OPTIONS = {
    "All Vehicles": "all",
    "Cars": "cars",
    "Trucks": "trucks"
}

KPI_TYPE_OPTIONS = {
    "Number of Vehicles": "number_of_vehicles",
    "Average Speed (km/h)": "avg_speed"
}

# Add new select boxes for Vehicle Type and KPI Type
selected_vehicle_type_display = st.sidebar.selectbox(
    "Select Vehicle Type",
    options=list(VEHICLE_TYPE_OPTIONS.keys()),
    index=list(VEHICLE_TYPE_OPTIONS.keys()).index(
        [k for k, v in VEHICLE_TYPE_OPTIONS.items() if v == st.session_state["selected_vehicle_type"]][0]
    ),
    key="vehicle_type_selector"
)
selected_vehicle_type_internal = VEHICLE_TYPE_OPTIONS[selected_vehicle_type_display]

selected_kpi_type_display = st.sidebar.selectbox(
    "Select KPI",
    options=list(KPI_TYPE_OPTIONS.keys()),
    index=list(KPI_TYPE_OPTIONS.keys()).index(
        [k for k, v in KPI_TYPE_OPTIONS.items() if v == st.session_state["selected_kpi_type"]][0]
    ),
    key="kpi_type_selector"
)
selected_kpi_type_internal = KPI_TYPE_OPTIONS[selected_kpi_type_display]

# Update session state if selection changes
if selected_vehicle_type_internal != st.session_state["selected_vehicle_type"]:
    st.session_state["selected_vehicle_type"] = selected_vehicle_type_internal
    st.session_state["auto_playing"] = False # Stop animation if type changes
    st.session_state["current_animation_index"] = 0 # Reset animation to start of range
    st.rerun() # Rerun to load new data

if selected_kpi_type_internal != st.session_state["selected_kpi_type"]:
    st.session_state["selected_kpi_type"] = selected_kpi_type_internal
    st.session_state["auto_playing"] = False # Stop animation if KPI changes
    st.session_state["current_animation_index"] = 0 # Reset animation to start of range
    st.rerun() # Rerun to load new data

# Get selected date and hour objects
start_col1, start_col2 = st.sidebar.columns([2, 1])
with start_col1:
    selected_start_date = st.sidebar.date_input("Start Date", value=min(unique_dates), min_value=min(unique_dates), max_value=max(unique_dates), key="start_date_picker")
with start_col2:
    selected_start_hour = st.sidebar.selectbox("Start Hour", options=unique_hours, index=0, key="start_hour_selector")

end_col1, end_col2 = st.sidebar.columns([2, 1])
with end_col1:
    selected_end_date = st.sidebar.date_input("End Date", value=max(unique_dates), min_value=min(unique_dates), max_value=max(unique_dates), key="end_date_picker")
with end_col2:
    selected_end_hour = st.sidebar.selectbox("End Hour", options=unique_hours, index=len(unique_hours)-1, key="end_hour_selector")

# Reconstruct the timestamp strings in the same format as 'unique_times'
start_datetime_obj = datetime.datetime.combine(selected_start_date, datetime.datetime.min.time().replace(hour=selected_start_hour))
end_datetime_obj = datetime.datetime.combine(selected_end_date, datetime.datetime.min.time().replace(hour=selected_end_hour))

# Format them as strings
start_time_str = start_datetime_obj.strftime("%Y-%m-%d %H:00")
end_time_str = end_datetime_obj.strftime("%Y-%m-%d %H:00")

st.session_state["animation_end_index"] = unique_times.index(end_time_str)

# Ensure start is not after end
if st.session_state["animation_start_index"] > st.session_state["animation_end_index"]:
    st.session_state["animation_end_index"] = st.session_state["animation_start_index"]
    st.warning("End time adjusted to be after start time.")
    st.rerun() # Rerun to update the end time selectbox

animation_speed_display = st.sidebar.slider(
    "Animation Speed",
    min_value=1,
    max_value=20,
    value=10,
    step=1,
    key="animation_speed_slider"
)
max_ms = 2000 # Max milliseconds (slowest)
min_ms = 100  # Min milliseconds (fastest)

animation_speed_ms = max_ms + ((min_ms - max_ms) / (20 - 1)) * (animation_speed_display - 1)

st.session_state["animation_speed"] = int(animation_speed_ms) # Ensure it's an integer
st.sidebar.caption(f"({st.session_state['animation_speed']} ms per frame)") # Show actual ms

st.session_state["animation_speed"] = animation_speed_ms

# Filter unique_times list based on selected start and end index for MongoDB query
times_for_query = unique_times[st.session_state["animation_start_index"] : st.session_state["animation_end_index"] + 1]

with st.spinner("Loading map data from database..."): # Explicit spinner for database fetch
    # Load data from MongoDB based on current selections
    # Crucial for re-fetching data only when selections change
    all_geojson_data = load_snapshots_from_mongodb(
        MONGO_URI, DB_NAME, COLLECTION_NAME,
        st.session_state["selected_vehicle_type"], # Use internal keys
        st.session_state["selected_kpi_type"],     # Use internal keys
        times_for_query
    )

# Extract available times for animation from the loaded data    
available_times_for_animation = sorted(list(all_geojson_data.keys()))


if not available_times_for_animation:
    st.error("No data available for the selected filters and time range. Please adjust your selections or ensure data is generated in MongoDB.")
    st.stop() # Stop the app if no data to display
    
try:
    js_animation_start_index = available_times_for_animation.index(start_time_str)
except ValueError:
    js_animation_start_index = 0

try:
    js_animation_end_index = available_times_for_animation.index(end_time_str)
except ValueError:
    js_animation_end_index = len(available_times_for_animation) - 1

# Ensure start is not after end within the *filtered* list
if js_animation_start_index > js_animation_end_index:
    js_animation_end_index = js_animation_start_index

st.session_state["animation_start_index"] = js_animation_start_index
st.session_state["animation_end_index"] = js_animation_end_index

# Adjust current_animation_index if it falls outside the new range
if st.session_state["current_animation_index"] < 0 or \
   st.session_state["current_animation_index"] >= len(available_times_for_animation):
    st.session_state["current_animation_index"] = 0 # Reset to start of available data


# --- Map HTML Generation ---
def create_map_html(
    geojson_data_all_times: dict, # Now contains data for specific vehicle/kpi combo
    available_times_list: list, # List of times for the current combo
    start_idx: int,
    end_idx: int,
    speed_ms: int, # Speed in milliseconds
    initial_current_idx: int,
    auto_play_on_load: bool,
    initial_zoom: int = 12,
    initial_center: list = [52.52, 13.405],
    selected_v_type_label: str = "All Vehicles",
    selected_kpi_type_label: str = "Number of Vehicles"
) -> str:
    # Convert Python dicts/lists to JSON strings for embedding in JavaScript
    geojson_json_str = json.dumps(geojson_data_all_times)
    times_json_str = json.dumps(available_times_list)

    # # Determine KPI for color scale, assuming 'value' field in GeoJSON properties
    # kpi_field = "value"

    # Dynamic legend based on selected KPI (passed from Python)
    legend_title = f"{selected_v_type_label} - {selected_kpi_type_label}"
    
    # Define color scale based on the type of KPI (passed from Python)
    
    if "speed" in selected_kpi_type_label.lower(): # Check if it's a speed KPI
        color_scale_js = """
        function getColor(d) {
            return d > 70 ? '#1A9850' : // Dark Green (70+ km/h)
                   d > 60 ? '#66BD63' : // Green (61-70 km/h)
                   d > 50 ? '#A6D96A' : // Light Green (51-60 km/h)
                   d > 40 ? '#D9EF8B' : // Yellow-Green (41-50 km/h)
                   d > 30 ? '#FEE08B' : // Light Orange (31-40 km/h)
                   d > 20 ? '#FDAE61' : // Orange (21-30 km/h)
                   d > 0  ? '#F46D43' : // Orange-Red (1-20 km/h)
                            '#D73027'; // Red (0 km/h)
        }
        """
        # Dynamic legend ranges for speed
        legend_ranges_js = """
        const legendRanges = [
            { value: '70+ km/h', color: '#1A9850' },
            { value: '61-70 km/h', color: '#66BD63' },
            { value: '51-60 km/h', color: '#A6D96A' },
            { value: '41-50 km/h', color: '#D9EF8B' },
            { value: '31-40 km/h', color: '#FEE08B' },
            { value: '21-30 km/h', color: '#FDAE61' },
            { value: '1-20 km/h', color: '#F46D43' },
            { value: '0 km/h', color: '#D73027' }
        ];
        """
    else: # Default to number of vehicles (count-based KPI)
        color_scale_js = """
        function getColor(d) {
            return d > 2000 ? '#A50026' : // Dark Red (2000+)
                   d > 1000 ? '#D73027' : // Red (1001-2000)
                   d > 500  ? '#F46D43' : // Orange-Red (501-1000)
                   d > 200  ? '#FDAE61' : // Orange (201-500)
                   d > 100  ? '#FEE08B' : // Light Orange (101-200)
                   d > 50   ? '#D9EF8B' : // Yellow-Green (51-100)
                   d > 20   ? '#A6D96A' : // Light Green (21-50)
                              '#66BD63'; // Dark Green (0-20)
        }
        """
        # Dynamic legend ranges for count
        legend_ranges_js = """
        const legendRanges = [
            { value: '2000+', color: '#A50026' },
            { value: '1001-2000', color: '#D73027' },
            { value: '501-1000', color: '#F46D43' },
            { value: '201-500', color: '#FDAE61' },
            { value: '101-200', color: '#FEE08B' },
            { value: '51-100', color: '#D9EF8B' },
            { value: '21-50', color: '#A6D96A' },
            { value: '0-20', color: '#66BD63' }
        ];
        """
    
    # Define legend_labels_js here
    legend_labels_js = """
    for (let i = 0; i < legendRanges.length; i++) {
        labels.push(
            '<i style="background:' + legendRanges[i].color + '"></i> ' +
            legendRanges[i].value
        );
    }
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
            #map {{ height: 90vh; width: 100%; border-radius: 8px; }} /* Adjusted height here */
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
            const animationSpeed = {speed_ms}; // Speed in milliseconds
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

                    // Get the data for the current animation index from the full dataset
                    const initialGeoJson = allGeoJsonData[availableTimes[currentAnimationIndex]];
                    
                    if (initialGeoJson && initialGeoJson.features && initialGeoJson.features.length > 0) {{
                        geoJsonLayer = L.geoJson(initialGeoJson, {{
                            style: styleFeature,
                            onEachFeature: onEachFeature
                        }}).addTo(map);
                    }} else {{
                        geoJsonLayer = L.geoJson(null).addTo(map); // Add an empty layer if no data
                        console.warn("No features to display for initial timestamp:", availableTimes[currentAnimationIndex]);
                    }}

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
                const value = feature.properties.value; // Now consistently 'value'
                return {{
                    color: getColor(value),
                    weight: 4,
                    opacity: 1,
                }};
            }}

            // Function to add tooltips on feature hover
            function onEachFeature(feature, layer) {{
                if (feature.properties && feature.properties.value !== undefined) {{ 
                    layer.bindTooltip(
                        `<b>Street:</b> ${{feature.properties.name_road_segment}}<br>` +
                        `<b>{selected_kpi_type_label}:</b> ${{feature.properties.value !== undefined ? feature.properties.value.toFixed(2) : 'N/A'}}`,
                        {{permanent: false, direction: 'auto', sticky: true}}
                    );
                }}
            }}

            // Function to update the map layer's style and display elements
            function updateMapLayer() {{
                try {{
                    // Only update if the current index is within the active animation range
                    if (currentAnimationIndex >= animationStartIndex && currentAnimationIndex <= animationEndIndex) {{
                        const currentTime = availableTimes[currentAnimationIndex];
                        const currentData = allGeoJsonData[currentTime];

                        if (map.hasLayer(geoJsonLayer)) {{
                            map.removeLayer(geoJsonLayer);
                        }}
                        
                        if (currentData && currentData.features && currentData.features.length > 0) {{
                            geoJsonLayer = L.geoJson(currentData, {{
                                style: styleFeature,
                                onEachFeature: onEachFeature
                            }}).addTo(map);
                        }} else {{
                            geoJsonLayer = L.geoJson(null).addTo(map); // Add an empty layer if no data
                            console.warn("No features to display for timestamp:", currentTime);
                        }}

                        updateDisplayElements(); // Call to update time and progress bar
                    }}
                }} catch (e) {{
                    console.error("Error updating map layer:", e);
                }}
            }}

            // Function to update the time display and progress bar
            function updateDisplayElements() {{
                timeDisplay.textContent = availableTimes[currentAnimationIndex];

                // Calculate progress based on the *selected* animation range
                const totalFramesInSelectedRange = animationEndIndex - animationStartIndex + 1;
                const currentFrameInSelectedRange = currentAnimationIndex - animationStartIndex;
                
                // Ensure totalFramesInSelectedRange is not zero to avoid division by zero
                if (totalFramesInSelectedRange > 0) {{
                    const progress = (currentFrameInSelectedRange / (totalFramesInSelectedRange - 1)) * 100;
                    progressBar.style.width = progress + '%';
                }} else {{
                    progressBar.style.width = '0%'; // No progress if no frames
                }}
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
                        // Loop back to the start of the selected range
                        currentAnimationIndex = animationStartIndex;
                        updateMapLayer();
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
                    let labels = ['<b>{legend_title}</b>']; // Dynamic title

                    {legend_labels_js}

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

if st.session_state["auto_playing"]:
    auto_play_on_load_flag = True
else:
    auto_play_on_load_flag = False

# --- Render the custom HTML component ---

map_html_key = (
    f"animated_map_"
    f"{st.session_state['animation_start_index']}_"
    f"{st.session_state['animation_end_index']}_"
    f"{st.session_state['animation_speed']}_"
    f"{st.session_state['selected_vehicle_type']}_"
    f"{st.session_state['selected_kpi_type']}"
)

# Get the display labels for the legend and tooltip
current_v_type_label = [k for k, v in VEHICLE_TYPE_OPTIONS.items() if v == st.session_state["selected_vehicle_type"]][0]
current_kpi_type_label = [k for k, v in KPI_TYPE_OPTIONS.items() if v == st.session_state["selected_kpi_type"]][0]


map_html = create_map_html(
    geojson_data_all_times=all_geojson_data,
    available_times_list=available_times_for_animation, # Use the filtered list of times
    start_idx=st.session_state["animation_start_index"],
    end_idx=st.session_state["animation_end_index"],
    speed_ms=st.session_state["animation_speed"], # Pass speed in milliseconds
    initial_current_idx=st.session_state["current_animation_index"], # Pass current index
    auto_play_on_load=auto_play_on_load_flag, # Pass auto-play flag
    selected_v_type_label=current_v_type_label, # Pass for JS legend/tooltip
    selected_kpi_type_label=current_kpi_type_label # Pass for JS legend/tooltip
)

st.markdown("### 📍 Animated Traffic Map")
components.html(map_html, height=700, scrolling=False)

# --- Streamlit Buttons to control animation state ---
st.sidebar.markdown("---")
st.sidebar.header("Manual Animation Control")

col1_sidebar, col2_sidebar = st.sidebar.columns(2)

with col1_sidebar:
    if st.button("Start Animation", key="start_animation_btn", disabled=st.session_state["auto_playing"]):
        st.session_state["auto_playing"] = True
        st.session_state["current_animation_index"] = st.session_state["animation_start_index"]
        time.sleep(0.1)
        st.rerun() 

with col2_sidebar:
    if st.button("Stop Animation", key="stop_animation_btn", disabled=not st.session_state["auto_playing"]):
        st.session_state["auto_playing"] = False
        time.sleep(0.1)
        st.rerun() 