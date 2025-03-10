# src/modeling/optimize_route.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))  # Add project root to path

import networkx as nx
import pickle
import logging
from typing import List, Dict
from src.utils.helpers import load_config, haversine_distance, get_node_coords

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_graph(graph_path: str) -> nx.MultiDiGraph:
    """Load the prebuilt NetworkX MultiDiGraph from a pickle file."""
    if not os.path.exists(graph_path):
        logger.error(f"Graph file not found at {graph_path}")
        raise FileNotFoundError(f"Graph file not found at {graph_path}")
    
    try:
        with open(graph_path, "rb") as f:
            G = pickle.load(f)
        logger.info(f"Graph loaded from {graph_path} with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
        return G
    except Exception as e:
        logger.error(f"Failed to load graph from {graph_path}: {e}")
        raise

def a_star_initial_path(G: nx.MultiDiGraph, start: str, goal: str, weight_priority: str = "time") -> List[str]:
    """Find an initial feasible path using A* search with a Haversine heuristic."""
    if start not in G.nodes:
        logger.error(f"Start node {start} not found in graph.")
        raise KeyError(f"Start node {start} not found in graph.")
    if goal not in G.nodes:
        logger.error(f"Goal node {goal} not found in graph.")
        raise KeyError(f"Goal node {goal} not found in graph.")

    def heuristic(n1: str, n2: str) -> float:
        """Heuristic: Haversine distance divided by mode-specific speed."""
        coords1 = get_node_coords(G.nodes[n1])
        coords2 = get_node_coords(G.nodes[n2])
        if not coords1 or not coords2:
            logger.warning(f"Missing coordinates for {n1} or {n2}. Using default heuristic of 0.")
            return 0.0
        distance_km = haversine_distance(coords1, coords2)
        modes = {data["mode"] for _, _, data in G.edges(n1, data=True)} if G.edges(n1) else {"road"}
        if "air" in modes:
            speed = 800  # km/h for air
        elif "sea" in modes:
            speed = 40   # km/h for sea
        else:
            speed = 60   # km/h for road/intermodal
        return distance_km / speed

    def get_edge_cost(u: str, v: str, data: Dict) -> float:
        """Calculate edge cost based on priority weight."""
        if weight_priority == "time":
            return data.get("time", 0.0)
        elif weight_priority == "cost":
            return data.get("cost", 0.0)
        elif weight_priority == "emissions":
            return data.get("emissions", 0.0)
        else:
            logger.warning(f"Invalid weight_priority '{weight_priority}'. Defaulting to time.")
            return data.get("time", 0.0)

    try:
        path = nx.astar_path(
            G,
            source=start,
            target=goal,
            heuristic=heuristic,
            weight=get_edge_cost
        )
        
        total_time = sum(G[u][v][0]["time"] for u, v in zip(path[:-1], path[1:]))
        total_cost = sum(G[u][v][0]["cost"] for u, v in zip(path[:-1], path[1:]))
        total_emissions = sum(G[u][v][0]["emissions"] for u, v in zip(path[:-1], path[1:]))
        
        logger.info(f"A* Path found: {' -> '.join(path)}")
        logger.info(f"Total Time: {total_time:.2f} hours, Cost: {total_cost:.2f} USD, Emissions: {total_emissions:.2f} kg CO₂")
        return path
    
    except nx.NetworkXNoPath:
        logger.error(f"No path exists between {start} and {goal}.")
        logger.info(f"Edges from start: {list(G.edges(start, data=True))}")
        logger.info(f"Edges to goal: {list(G.edges(goal, data=True))}")
        raise nx.NetworkXNoPath(f"No path exists between {start} and {goal}.")
    except Exception as e:
        logger.error(f"A* search failed: {e}")
        raise

def main():
    """Main function to demonstrate A* pathfinding."""
    config = load_config()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    graph_path = os.path.join(project_root, config["data"]["processed_dir"], config["graph"]["output_file"])
    
    G = load_graph(graph_path)
    start_node = "Custom_19.0760_72.8777_general"  # New York
    goal_node = "Custom_51.5074_-0.1278_general"   # London
    initial_path = a_star_initial_path(G, start_node, goal_node, weight_priority="time")
    return initial_path

if __name__ == "__main__":
    initial_path = main()
    print("Initial Path:", initial_path)