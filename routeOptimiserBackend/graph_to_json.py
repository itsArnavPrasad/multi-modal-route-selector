import networkx as nx
import pickle
import json
import numpy as np
from src.utils.helpers import load_config, get_node_coords

# Function to parse numeric value from string with unit
def parse_numeric(value, default='N/A'):
    if value is None or value == 'N/A':
        return 'N/A'
    try:
        # Extract numeric part (assumes format like "299 km" or "8 hr")
        if isinstance(value, str):
            numeric_part = ''.join(filter(str.isdigit, value.split()[0]))
            return float(numeric_part) if numeric_part else 'N/A'
        return float(value)  # If already numeric
    except (ValueError, IndexError, TypeError):
        return 'N/A'

config = load_config()
with open("data/processed/transport_graph.pkl", 'rb') as f:
    G = pickle.load(f)

# Extract node and edge data
nodes = []
for node in G.nodes:
    coords = get_node_coords(G.nodes[node])
    lat, lon = coords if coords else (np.random.uniform(-90, 90), np.random.uniform(-180, 180))
    nodes.append({
        'id': node,
        'lat': float(lat),
        'lon': float(lon),
        'type': G.nodes[node].get('type', 'custom'),
        'country': G.nodes[node].get('country', 'N/A'),
        'city': G.nodes[node].get('city', 'N/A')
    })

edges = []
for u, v, data in G.edges(data=True):
    edges.append({
        'source': u,
        'target': v,
        'mode': data.get('mode', 'unknown'),
        'distance': parse_numeric(data.get('distance', 'N/A')),
        'time': parse_numeric(data.get('time', 'N/A'))
    })

# Save to JSON
with open('graph_data.json', 'w') as f:
    json.dump({'nodes': nodes, 'edges': edges}, f)
print("Graph data saved as 'graph_data.json'")