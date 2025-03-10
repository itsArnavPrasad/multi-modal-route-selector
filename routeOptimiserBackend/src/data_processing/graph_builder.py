# src/data_processing/graph_builder.py
import pandas as pd
import networkx as nx
import os
import pickle
import logging
import logging.config
import yaml
import re
from googlemaps import Client
from googlemaps.exceptions import ApiError
from src.utils.geocoding import GeocodingUtils

# Set up logging
try:
    with open("config/logging_config.yaml", "r") as f:
        config = yaml.safe_load(f.read())
    # Delete existing log file(s) if defined in the configuration
    for handler in config.get("handlers", {}).values():
        if "filename" in handler:
            log_file = handler["filename"]
            if os.path.exists(log_file):
                os.remove(log_file)
    logging.config.dictConfig(config)
except FileNotFoundError:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graph_builder")
class GraphBuilder:
    def __init__(self, config):
        self.config = config
        self.raw_nodes_dir = config["data"]["raw_nodes_dir"]
        self.raw_edges_dir = config["data"]["raw_edges_dir"]
        self.processed_dir = config["data"]["processed_dir"]
        self.cache_dir = config["data"]["cache_dir"]
        
        try:
            with open(os.path.join(config["data"]["external_dir"], config["api"]["google_routes_key_file"]), "r") as f:
                self.gmaps = Client(key=f.read().strip())
            logger.info("Google Maps API key loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load Google Maps API key: {e}. Using fallback methods.")
            self.gmaps = None
        
        self.G = nx.MultiDiGraph()
        self.iata_to_city = {}
        self.node_coords = {}
        self.geo_utils = GeocodingUtils()

    def parse_time_to_hours(self, time_val):
        if pd.isna(time_val):
            logger.warning(f"Invalid time '{time_val}'. Using default {self.config['defaults']['fallback_time_hours']} hours.")
            return float(self.config["defaults"]["fallback_time_hours"])
        if isinstance(time_val, (int, float)):
            return float(time_val)
        time_str = str(time_val)
        try:
            days = hours = minutes = 0
            day_match = re.search(r"(\d+\.?\d*)\s*days?", time_str, re.IGNORECASE)
            hour_match = re.search(r"(\d+\.?\d*)\s*hours?", time_str, re.IGNORECASE)
            min_match = re.search(r"(\d+\.?\d*)\s*minutes?", time_str, re.IGNORECASE)
            if day_match:
                days = float(day_match.group(1))
            if hour_match:
                hours = float(hour_match.group(1))
            if min_match:
                minutes = float(min_match.group(1))
            return days * 24 + hours + (minutes / 60)
        except Exception as e:
            logger.warning(f"Error parsing time '{time_str}': {e}. Using default.")
            return float(self.config["defaults"]["fallback_time_hours"])

    def parse_distance_to_km(self, distance_val):
        if pd.isna(distance_val):
            logger.warning(f"Invalid distance '{distance_val}'. Using default {self.config['defaults']['fallback_distance_km']} km.")
            return float(self.config["defaults"]["fallback_distance_km"])
        if isinstance(distance_val, (int, float)):
            return float(distance_val)
        distance_str = str(distance_val)
        try:
            return float(re.sub(r'\s*km$', '', distance_str.strip(), flags=re.IGNORECASE))
        except Exception as e:
            logger.warning(f"Error parsing distance '{distance_str}': {e}. Using default.")
            return float(self.config["defaults"]["fallback_distance_km"])

    def load_data(self):
        try:
            nodes = {
                "seaports": pd.read_csv(os.path.join(self.raw_nodes_dir, "seaports.csv")),
                "airports": pd.read_csv(os.path.join(self.raw_nodes_dir, "airports.csv"))
            }
            edges = {
                "ships": pd.read_csv(os.path.join(self.raw_edges_dir, "ships.csv")),
                "flights": pd.read_csv(os.path.join(self.raw_edges_dir, "flights.csv")),
                "seaport_airport_connect": pd.read_csv(os.path.join(self.raw_edges_dir, "seaport_airport_connect.csv")),
                "trade": pd.read_csv(os.path.join(self.raw_edges_dir, "trade.csv")),
                "logistics": pd.read_csv(os.path.join(self.raw_edges_dir, "logistics.csv")),
                "carbon_emission": pd.read_csv(os.path.join(self.raw_edges_dir, "carbon_emission.csv")),
                "trade_neighbour": pd.read_csv(os.path.join(self.raw_edges_dir, "trade_neighbour.csv"))
            }
            logger.debug(f"ships.csv columns: {edges['ships'].columns.tolist()}")
            logger.debug(f"flights.csv columns: {edges['flights'].columns.tolist()}")
            logger.debug(f"seaport_airport_connect.csv columns: {edges['seaport_airport_connect'].columns.tolist()}")
        except FileNotFoundError as e:
            logger.error(f"Data file missing: {e}")
            raise

        edges["ships"]["Time"] = edges["ships"]["Time"].apply(self.parse_time_to_hours)
        edges["seaport_airport_connect"]["Time"] = edges["seaport_airport_connect"]["Time"].apply(self.parse_time_to_hours)
        edges["flights"]["Flight_Time_Minutes"] = edges["flights"]["Flight_Time_Minutes"].apply(lambda x: self.parse_time_to_hours(x) / 60)

        for _, row in nodes["airports"].iterrows():
            if pd.notna(row["IATA"]):
                self.iata_to_city[row["IATA"]] = (row["Country"], row["City"])
                self.node_coords[f"{row['Country']}_{row['City']}_Airport"] = (float(row["Latitude"]), float(row["Longitude"]))

        logger.info("Data loaded and preprocessed.")
        return nodes, edges

    def build_nodes(self, nodes_data, logistics_data):
        logistics_dict = logistics_data.set_index("Country").to_dict(orient="index")

        for _, row in nodes_data["seaports"].iterrows():
            node_id = f"{row['Country']}_{row['City']}_Seaport"
            attrs = {
                "country": row["Country"], 
                "city": row["City"], 
                "type": "seaport",
            }
            if "Latitude" in row and "Longitude" in row and pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
                attrs["latitude"] = float(row["Latitude"])
                attrs["longitude"] = float(row["Longitude"])
            if row["Country"] in logistics_dict:
                attrs.update({
                    "customs_score": logistics_dict[row["Country"]].get("Customs Score", 3.0),
                    "mean_port_dwell_time": logistics_dict[row["Country"]].get("Mean Port Dwell Time (days)", 2.0) * 24,
                    "mean_turnaround_time": logistics_dict[row["Country"]].get("Mean Turnaround Time at Port (days)", 1.0) * 24
                })
            else:
                attrs.update({"customs_score": 3.0, "mean_port_dwell_time": 48, "mean_turnaround_time": 24})
            self.G.add_node(node_id, **attrs)

        for _, row in nodes_data["airports"].iterrows():
            node_id = f"{row['Country']}_{row['City']}_Airport"
            attrs = {
                "country": row["Country"], 
                "city": row["City"], 
                "type": "airport",
            }
            if "Latitude" in row and "Longitude" in row and pd.notna(row["Latitude"]) and pd.notna(row["Longitude"]):
                attrs["latitude"] = float(row["Latitude"])
                attrs["longitude"] = float(row["Longitude"])
            self.G.add_node(node_id, **attrs)

        logger.info(f"Added {self.G.number_of_nodes()} nodes.")

    def add_edge_if_unique(self, from_node, to_node, mode, distance, time, transportation_cost_per_kg, border_cost, emissions, **extra_attrs):
        if from_node not in self.G:
            logger.warning(f"Skipping edge {from_node} -> {to_node}; node missing. {from_node}")
            return
        if to_node not in self.G:
            logger.warning(f"Skipping edge {from_node} -> {to_node}; node missing. {to_node}")
            return
        
        if self.G.has_edge(from_node, to_node):
            for edge_key, edge_data in self.G[from_node][to_node].items():
                if edge_data["mode"] == mode:
                    existing_score = edge_data["transportation_cost_per_kg"] + edge_data["border_cost"] + edge_data["time"]
                    new_score = transportation_cost_per_kg + border_cost + time
                    if new_score < existing_score:
                        self.G[from_node][to_node][edge_key].update(
                            distance=distance, time=time, transportation_cost_per_kg=transportation_cost_per_kg,
                            border_cost=border_cost, emissions=emissions, **extra_attrs
                        )
                        logger.debug(f"Updated edge {from_node} -> {to_node} (mode: {mode}) with better attributes.")
                    else:
                        logger.debug(f"Skipped duplicate edge {from_node} -> {to_node} (mode: {mode}); existing is better.")
                    return
        
        self.G.add_edge(from_node, to_node, mode=mode, distance=distance, time=time,
                        transportation_cost_per_kg=transportation_cost_per_kg, border_cost=border_cost,
                        emissions=emissions, **extra_attrs)
        logger.debug(f"Added edge {from_node} -> {to_node} (mode: {mode})")

    def add_intermodal_edges(self):
        for node in self.G.nodes(data=True):
            if node[1]["type"] == "seaport":
                airport_node = f"{node[1]['country']}_{node[1]['city']}_Airport"
                if airport_node in self.G:
                    dwell_time = node[1].get("mean_port_dwell_time", self.config["defaults"]["dwell_time"])
                    self.add_edge_if_unique(node[0], airport_node, mode="intermodal", distance=0, time=dwell_time,
                                            transportation_cost_per_kg=0, border_cost=0, emissions=0)
                    self.add_edge_if_unique(airport_node, node[0], mode="intermodal", distance=0, time=dwell_time,
                                            transportation_cost_per_kg=0, border_cost=0, emissions=0)

    def build_edges(self, edges_data):
        trade_dict = edges_data["trade"].set_index("Country").to_dict(orient="index")
        carbon_dict = edges_data["carbon_emission"].set_index("Mode of Transport")["Emission Factor (g CO₂/tonne-km)"].to_dict()
        trade_neighbour_dict = {}


        for _, row in edges_data["trade_neighbour"].iterrows():
            country = row["Country"]
            neighbors = row["Trade_Neighbors_Country"]
            if pd.isna(neighbors):
                trade_neighbour_dict[country] = []
                logger.debug(f"Country {country} has no trade neighbors (NaN).")
            elif neighbors == "None":
                trade_neighbour_dict[country] = []
                logger.debug(f"Country {country} has no trade neighbors (None).")
            else:
                trade_neighbour_dict[country] = neighbors.split(";")
                logger.debug(f"Country {country} trade neighbors: {trade_neighbour_dict[country]}")

        def get_border_costs(country_a, country_b):
            if country_a == country_b:
                return 0
            export_cost = trade_dict.get(country_a, {}).get("Cost to export: Border compliance (USD)", self.config["defaults"]["border_cost"])
            import_cost = trade_dict.get(country_b, {}).get("Cost to import: Border compliance (USD)", self.config["defaults"]["border_cost"])
            return float(export_cost) + float(import_cost)

        for _, row in edges_data["ships"].iterrows():
            node_a = f"{row['Country_A']}_{row['Port_A']}_Seaport"
            node_b = f"{row['Country_B']}_{row['Port_B']}_Seaport"
            distance = self.parse_distance_to_km(row["Distance"])
            time = row["Time"] + self.G.nodes.get(node_b, {}).get("mean_port_dwell_time", 0)
            
            # Attempt to read Price_Per_kg from the row
            try:
                cost_per_kg = float(row["Price_Per_kg"])
                # Log the value for verification
                # logger.info(f"Sea route {node_a} -> {node_b}: cost_per_kg = {cost_per_kg}")
            except KeyError:
                # Handle missing 'Price_Per_kg' column
                logger.warning(f"'Price_Per_kg' column missing in ships.csv for route {node_a} -> {node_b}. Using default sea freight cost.")
                cost_per_kg = self.config["defaults"].get("sea_cost_per_kg", 0.05)  # Use a sea-specific default, fallback to 0.05
            except ValueError as e:
                # Handle invalid (non-numeric) 'Price_Per_kg' values
                logger.warning(f"Invalid 'Price_Per_kg' value '{row.get('Price_Per_kg')}' for route {node_a} -> {node_b}: {e}. Using default sea freight cost.")
                cost_per_kg = self.config["defaults"].get("sea_cost_per_kg", 0.05)  # Use a sea-specific default, fallback to 0.05
            
            border_cost = get_border_costs(row["Country_A"], row["Country_B"])
            self.add_edge_if_unique(node_a, node_b, mode="sea", distance=distance, time=time,
                                    transportation_cost_per_kg=cost_per_kg, border_cost=border_cost,
                                    emissions=distance * carbon_dict["Sea Freight"], route=row["Route"])

        for _, row in edges_data["flights"].iterrows():
            from_city = self.iata_to_city.get(row["From_IATA"], (row["From_Country"], row["From_IATA"]))[1]
            to_city = self.iata_to_city.get(row["To_IATA"], (row["To_Country"], row["To_IATA"]))[1]
            node_a = f"{row['From_Country']}_{from_city}_Airport"
            node_b = f"{row['To_Country']}_{to_city}_Airport"
            distance = self.parse_distance_to_km(row["Distance_km"])
            time = row["Flight_Time_Minutes"]
            cost_per_kg = float(row["Cost_Per_Kg"])
            border_cost = get_border_costs(row["From_Country"], row["To_Country"])
            self.add_edge_if_unique(node_a, node_b, mode="air", distance=distance, time=time,
                                    transportation_cost_per_kg=cost_per_kg, border_cost=border_cost,
                                    emissions=distance * carbon_dict["Air Freight"])


        for _, row in edges_data["seaport_airport_connect"].iterrows():
            node_a = f"{row['Port_Country']}_{row['Port_City']}_Seaport"
            node_b = f"{row['Port_Country']}_{row['City']}_Airport"
            distance = self.parse_distance_to_km(row["Distance"])
            time = row["Time"]
            cost_per_kg = float(row["Cost_USD"]) / 1000
            border_cost = get_border_costs(row["Port_Country"], row["Port_Country"])
            self.add_edge_if_unique(node_a, node_b, mode="road", distance=distance, time=time,
                                    transportation_cost_per_kg=cost_per_kg, border_cost=border_cost,
                                    emissions=distance * carbon_dict["Road Freight"])

        for country, neighbors in trade_neighbour_dict.items():
            for neighbor in neighbors:
                neighbor = neighbor.strip()
                country_nodes = [n for n in self.G.nodes() if n.startswith(f"{country}_")]
                neighbor_nodes = [n for n in self.G.nodes() if n.startswith(f"{neighbor}_")]
                for n1 in country_nodes:
                    for n2 in neighbor_nodes:
                        if n1 == n2 or "latitude" not in self.G.nodes[n1] or "latitude" not in self.G.nodes[n2]:
                            continue
                        distance = self.geo_utils.haversine_distance(
                            (self.G.nodes[n1]["latitude"], self.G.nodes[n1]["longitude"]),
                            (self.G.nodes[n2]["latitude"], self.G.nodes[n2]["longitude"])
                        )
                        if distance > self.config["defaults"]["max_road_distance_km"]:
                            continue
                        time = distance / self.config["defaults"]["fallback_speed_km_h"]
                        cost_per_kg = self.config["defaults"]["road_cost_per_km"]
                        border_cost = get_border_costs(country, neighbor)
                        self.add_edge_if_unique(n1, n2, mode="road", distance=distance, time=time,
                                                transportation_cost_per_kg=cost_per_kg, border_cost=border_cost,
                                                emissions=distance * carbon_dict["Road Freight"])

        self.add_intermodal_edges()
        logger.info(f"Added {self.G.number_of_edges()} edges.")

    def add_dynamic_road(self, start_location, end_location, start_country, end_country):
        carbon_factor = self.load_data()[1]["carbon_emission"].set_index("Mode of Transport")["Emission Factor (g CO₂/tonne-km)"].to_dict()["Road Freight"]

        def find_nearest_nodes(location, country_hint):
            min_dist_seaport = min_dist_airport = float("inf")
            nearest_seaport = nearest_airport = None
            for node, data in self.G.nodes(data=True):
                if "latitude" in data and data["country"] == country_hint:
                    dist = self.geo_utils.haversine_distance(location, (data["latitude"], data["longitude"]))
                    if data["type"] == "seaport" and dist < min_dist_seaport:
                        min_dist_seaport = dist
                        nearest_seaport = node
                    elif data["type"] == "airport" and dist < min_dist_airport:
                        min_dist_airport = dist
                        nearest_airport = node
            return nearest_seaport, nearest_airport

        start_node = f"Custom_{start_location[0]}_{start_location[1]}_Start"
        end_node = f"Custom_{end_location[0]}_{end_location[1]}_End"
        
        if start_node not in self.G:
            self.G.add_node(start_node, country="Unknown", city="Custom", type="start",
                            latitude=start_location[0], longitude=start_location[1])
            self.node_coords[start_node] = start_location
            logger.info(f"Added custom node {start_node}")
        if end_node not in self.G:
            self.G.add_node(end_node, country="Unknown", city="Custom", type="end",
                            latitude=end_location[0], longitude=end_location[1])
            self.node_coords[end_node] = end_location
            logger.info(f"Added custom node {end_node}")

        # Use the user-supplied countries instead of hardcoded values:
        start_seaport, start_airport = find_nearest_nodes(start_location, start_country)
        end_seaport, end_airport = find_nearest_nodes(end_location, end_country)

        for nearest in [start_seaport, start_airport]:
            if nearest:
                distance = self.geo_utils.haversine_distance(start_location, (self.G.nodes[nearest]["latitude"], self.G.nodes[nearest]["longitude"]))
                time = distance / self.config["defaults"]["fallback_speed_km_h"]
                cost_per_kg = self.config["defaults"]["road_cost_per_km"]
                self.add_edge_if_unique(start_node, nearest, mode="road", distance=distance, time=time,
                                        transportation_cost_per_kg=cost_per_kg, border_cost=0,
                                        emissions=distance * carbon_factor)
                self.add_edge_if_unique(nearest, start_node, mode="road", distance=distance, time=time,
                                        transportation_cost_per_kg=cost_per_kg, border_cost=0,
                                        emissions=distance * carbon_factor)

        for nearest in [end_seaport, end_airport]:
            if nearest:
                distance = self.geo_utils.haversine_distance(end_location, (self.G.nodes[nearest]["latitude"], self.G.nodes[nearest]["longitude"]))
                time = distance / self.config["defaults"]["fallback_speed_km_h"]
                cost_per_kg = self.config["defaults"]["road_cost_per_km"]
                self.add_edge_if_unique(end_node, nearest, mode="road", distance=distance, time=time,
                                        transportation_cost_per_kg=cost_per_kg, border_cost=0,
                                        emissions=distance * carbon_factor)
                self.add_edge_if_unique(nearest, end_node, mode="road", distance=distance, time=time,
                                        transportation_cost_per_kg=cost_per_kg, border_cost=0,
                                        emissions=distance * carbon_factor)

    def save_graph(self):
        output_path = os.path.join(self.processed_dir, self.config.get("graph", {}).get("output_file", "transport_graph.pkl"))
        os.makedirs(self.processed_dir, exist_ok=True)
        with open(output_path, "wb") as f:
            pickle.dump(self.G, f)
        logger.info(f"Graph saved to {output_path} with {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges.")

    def build(self, start_location=None, end_location=None, start_country=None, end_country=None):
        nodes_data, edges_data = self.load_data()
        self.build_nodes(nodes_data, edges_data["logistics"])
        self.build_edges(edges_data)
        if start_location and end_location:
            self.add_dynamic_road(start_location, end_location, start_country, end_country)
        self.save_graph()
        return self.G


if __name__ == "__main__":
    from src.utils.helpers import load_config
    config = load_config()
    builder = GraphBuilder(config)
    start = (40.7128, -74.0060)  # New York
    end = (51.5074, -0.1278)     # London
    G = builder.build(start, end)
