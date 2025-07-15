BerliFlow: Interactive Berlin Traffic Visualization Dashboard

🚦 Project Overview
BerliFlow bridges the gap between Berlin’s fragmented traffic data sources and the need for actionable, accessible urban mobility insights. By integrating Berlin’s traffic APIs, OpenStreetMap geodata, and modern big data principles, we provide a user-friendly dashboard that transforms complex traffic data into meaningful visualizations.

Key Technologies:

MongoDB (optimized for JSON / GeoJSON and geospatial queries)

Python (pandas, geopandas, shapely for processing)

Streamlit (interactive web-based dashboard)

Containerized Cloud Deployment (CapRover)

🛑 Problem Statement & Motivation
Berlin’s traffic data exists but is fragmented across city departments, published in technical formats that are not accessible to general users. Existing solutions lack integrated historical analysis or intuitive dashboards.
Challenges Addressed:

Accessibility: Non-technical users cannot easily interpret existing datasets.

Temporal Limitations: Existing tools lack robust historical exploration.

Decision-Making Gaps: Urban planners and officials lack consolidated, actionable insights.

Our Solution:
A unified platform offering real-time and historical traffic data visualization, enabling insights through interactive, map-based filtering and temporal exploration.

🏗️ System Architecture
Context Diagram
plaintext
Kopieren
Bearbeiten
+----------------+     +------------------+     +-----------------+
|    Citizens    |     | Urban Planners    |     | City Officials   |
| (Route Planning)|    | (Infrastructure)  |     | (Traffic Mgmt.)  |
+-------+--------+     +--------+----------+     +--------+--------+
        |                       |                         |
        +-----------------------+-------------------------+
                                |
                                v
                   +--------------------------------------+
                   |           BerliFlow Platform          |
                   | (Traffic Visualization Application)   |
                   +--------------------------------------+
                    /             |                 \
                   /              |                  \
    +-----------------+  +----------------+  +------------------+
    | Berlin Open Data|  | Geographic Data|  | Other APIs       |
    | Portal (Traffic)|  | (OSM, Districts)| | (City Systems)    |
    +-----------------+  +----------------+  +------------------+
Container Diagram
plaintext
Kopieren
Bearbeiten
+-----------------------------------------------------------+
|                      BerliFlow Platform                    |
|-----------------------------------------------------------|
| +------------------+  +--------------------+  +----------+ |
| |    Frontend      |  |      Backend       |  |  MongoDB  | |
| |  (Streamlit UI)  |  |   (Python APIs)    |  | (GeoJSON) | |
| | - Map Filters    |  | - Data Processing  |  | - Traffic | |
| | - KPIs           |  | - Geospatial Logic |  | - Spatial | |
| +--------+---------+  +--------+-----------+  +----------+ |
|          |                    |                     |      |
|          +--------------------+---------------------+      |
|                                |                             |
|       +------------------------v-----------------------------+
|       |       Berlin Open Data APIs (Traffic Measurement)     |
|       +-------------------------------------------------------+
🧰 Technology Stack
Component	Technology	Purpose
Backend	Python	Data integration, processing, APIs
Database	MongoDB	JSON & GeoJSON, flexible geospatial data
Frontend	Streamlit	Interactive dashboards & filtering
Geodata	OpenStreetMap	Base maps, district-level geometry
APIs	Berlin Traffic	Real-time sensor & historical traffic
Cloud	CapRover / Docker	Containerized deployment

Why MongoDB?
Our data is JSON-based with heavy geospatial components (GeoJSON). MongoDB’s flexibility, spatial indexing, and document model far surpass relational alternatives for our needs.

🛣️ Data Sources & Structure
Data Origin:
Berlin Traffic Detection API (Sensors: cars, trucks, speed, hourly granularity)

OpenStreetMap (Road network, districts)

Data Pipeline:
Collect: APIs deliver raw JSON data.

Enrich: Merge traffic data with geographic road network.

Transform: Convert to GeoJSON for MongoDB ingestion.

Serve: Backend queries serve frontend requests.

Key Metrics (KPIs):
Vehicle counts by type (cars, trucks)

Average speeds

Historical trends & patterns

Road-level aggregation for clarity beyond individual sensors

📊 Key Features & User Interaction
For Citizens:
Real-time route condition awareness

Historical data reveals optimal travel times

For Urban Planners:
Data-driven insights into congestion patterns

Infrastructure impact assessment

For Officials:
Comprehensive traffic monitoring

Performance KPIs for city management

Dashboard Highlights:
Dynamic Maps: Color-coded traffic density (green → red)

Filters: Date range, vehicle type, KPI type

Animation: Explore temporal changes visually

Sub-Second Queries: Thanks to MongoDB’s geospatial indexing

🚀 Implementation & Deployment
Cloud-Native Architecture:
Containerized via CapRover

MongoDB hosted with regular backups and scaling

Streamlit app served via Docker, publicly available

Demo:
https://berlin-traffic-dashboard.huyhoangho.online

📈 Results & Impact
Achievements:
Made complex data accessible to non-technical users

Real-time & historical insights delivered interactively

Robust system handling Berlin-wide data with responsive performance

Stakeholder Benefits:
Citizens: Better-informed daily decisions

Planners: Evidence-based urban design

Officials: Transparent monitoring & reporting

🔮 Future Roadmap
Congestion prediction through machine learning

Expand coverage to Brandenburg

Mobile app for commuters

3D visualization integrating buildings & infrastructure

Public API for external integrations
