"""Per-observation detector, navigation and metric pipeline."""

from typing import NamedTuple

import config
from detection import calculate_metrics, run_firewall_rules
from features import extract_features
from ml_detection import get_hybrid_decision, log_training_data
from navigation import process_navigation


class ObservationResult(NamedTuple):
    """Values needed by the Streamlit presentation after one sensor sample."""

    decision: str
    reason: str
    confidence: float | None
    model_label: str
    anomaly_score: float
    latitude: float
    longitude: float
    speed: float
    metrics: tuple


def process_observation(state, observation, dt, firewall_settings):
    """Evaluate one normalized observation without rendering UI elements."""
    raw_lat, raw_lon, raw_speed, raw_cn0 = observation
    conf_cn0, conf_accel, conf_heading, fw_active = firewall_settings

    physical_decision, reason = run_firewall_rules(
        state, raw_lat, raw_lon, raw_cn0, raw_speed, config.NOMINAL_CN0,
        conf_cn0, conf_accel, conf_heading, dt=dt)
    features = extract_features(state, raw_lat, raw_lon, raw_speed, raw_cn0, dt=dt)

    # Dataset ground truth is reserved for evaluation and never enters training.
    if (not state.get("use_live_gps", False) and not state.get("use_dataset_mode", False)
            and state.get("cn0_available", True)):
        label = ("SPOOFING" if state.attack_mode in ("slow_spoofing", "stealth_spoofing")
                 else state.attack_mode.upper())
        log_training_data(state, features, label)

    state.residuals_history.append(features[3])
    if len(state.residuals_history) > 30:
        state.residuals_history.pop(0)

    state.snr_history.append(raw_cn0)
    if len(state.snr_history) > 30:
        state.snr_history.pop(0)

    state.vae_buffer.append(features)
    if len(state.vae_buffer) > 10:
        state.vae_buffer.pop(0)

    decision, confidence, model_label, anomaly_score = get_hybrid_decision(
        physical_decision, features, state, state.vae_buffer)
    state.current_detector_decision = decision
    if decision != physical_decision:
        reason = (f"Hibrit tespit: {decision}" if confidence is None else
                  f"Hibrit tespit: {decision} (skor {confidence:.1f}; kalibre olasılık değil)")

    latitude, longitude, speed, decision, reason = process_navigation(
        state, raw_lat, raw_lon, raw_speed, raw_cn0, fw_active,
        conf_cn0, conf_accel, dt=dt, decision=(decision, reason))
    metrics = calculate_metrics(state, decision, raw_lat, raw_lon, latitude, longitude)

    return ObservationResult(
        decision, reason, confidence, model_label, anomaly_score,
        latitude, longitude, speed, metrics)
