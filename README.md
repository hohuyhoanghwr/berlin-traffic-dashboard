# BerliFlow: Interactive Berlin Traffic Visualization Dashboard  
**Enterprise Architecture for Big Data – Final Project**  
**HWR Berlin | July 2025**  
**Team:** Onat Arzoglu, Gökan Görer, Huy-Hoang Ho  

---

## 🚦 Project Overview  
BerliFlow bridges the gap between Berlin’s fragmented traffic data sources and the need for actionable, accessible urban mobility insights. By integrating Berlin’s open-source traffic measurements, OpenStreetMap geodata, and a lightweight Streamlit app, we provide a user-friendly dashboard that transforms complex traffic data into meaningful visualizations.

**Key Technologies:**  
- **MongoDB** (optimized for JSON / GeoJSON and geospatial queries)  
- **Python** (pandas, geopandas, shapely for processing)  
- **Streamlit** (interactive web-based dashboard)  
- **Containerized Cloud Deployment** (CapRover)  

---

## 🛑 Problem Statement & Motivation  
Berlin’s traffic data exists but is fragmented across city departments, published in technical formats that are not accessible to general users. Existing solutions lack integrated historical analysis or intuitive dashboards.

**Challenges Addressed:**  
- **Accessibility:** Non-technical users cannot easily interpret existing datasets.  
- **Temporal Limitations:** Existing tools lack robust historical exploration.  
- **Decision-Making Gaps:** Urban planners and officials lack consolidated, actionable insights.

**Our Solution:**  
A unified platform offering historical traffic data visualization, enabling insights through interactive, map-based filtering and temporal exploration.

---

## 🏗️ System Architecture  

### **Context Diagram**  
<img width="716" height="832" alt="image" src="https://github.com/user-attachments/assets/eecc678a-ce03-4b07-be18-b8e56d3c66ed" />

### **Container Diagram**  
<img width="1296" height="822" alt="image" src="https://github.com/user-attachments/assets/ff65b707-f31c-4b6d-878e-72a71fd40ec3" />


---

## 🧰 Technology Stack  

|**Component**  |**Technology**      | **Purpose**                         |
|---------------|--------------------|-------------------------------------|
| Backend       | Python             | Data integration, processing, APIs  |
| Database      | MongoDB            | JSON & GeoJSON, flexible geospatial data |
| Frontend      | Streamlit          | Interactive dashboards & filtering  |
| Map geodata   | OpenStreetMap API  | Base maps, district-level geometry  |
| Cloud         | CapRover / Docker  | Containerized deployment            |

**Why MongoDB?**  
Our data is JSON-based with heavy geospatial components (GeoJSON). The key advantage of MongoDB’s for our use case is its 2dsphere, which directly works with Berlin's data having spherical (Earth-like) coordinates (WGS84).
With PostGIS (extension of PostgreSQL), we would need to perform additional work of casting to geography type via SRID 4326, which also contains some probable risk of data precision within the transformation pipeline. 

---

## 🛣️ Data Sources & Structure  

**Data Origin:**  
- **Berlin Traffic Detection API** (Sensors: cars, trucks, speed, hourly granularity): https://api.viz.berlin.de/daten/verkehrsdetektion
- **OpenStreetMap** (Road network, districts)
```python
def load_osm_network(self):
    if os.path.exists(self.cache_path):
        print("📂 Loading cached Berlin road network...")
        G = ox.load_graphml(self.cache_path)
    else:
        print("🌐 Downloading Berlin road network from OpenStreetMap...")
        G = ox.graph_from_place(self.network_place, network_type='drive')
        ox.save_graphml(G, filepath=self.cache_path)
```

**Data Pipeline:**  
1. **Collect:** APIs deliver raw JSON data.  
2. **Enrich:** Merge traffic data with geographic road network.  
3. **Transform:** Convert to GeoJSON for MongoDB ingestion.  
4. **Serve:** Backend queries serve frontend requests.  

**Key Metrics (KPIs):**  
- Vehicle counts by type (cars, trucks)  
- Average speeds  
- Historical trends & patterns  
- Road-level aggregation for clarity beyond individual sensors  

---

## 📊 Key Features & User Interaction  

### **For Citizens:**  
- Intuitive visualization of traffic conditions in interested route
- Historical data reveals optimal travel times  

### **For Urban Planners:**  
- Data-driven insights into congestion patterns  
- Infrastructure impact assessment  

### **For Officials:**  
- Comprehensive traffic monitoring  
- Performance KPIs for city management  

### **Dashboard Highlights:**  
- **Dynamic Maps:** Color-coded traffic density (green → red)  
- **Filters:** Date range, vehicle type, KPI type  
- **Animation:** Explore temporal changes visually  
- **Sub-Second Queries:** Thanks to MongoDB’s 2dsphere index - directly applies to geodadata with spherical (Earth-like) coordinates (WGS84) - which is our case

---

## 🚀 Implementation & Deployment

**Cloud-Native Architecture:**  
- Containerized via CapRover  
- MongoDB hosted with regular backups and scaling  
- Streamlit app served via Docker, publicly available  

**Demo:**  
[https://berlin-traffic-dashboard.huyhoangho.online](https://berlin-traffic-dashboard.huyhoangho.online)

---

## 📈 Results & Impact  

**Achievements:**  
- Made complex data accessible to non-technical users  
- Historical insights delivered interactively  
- Robust system handling Berlin-wide data with responsive performance  

**Stakeholder Benefits:**  
- **Citizens:** Better-informed daily decisions  
- **Planners:** Evidence-based urban design  
- **Officials:** Transparent monitoring & reporting  

---

## 🔮 Future Roadmap  
- Congestion prediction through machine learning  
- Expand coverage to Brandenburg
- Expand data coverage to cover further time range
- Develop detailed dashboards to deliver district- and street-level insights
- Mobile app for commuters  
- 3D visualization integrating buildings & infrastructure  
- Public API for external integrations  

---

## Team Contribution
|**Task**                                    |**Member in charge**|
|--------------------------------------------|--------------------|
| Data extraction, processing & enrichment   | Gökan Görer + Huy-Hoang Ho|
| Map buiding                                | Huy-Hoang Ho|
| Cloud deployment - Database & App          | Onat Arzoglu + Huy-Hoang Ho|
| Presentation & Documentation               | All members|
