"""Versioned, label-free feature extraction used by training and inference."""
import math
from sensors import calculate_distance_km

FEATURE_SCHEMA = "motion-v2"


def extract_features(state, lat, lon, speed, cn0, dt=.5):
    if dt <= 0:
        raise ValueError("dt must be positive")
    heading = math.radians(state.get("prev_heading", 0.0))
    distance = max(0.0, state.get("prev_speed", speed)) / 3.6 * dt
    previous_lat = state.get("prev_lat", lat)
    previous_lon = state.get("prev_lon", lon)
    predicted_lat = previous_lat + distance * math.cos(heading) / 111320
    predicted_lon = previous_lon + distance * math.sin(heading) / (111320 * math.cos(math.radians(previous_lat)))
    residual = calculate_distance_km(lat, lon, predicted_lat, predicted_lon) * 1000
    return [float(cn0), float(state.get("acceleration", 0.0)),
            float(state.get("heading_difference", 0.0)), float(residual)]
