# src/utils/helpers.py
import yaml
import os
from math import radians, sin, cos, sqrt, atan2

def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        # Default to config/config.yaml relative to project root
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../config/config.yaml")
    
    # Normalize path to ensure consistency
    config_path = os.path.abspath(config_path)
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def haversine_distance(coords1: tuple, coords2: tuple) -> float:
    """Calculate Haversine distance between two (lat, lon) points in kilometers."""
    if not (coords1 and coords2):
        return 100.0  # Default fallback distance
    lat1, lon1 = map(radians, coords1)
    lat2, lon2 = map(radians, coords2)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    R = 6371  # Earth radius in km
    return R * c

def get_node_coords(node_attrs: dict) -> tuple:
    """Extract coordinates from node attributes."""
    if "latitude" in node_attrs and "longitude" in node_attrs:
        return (node_attrs["latitude"], node_attrs["longitude"])
    return None