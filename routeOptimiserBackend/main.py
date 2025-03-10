from flask import Flask, request, jsonify
from flask_cors import CORS
from src.data_processing.graph_builder import GraphBuilder
from src.optimization.moa_star import MOAStar
from src.optimization.route_constructor import RouteConstructor
from src.utils.validators import validate_inputs
from src.utils.helpers import load_config
import logging
import pandas as pd
from pathlib import Path

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

@app.route('/api/find-routes', methods=['POST'])
def find_routes():
    try:
        data = request.get_json()
        logger.info(f"Received request with data: {data}")

        # Extract and validate data
        start_lat = float(data['startLat'])
        start_lon = float(data['startLon'])
        start_country = data['initialCountry']
        end_lat = float(data['endLat'])
        end_lon = float(data['endLon'])
        end_country = data['finalCountry']
        max_days = float(data['maxDays']) if data['maxDays'] and data['maxDays'] != '' else 500
        weight = float(data['weight']) / 1000 if data['weight'] is not None else 0  # kg to tons
        volume = float(data['volume']) if data['volume'] is not None else 0  # m³
        optimization_type = data['optimizationType']
        custom_weights = data.get('customWeights', {})

        start_coords = (start_lat, start_lon)
        end_coords = (end_lat, end_lon)

        # Load configuration and build graph
        config = load_config()
        builder = GraphBuilder(config)
        logger.info("Starting graph construction...")
        G = builder.build(start_coords, end_coords, start_country, end_country)
        logger.info("Graph construction completed.")

        # Determine optimization weights
        if weight > 10 or volume > 400:
            weights = [0.1, 0.9, 0, 0]  # Heavy load
        elif optimization_type == "time":
            weights = [1, 0, 0, 0]
        elif optimization_type == "cost":
            weights = [0, 1, 0, 0]
        elif optimization_type == "emissions":
            weights = [0, 0, 1, 0]
        elif optimization_type == "logisticsScore":
            weights = [0.5, 0.0, 0.0, 0.5]
        elif optimization_type == "customWeights":
            weights = [
                custom_weights.get('time', 0.25),
                custom_weights.get('cost', 0.25),
                custom_weights.get('emissions', 0.25),
                custom_weights.get('logisticsScore', 0.25)
            ]

        # Validate inputs
        logger.info("Validating inputs...")
        validate_inputs(start_coords, end_coords, max_days, weights, weight, volume)
        logger.info("Inputs validated successfully.")

        # Initialize components
        moa = MOAStar(G)
        constructor = RouteConstructor(G, config)
        logger.info("Loading trade neighbors CSV...")
        trade_df = pd.read_csv(Path(__file__).parent / "data" / "raw" / "edges" / "trade_neighbour.csv")
        logger.info("Trade neighbors CSV loaded successfully.")

        # Get neighboring countries with safety checks
        neighbors_series_start = trade_df.loc[
            trade_df["Country"].str.lower() == start_country.lower(), "Trade_Neighbors_Country"
        ]
        neighbors_start = (
            [nbr.strip() for nbr in neighbors_series_start.values[0].split(";")]
            if not neighbors_series_start.empty and isinstance(neighbors_series_start.values[0], str) and neighbors_series_start.values[0].strip().lower() != "none"
            else []
        )
        countries_to_include_start = [start_country] + neighbors_start

        neighbors_series_end = trade_df.loc[
            trade_df["Country"].str.lower() == end_country.lower(), "Trade_Neighbors_Country"
        ]
        neighbors_end = (
            [nbr.strip() for nbr in neighbors_series_end.values[0].split(";")]
            if not neighbors_series_end.empty and isinstance(neighbors_series_end.values[0], str) and neighbors_series_end.values[0].strip().lower() != "none"
            else []
        )
        countries_to_include_end = [end_country] + neighbors_end

        # Identify nodes
        initial_nodes = [
            n for n in G.nodes()
            if any(n.startswith(f"{country}_") for country in countries_to_include_start)
        ]
        final_nodes = [
            n for n in G.nodes()
            if any(n.startswith(f"{country}_") for country in countries_to_include_end)
        ]
        logger.info(f"Initial nodes: {len(initial_nodes)}, Final nodes: {len(final_nodes)}")

        # Find core routes
        core_routes = []
        for start in initial_nodes:
            for goal in final_nodes:
                path, metrics = moa.moa_star(start, goal, weights, weight * 1000, max_days)
                if path:
                    core_routes.append((path, metrics))
        logger.info(f"Found {len(core_routes)} core routes.")

        # Construct and rank routes
        logger.info("Constructing full routes...")
        full_routes = constructor.construct_full_routes(core_routes, start_coords, end_coords, weight * 1000, max_days)
        logger.info("Ranking routes...")
        ranked_routes = constructor.rank_routes(full_routes, weights)

        # Format response
        routes_response = []
        for i, (score, path, modes, metrics, cost_breakdown, time_breakdown) in enumerate(ranked_routes[:10], 1):
            time_days = metrics["time"] / 24
            route_data = {
                "rank": i,
                "score": round(score, 2),
                "time_days": round(time_days, 2),
                "cost": round(metrics["cost"], 2),
                "emissions": round(metrics["emissions"] / 1000, 2),
                "path": path,
                "modes": modes,
                "cost_breakdown": {k: round(v, 2) for k, v in cost_breakdown.items()},
                "time_breakdown": {k: round(v / 24, 2) for k, v in time_breakdown.items()}
            }
            routes_response.append(route_data)

        logger.info("Routes computed successfully.")
        return jsonify({"status": "success", "routes": routes_response}), 200

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)