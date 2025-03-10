# 🚛 Multi-Modal Cross-Border Route Selector

### 🏆 **Winner of LogiTHON 2025**  
*A logistics optimization tool developed by Team Fusion Flow at IIT Bombay*

---

## 📌 Problem Statement  
A small logistics provider needs a **fast and efficient** way to determine the best cross-border shipping route using **air, sea, land**, or their **combinations**.  
Our tool **analyzes shipment details** and suggests **optimal routes** based on:  
- **Cost**  
- **Transit Time**  
- **Feasibility** 
- **Emissions** 
- **Or A Mix Of Them**

---

## 👥 Team Fusion Flow  
🔹 **Anmol Sureka**  
🔹 **Arnav Prasad**  
🔹 **Neepun Nandan**  
🎓 **IIT Bombay**

---

## 🎯 Objectives  
✅ Gather **clean transport data**  
✅ Optimize **cross-border routes**  
✅ Balance **cost, time, emissions, and logistics scores**  
✅ Provide a **user-friendly interface** for route mapping  
✅ Adapt dynamically to **real-world constraints**  

---

## 📊 Data Collection & Sources  
We collected real-world logistics data from multiple sources:  

🔹 **Seaports & Airports**  
- 71 Major Seaports  
- 105 Major Airports  
- 1932 Sea Routes (scraped from *sea-distances.org*)  
- 10,920 Air Routes (scraped from *travelmath.com*)  

🔹 **Trade & Logistics Data**  
- Customs Scores, Port Dwell Times (*WTO*)  
- Logistics Scores, Import/Export Tariffs (*World Bank*)  
- Real-time shipping costs from *Freightos FBX Index*  

🔹 **Road Routing**  
- Haversine Distance Calculation  
- **Google Maps API** Integration for Real-World Routes  

---

## 🔧 Data Pre-Processing  
Before modeling, we ensured:  
✅ **Data Cleaning & Deduplication**  
✅ **Standardized Location Names**  
✅ **Carbon Emission Calculations**  
✅ **Dynamic Real-World Data Integration**  

---

## 🛠️ Graph-Based Modeling  
We built a **fully connected logistics network** using **NetworkX** in Python.  

🔹 **Nodes** (Seaports, Airports, Cities)  
🔹 **Edges** (Connections with distance, transit time, cost, emissions, logistics score)  
🔹 **Extended Graph** (Includes neighboring countries without trade restrictions)  

📈 **Graph Visualization**: Displays all possible routes & rankings  

---

## 🔍 Multi-Objective A* Search Algorithm  
To determine the **best** shipping route, we implemented a **multi-objective** A* search:  

**f*(n) = g*(n) + h(n)**  
- **h(n)** → Haversine distance heuristic  
- **g*(n)** → Weighted sum of cost, time, emissions, and logistics score  

✅ **Balances cost, time, and emissions** based on user priorities  
✅ **Computationally efficient** for large networks  
✅ **Searches various routes dynamically**  

---

## 🖥️ User Interface  
💡 **Features**  
✔ **Ranked Routes** with detailed metrics  
✔ **Google Maps API** for start & end coordinates  
✔ **Weight & Volume Constraints**  
✔ **Eco-Friendly Routing Options**  
✔ **Optimized for Perishable Goods**  

---

## 🏗️ Tech Stack  
🗂️ **Data Sources & APIs**  
📊 **Graph Representation & Mathematical Modeling**  
📌 **User Interface & Visualization**  

---

## 🚀 Features  
✅ **Custom Rule Integration**  
✅ **Real-Time Cost Estimation**  
✅ **Smart Route Suggestions**  
✅ **User-Friendly Dashboard with Visualizations**  
✅ **Sustainable Routing to Reduce Carbon Emissions**  
✅ **Adapts to User Priorities**  

---

## 📜 How to Run the Project  

### 🛠 **Backend Setup**  
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 main.py
```

### 🌍 **Frontend Setup**  
```bash
cd frontend
# Create .env file with Google API Key
echo 'REACT_APP_GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"' > .env
echo 'VITE_GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"' >> .env
npm install
npm run dev
```

🔗 **Go to:** `http://localhost:5173/` to run the project.

---

## 📢 Acknowledgments  
Special thanks to **IIT Bombay IEOR Department**, **Softlink Global Pvt. Ltd.**, and **AllMasters** for organizing LogiTHON 2025! 🎉

---

🚀 *Built for the Future of Logistics* 🚀  
📌 **By Team Fusion Flow**
