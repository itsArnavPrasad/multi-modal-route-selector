# src/utils/geocoding.py
import logging
import logging.config
import yaml
import os
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Set up logging
try:
    with open("config/logging_config.yaml", "r") as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
except (FileNotFoundError, ValueError) as e:
    logging.basicConfig(level=logging.INFO)
    logging.warning(f"Failed to load logging config: {e}. Using basic configuration.")
logger = logging.getLogger("geocoding")

class GeocodingUtils:
    def __init__(self):
        try:
            self.geolocator = Nominatim(user_agent="fusionflow_logithon")
            self.geocode = RateLimiter(self.geolocator.geocode, min_delay_seconds=1)
            logger.info("Nominatim geocoder initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Nominatim: {e}")
            self.geolocator = None
            self.geocode = None

    def haversine_distance(self, coords1, coords2):
        import math
        lat1, lon1 = coords1
        lat2, lon2 = coords2
        R = 6371  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def get_node_coords(self, node_data):
        """
        Extract coordinates from node attributes.
        
        Args:
            node_data (dict): Node attributes from the graph (e.g., G.nodes[node]).
        
        Returns:
            tuple: (latitude, longitude) or None if not found.
        """
        try:
            lat = node_data.get("latitude")
            lon = node_data.get("longitude")
            if lat is not None and lon is not None:
                return (float(lat), float(lon))
            logger.debug(f"No coordinates found in node data: {node_data}")
            return None
        except Exception as e:
            logger.error(f"Error extracting coordinates from node data {node_data}: {e}")
            return None

if __name__ == "__main__":
    utils = GeocodingUtils()
    # Example usage
    coords1 = (40.7128, -74.0060)  # New York
    coords2 = (51.5074, -0.1278)   # London
    distance = utils.haversine_distance(coords1, coords2)
    print(f"Distance: {distance:.2f} km")