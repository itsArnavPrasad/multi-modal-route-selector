# src/utils/validators.py
import logging
import logging.config
import yaml
import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Set up logging with fallback
try:
    with open("config/logging_config.yaml", "r") as f:
        config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)
except (FileNotFoundError, ValueError) as e:
    logging.basicConfig(level=logging.INFO)
    logging.warning(f"Failed to load logging config: {e}. Using basic configuration.")
logger = logging.getLogger("validators")

def validate_inputs(initial_coords, final_coords, max_days, weights, weight, volume):
    """
    Validate user inputs for the route selector.
    
    Args:
        initial_coords (tuple): (latitude, longitude) of start.
        final_coords (tuple): (latitude, longitude) of end.
        max_days (float, optional): Maximum allowed time in days.
        weights (list): [time, cost, emissions, customs] weights.
        weight (float): Shipment weight in tons.
        volume (float): Shipment volume in cubic meters.
    
    Returns:
        list: Validated weights (defaults if None).
    
    Raises:
        ValueError: If inputs are invalid.
    """
    # Validate coordinates
    try:
        lat1, lon1 = initial_coords
        lat2, lon2 = final_coords
        if not (-90 <= lat1 <= 90 and -180 <= lon1 <= 180 and -90 <= lat2 <= 90 and -180 <= lon2 <= 180):
            logger.error(f"Invalid coordinates: initial={initial_coords}, final={final_coords}")
            raise ValueError("Coordinates must be within valid ranges: latitude [-90, 90], longitude [-180, 180]")
    except (TypeError, ValueError) as e:
        logger.error(f"Coordinates format error: {e}")
        raise ValueError("Coordinates must be tuples of (latitude, longitude)")

    # Validate max_days
    if max_days is not None:
        try:
            max_days = float(max_days)
            if max_days <= 0:
                logger.error(f"Invalid max_days: {max_days}")
                raise ValueError("Max Days must be positive if provided")
        except (TypeError, ValueError):
            logger.error(f"Max_days must be a number: {max_days}")
            raise ValueError("Max Days must be a positive number")

    # Validate weights
    if weights is None:
        logger.info("No weights provided; using default [0.25, 0.25, 0.25, 0.25]")
        weights = [0.25, 0.25, 0.25, 0.25]
    else:
        try:
            weights = [float(w) for w in weights]
            if len(weights) != 4 or abs(sum(weights) - 1) > 0.01 or any(w < 0 for w in weights):
                logger.error(f"Invalid weights: {weights}")
                raise ValueError("Weights must be a list of 4 non-negative numbers summing to approximately 1")
        except (TypeError, ValueError):
            logger.error(f"Weights format error: {weights}")
            raise ValueError("Weights must be a list of 4 numbers")

    # Validate weight and volume
    try:
        weight = float(weight)
        volume = float(volume)
        if weight <= 0 or volume <= 0:
            logger.error(f"Invalid weight or volume: weight={weight}, volume={volume}")
            raise ValueError("Weight and volume must be positive")
    except (TypeError, ValueError):
        logger.error(f"Weight or volume format error: weight={weight}, volume={volume}")
        raise ValueError("Weight and volume must be positive numbers")

    logger.info("Inputs validated successfully.")
    return weights

if __name__ == "__main__":
    # Example usage
    try:
        weights = validate_inputs((40.7128, -74.0060), (51.5074, -0.1278), 5, [0.4, 0.3, 0.2, 0.1], 10, 50)
        print(f"Validated weights: {weights}")
    except ValueError as e:
        print(f"Validation error: {e}")