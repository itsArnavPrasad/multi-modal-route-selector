import os
from googlemaps import Client

def load_api_key(filepath="data/external/google_routes_api_key.txt"):
    try:
        with open(filepath, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise Exception("API key file not found. Please provide it in data/external/.")

def initialize_gmaps_client():
    api_key = load_api_key()
    return Client(key=api_key)

def fetch_road_routes(origin, destination):
    gmaps = initialize_gmaps_client()
    directions = gmaps.directions(origin, destination, mode="driving")
    if directions:
        route = directions[0]["legs"][0]
        return {
            "distance_km": route["distance"]["value"] / 1000,  # Convert meters to km
            "time_hours": route["duration"]["value"] / 3600,   # Convert seconds to hours
        }
    return None

# Example usage
if __name__ == "__main__":
    route_data = fetch_road_routes("Port A", "Port B")
    print(route_data)