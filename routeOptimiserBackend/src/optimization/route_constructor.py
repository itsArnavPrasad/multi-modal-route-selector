# src/optimization/route_constructor.py
import logging
import logging.config
import yaml
from src.utils.geocoding import GeocodingUtils
import os

os.makedirs("logs", exist_ok=True)
try:
    with open("config/logging_config.yaml", "r") as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
except FileNotFoundError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
logger = logging.getLogger("route_constructor")

class RouteConstructor:
    def __init__(self, G, config):
        self.G = G
        self.config = config
        self.geo_utils = GeocodingUtils()

    def add_road_segment(self, coords, node, weight_kg):
        node_coords = self.geo_utils.get_node_coords(self.G.nodes[node])
        if not node_coords:
            logger.warning(f"No coordinates for {node}; assuming zero-distance road segment.")
            return {"distance": 0, "time": 0, "cost_per_km": 0, "border_cost": 0, "emissions": 0, "mode": "road", "total_cost": 0}
        
        distance = self.geo_utils.haversine_distance(coords, node_coords)
        time = distance / self.config["defaults"]["fallback_speed_km_h"]
        cost_per_km = self.config["defaults"]["road_cost_per_km"]
        emission_factor = self.config["defaults"].get("road_emission_factor", 169)
        emissions = distance * emission_factor * (weight_kg / 1000) / 1000  # g CO₂ to tons
        
        total_cost = cost_per_km * distance  # Distance-based cost for roads
        logger.debug(f"Added road segment: {coords} -> {node} | Distance: {distance:.2f} km, Time: {time:.2f} h, Total Cost: ${total_cost:.2f}")
        return {
            "distance": distance,
            "time": time,
            "cost_per_km": cost_per_km,
            "border_cost": 0,
            "emissions": emissions,
            "mode": "road",
            "total_cost": total_cost
        }

    def construct_full_routes(self, core_routes, initial_coords, final_coords, weight_kg, max_days):
        full_routes = []
        start_node = f"Custom_{initial_coords[0]}_{initial_coords[1]}_Start"
        end_node = f"Custom_{final_coords[0]}_{final_coords[1]}_End"

        for core_path, core_metrics in core_routes:
            if not core_path:
                continue
            
            # Initial road segment
            start_edge = self.G.get_edge_data(start_node, core_path[0], default=None)
            if not start_edge or "distance" not in start_edge[0] or start_edge[0]["distance"] == 0 or "time" not in start_edge[0] or start_edge[0]["time"] == 0:
                start_edge = self.add_road_segment(initial_coords, core_path[0], weight_kg)
                logger.debug(f"Added dynamic road (or recalculated due to invalid edge): {start_node} -> {core_path[0]}")
            else:
                start_edge = start_edge[0]
                if start_edge["mode"] == "road":
                    distance = start_edge.get("distance", 0)
                    start_edge["total_cost"] = (start_edge.get("cost_per_km", self.config["defaults"]["road_cost_per_km"]) * distance + 
                                                start_edge.get("border_cost", 0))
                else:
                    start_edge["total_cost"] = (start_edge.get("transportation_cost_per_kg", 0) * weight_kg + 
                                                start_edge.get("border_cost", 0))
                logger.debug(f"Using pre-existing start edge: {start_node} -> {core_path[0]} | {start_edge}")

            # Final road segment
            end_edge = self.G.get_edge_data(core_path[-1], end_node, default=None)
            if not end_edge or "distance" not in end_edge[0] or end_edge[0]["distance"] == 0 or "time" not in end_edge[0] or end_edge[0]["time"] == 0:
                end_edge = self.add_road_segment(final_coords, core_path[-1], weight_kg)
                logger.debug(f"Added dynamic road (or recalculated due to invalid edge): {core_path[-1]} -> {end_node}")
            else:
                end_edge = end_edge[0]
                if end_edge["mode"] == "road":
                    distance = end_edge.get("distance", 0)
                    end_edge["total_cost"] = (end_edge.get("cost_per_km", self.config["defaults"]["road_cost_per_km"]) * distance + 
                                              end_edge.get("border_cost", 0))
                else:
                    end_edge["total_cost"] = (end_edge.get("transportation_cost_per_kg", 0) * weight_kg + 
                                              end_edge.get("border_cost", 0))
                logger.debug(f"Using pre-existing end edge: {core_path[-1]} -> {end_node} | {end_edge}")

            # Core route cost and time breakdown
            cost_breakdown = {}
            time_breakdown = {}
            core_cost = 0
            for i in range(len(core_path) - 1):
                edge_data = self.G[core_path[i]][core_path[i+1]][0]
                if edge_data["mode"] == "road":
                    distance = edge_data.get("distance", 0)
                    segment_cost = (edge_data.get("cost_per_km", self.config["defaults"]["road_cost_per_km"]) * distance + 
                                    edge_data.get("border_cost", 0))
                else:
                    segment_cost = (edge_data.get("transportation_cost_per_kg", 0) * weight_kg + 
                                    edge_data.get("border_cost", 0))
                core_cost += segment_cost
                cost_breakdown[f"{core_path[i]} -> {core_path[i+1]}"] = segment_cost
                time_breakdown[f"{core_path[i]} -> {core_path[i+1]}"] = edge_data.get("time", 0)

            # Total metrics
            total_time = core_metrics["time"] + start_edge["time"] + end_edge["time"]
            if total_time / 24 > max_days:
                logger.debug(f"Route {start_node} -> {' -> '.join(core_path)} -> {end_node} exceeds {max_days} days: {total_time/24:.2f}")
                continue

            total_cost = core_cost + start_edge["total_cost"] + end_edge["total_cost"]
            total_emissions = core_metrics["emissions"] + start_edge["emissions"] + end_edge["emissions"]
            total_customs = (core_metrics["customs"] + 
                             self.G.nodes[core_path[0]].get("customs_score", 0) + 
                             self.G.nodes[end_node].get("customs_score", 0))

            # Add breakdown for start and end segments
            cost_breakdown[f"{start_node} -> {core_path[0]}"] = start_edge["total_cost"]
            cost_breakdown[f"{core_path[-1]} -> {end_node}"] = end_edge["total_cost"]
            time_breakdown[f"{start_node} -> {core_path[0]}"] = start_edge["time"]
            time_breakdown[f"{core_path[-1]} -> {end_node}"] = end_edge["time"]

            full_path = [start_node] + core_path + [end_node]
            modes = [start_edge["mode"]] + [self.G[core_path[i]][core_path[i+1]][0]["mode"] for i in range(len(core_path)-1)] + [end_edge["mode"]]
            full_routes.append((full_path, modes, {"time": total_time, "cost": total_cost, "emissions": total_emissions, "customs": total_customs}, cost_breakdown, time_breakdown))
            # logger.info(
            #     f"Constructed route: {' -> '.join(full_path)} | "
            #     f"Time: {total_time/24:.2f} days, "
            #     f"Cost: ${total_cost:,.2f}, "
            #     f"Emissions: {total_emissions/1000:.2f} Kg CO₂"
            # )

        logger.info(f"Total full routes constructed: {len(full_routes)}")
        return full_routes

    def rank_routes(self, routes, weights):
        ranked = []
        for path, modes, metrics, cost_breakdown, time_breakdown in routes:
            score = sum(w * metrics[k] for w, k in zip(weights, ["time", "cost", "emissions", "customs"]))
            ranked.append((score, path, modes, metrics, cost_breakdown, time_breakdown))
        ranked.sort(key=lambda x: x[0])
        logger.info(f"Ranked {len(ranked)} routes.")
        return ranked[:10]

if __name__ == "__main__":
    pass