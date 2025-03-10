# src/modeling/optimize_road_segments.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import networkx as nx
import pickle
import logging
from typing import List
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from src.utils.helpers import load_config, get_node_coords

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_graph(graph_path: str) -> nx.MultiDiGraph:
    with open(graph_path, "rb") as f:
        G = pickle.load(f)
    logger.info(f"Graph loaded with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    return G

def extract_road_subgraph(G: nx.MultiDiGraph, start: str, end: str) -> List[str]:
    """Extract nodes forming a road segment using shortest path."""
    try:
        road_nodes = nx.shortest_path(G, start, end, weight="distance")
        logger.info(f"Extracted road nodes: {road_nodes}")
        return road_nodes
    except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
        logger.warning(f"No road path from {start} to {end}: {e}")
        return [start, end]

def optimize_road_segment(G: nx.MultiDiGraph, nodes: List[str], start: str, end: str) -> List[str]:
    """Optimize a road segment using OR-Tools VRP."""
    if len(nodes) < 2:
        return nodes

    # Initialize routing model with start node as depot
    manager = pywrapcp.RoutingIndexManager(len(nodes), 1, nodes.index(start))  # 1 vehicle, start depot
    routing = pywrapcp.RoutingModel(manager)

    # Define distance callback
    def distance_callback(from_index, to_index):
        from_node = nodes[manager.IndexToNode(from_index)]
        to_node = nodes[manager.IndexToNode(to_index)]
        try:
            return int(G[from_node][to_node][0].get("distance", 0) * 1000)  # meters
        except KeyError:
            return 999999  # Large penalty if no edge

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Ensure vehicle ends at 'end' node
    end_index = manager.NodeToIndex(nodes.index(end))
    routing.AddPickupAndDelivery(0, end_index)  # Start (0) must reach end
    routing.solver().Add(routing.VehicleVar(end_index) == 0)  # Vehicle 0 ends at end_index

    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.time_limit.seconds = 5

    # Solve
    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(nodes[node_index])
            index = solution.Value(routing.NextVar(index))
        if route[-1] != end:
            route.append(end)
        logger.info(f"Optimized road segment: {route}")
        return route
    else:
        logger.warning(f"No VRP solution found. Returning original nodes.")
        return nodes

def refine_path_with_road_segments(G: nx.MultiDiGraph, path: List[str]) -> List[str]:
    """Refine an RL path by optimizing road segments."""
    refined_path = []
    i = 0
    while i < len(path) - 1:
        start, end = path[i], path[i + 1]
        if "general" in start or "general" in end:
            road_nodes = extract_road_subgraph(G, start, end)
            optimized_nodes = optimize_road_segment(G, road_nodes, start, end)
            refined_path.extend(optimized_nodes[:-1])  # Avoid duplicating end
        else:
            refined_path.append(start)
        i += 1
    refined_path.append(path[-1])
    return refined_path

def main():
    config = load_config()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    graph_path = os.path.join(project_root, config["data"]["processed_dir"], config["graph"]["output_file"])
    G = load_graph(graph_path)

    # RL path from your last output
    rl_path = [
        "Custom_40.7128_-74.006_general", "United States_New York & New Jersey_seaport",
        "Vietnam_Saigon_seaport", "Sri Lanka_Colombo_seaport",
        "India_Bombay_seaport", "France_Marseilles_seaport"
    ]

    # Refine the path
    refined_path = refine_path_with_road_segments(G, rl_path)
    logger.info(f"Original RL Path: {' -> '.join(rl_path)}")
    logger.info(f"Refined Path: {' -> '.join(refined_path)}")

    # Visualize
    from src.visualization.visualize_graph import visualize_paths
    visualize_paths(G, [rl_path, refined_path], "Original vs Refined RL Path")

if __name__ == "__main__":
    main()