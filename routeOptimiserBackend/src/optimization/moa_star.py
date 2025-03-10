# src/optimization/moa_star.py
import logging
import logging.config
import yaml
from heapq import heappush, heappop
from src.utils.geocoding import GeocodingUtils
import os

os.makedirs("logs", exist_ok=True)
try:
    with open("config/logging_config.yaml", "r") as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
except FileNotFoundError:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moa_star")

class MOAStar:
    def __init__(self, G):
        self.G = G
        self.geo_utils = GeocodingUtils()

    def dominates(self, cost1, cost2):
        return all(c1 <= c2 for c1, c2 in zip(cost1, cost2)) and any(c1 < c2 for c1, c2 in zip(cost1, cost2))

    def heuristic(self, node, goal, weights):
        """
        Heuristic function estimating the cost from node to goal.
        
        Args:
            node (str): Current node ID.
            goal (str): Goal node ID.
            weights (list): Weights for [time, cost, emissions, customs].
        
        Returns:
            float: Weighted heuristic score.
        """
        node_coords = self.geo_utils.get_node_coords(self.G.nodes[node])
        goal_coords = self.geo_utils.get_node_coords(self.G.nodes[goal])
        
        if not node_coords or not goal_coords:
            logger.debug(f"Using zero heuristic for {node} -> {goal} due to missing coordinates.")
            return 0
        
        distance_km = self.geo_utils.haversine_distance(node_coords, goal_coords)
        # Estimate time (hours) using a fast speed (e.g., plane at 800 km/h)
        time_h = distance_km / 800
        # Estimate cost (USD) using a low cost per kg (e.g., 0.01 USD/kg) * 1000 kg
        cost = distance_km * 0.01 * 1000
        # Estimate emissions (g CO₂) using a low emission factor (e.g., 10 g/tonne-km) * 1000 kg
        emissions = distance_km * 10 * 1000 / 1000  # Convert to kg
        # Estimate customs as minimal (e.g., 1)
        customs = 1
        
        heuristic_costs = (time_h, cost, emissions, customs)
        return sum(w * c for w, c in zip(weights, heuristic_costs))

    def moa_star(self, start, goal, weights, weight_kg, max_days):
        if start not in self.G or goal not in self.G:
            logger.warning(f"Start {start} or goal {goal} not in graph.")
            return None, None
        
        open_set = [(0, start, [start], (0, 0, 0, 0))]  # (f_score, node, path, costs: time, cost, emissions, customs)
        closed_set = set()
        pareto_frontier = {}

        while open_set:
            f_score, current, path, costs = heappop(open_set)
            if current in closed_set:
                continue

            if current == goal:
                total_time_days = costs[0] / 24
                if total_time_days <= max_days:
                    logger.debug(f"Valid path found: {path}, Costs: {costs}")
                    return path, {"time": costs[0], "cost": costs[1], "emissions": costs[2], "customs": costs[3]}
                else:
                    logger.debug(f"Path to {goal} exceeds max_days: {total_time_days} > {max_days}")
                    continue

            closed_set.add(current)
            for neighbor, edge_data_dict in self.G[current].items():
                for edge_key, edge_data in edge_data_dict.items():
                    if neighbor in closed_set:
                        continue
                    
                    new_time = costs[0] + edge_data["time"]
                    if new_time / 24 > max_days:
                        logger.debug(f"Skipping {current} -> {neighbor}: Time {new_time/24:.2f} days exceeds {max_days}.")
                        continue
                    
                    new_cost = costs[1] + (edge_data["transportation_cost_per_kg"] + edge_data["border_cost"]) * weight_kg
                    new_emissions = costs[2] + edge_data["emissions"] * weight_kg / 1000
                    new_customs = costs[3] + self.G.nodes[neighbor].get("customs_score", 0)
                    new_costs = (new_time, new_cost, new_emissions, new_customs)

                    if neighbor in pareto_frontier:
                        if any(self.dominates(existing_costs, new_costs) for existing_costs in pareto_frontier[neighbor]):
                            continue
                        pareto_frontier[neighbor] = [c for c in pareto_frontier[neighbor] if not self.dominates(new_costs, c)]
                        pareto_frontier[neighbor].append(new_costs)
                    else:
                        pareto_frontier[neighbor] = [new_costs]

                    new_path = path + [neighbor]
                    g_score = sum(w * c for w, c in zip(weights, new_costs))
                    h_score = self.heuristic(neighbor, goal, weights)
                    f_score = g_score + h_score
                    heappush(open_set, (f_score, neighbor, new_path, new_costs))

        logger.info(f"No valid path found from {start} to {goal} within {max_days} days.")
        return None, None

if __name__ == "__main__":
    # Example usage would go here
    pass