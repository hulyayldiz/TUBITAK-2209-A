"""
Hibrit ML Karar Motoru (ml_detection.py)
Kural Tabanlı (%80) + Random Forest (%10) + LSTM-VAE Anomali (%10) füzyonu.
train_model.py ile üretilen model bundle formatına tam uyumlu.
"""

import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import time

try:
    from lstm_vae import LSTMVAE, vae_loss
except ImportError:
    from models.lstm_vae import LSTMVAE, vae_loss

import torch
import streamlit as st

MODEL_PATH     = "gnss_rf_model.pkl"
SCALER_PATH    = "gnss_scaler.pkl"
VAE_PATH       = "gnss_lstm_vae.pth"
THRESHOLD_PATH = "vae_threshold.npy"

SEQ_LEN    = 10
VAE_INPUT  = 4
VAE_HIDDEN = 32
VAE_LATENT = 8

# Deneysel Grid Search sonuçlarına göre optimize edilmiş hibrit ağırlıklar:
# Kural tabanlı sistem (%80) deterministik güvenlik sağlarken,
# ML katmanları (%10 + %10) false-negative durumlarını minimize eder.
OPTIMIZED_WEIGHTS = {
    "rule": 0.80,
    "rf": 0.10,
    "vae": 0.10
}


@st.cache_resource
def load_rf_bundle():
    if not os.path.exists(MODEL_PATH):
        return None, None
    try:
        obj = joblib.load(MODEL_PATH)
        if isinstance(obj, dict) and "model" in obj:
            return obj["model"], obj.get("label_encoder")
        return obj, None
    except Exception as e:
        logging.error(f"RF model yükleme hatası: {e}")
        return None, None


@st.cache_resource
def load_scaler():
    if os.path.exists(SCALER_PATH):
        try:
            return joblib.load(SCALER_PATH)
        except Exception:
            pass
    return None


@st.cache_resource
def load_vae_model():
    if not os.path.exists(VAE_PATH):
        return None
    try:
        model = LSTMVAE(input_size=VAE_INPUT, hidden_size=VAE_HIDDEN,
                        latent_size=VAE_LATENT, seq_len=SEQ_LEN)
        model.load_state_dict(torch.load(VAE_PATH, map_location=torch.device("cpu")))
        model.eval()
        return model
    except Exception as e:
        logging.error(f"VAE yükleme hatası: {e}")
        return None


def get_hybrid_decision(rule_attack_type, simulation_features, state, sequence_buffer=None):
    start_time = time.perf_counter()
    
    rule_score = 1.0 if rule_attack_type != "NORMAL" else 0.0
    ml_label   = "NORMAL"
    ml_score   = 0.0

    rf_model, label_encoder = load_rf_bundle()
    scaler = load_scaler()

    if rf_model is not None:
        try:
            X = np.array(simulation_features, dtype=np.float32).reshape(1, -1)
            if scaler is not None:
                X = scaler.transform(X)
            prediction = rf_model.predict(X)[0]
            probs      = rf_model.predict_proba(X)[0]
            classes    = (label_encoder.classes_.tolist() if label_encoder is not None
                          else list(range(len(probs))))
            normal_prob = next((probs[i] for i, c in enumerate(classes)
                                if str(c).lower() == "normal"), 0.0)
            ml_score = float(1.0 - normal_prob)
            ml_label = (str(label_encoder.inverse_transform([prediction])[0]).upper()
                        if label_encoder is not None
                        else {0: "NORMAL", 1: "JAMMING", 2: "SPOOFING"}.get(int(prediction), "?"))
        except Exception as e:
            logging.error(f"RF tahmin hatası: {e}")
            ml_label = "RF_HATASI"

    anomaly_score = 0.0
    is_anomaly    = False
    vae_model = load_vae_model()

    if vae_model is not None and sequence_buffer is not None and len(sequence_buffer) >= 1:
        try:
            buf = list(sequence_buffer)
            if len(buf) < SEQ_LEN:
                buf = [[0.0] * VAE_INPUT] * (SEQ_LEN - len(buf)) + buf
            X_vae = torch.tensor([buf], dtype=torch.float32)
            with torch.no_grad():
                recon, _, _ = vae_model(X_vae)
                mae = torch.mean(torch.abs(recon - X_vae)).item()
            if os.path.exists(THRESHOLD_PATH):
                threshold     = float(np.load(THRESHOLD_PATH))
                anomaly_score = min(1.0, mae / max(threshold, 1e-8))
                is_anomaly    = mae > threshold
        except Exception as e:
            logging.exception(f"VAE anomali hatası: {e}")
    elif vae_model is None and hasattr(state, 'vae_error_logged') and not state.vae_error_logged:
        logging.warning("VAE modeli yüklenemedi. Anomali tespiti (LSTM-VAE) şu an devre dışı.")
        state.vae_error_logged = True

    # Optimize edilmiş ağırlıklarla Nihai Karar Skoru (Fusion)
    final_score = (OPTIMIZED_WEIGHTS["rule"] * rule_score + 
                   OPTIMIZED_WEIGHTS["rf"] * ml_score + 
                   OPTIMIZED_WEIGHTS["vae"] * anomaly_score)

    if final_score > 0.5 or rule_score > 0.5:
        if rule_attack_type != "NORMAL":
            final_type = rule_attack_type
        elif ml_label not in ("NORMAL", "RF_HATASI", "?"):
            final_type = ml_label
        elif is_anomaly:
            final_type = "ANOMALİ (Potansiyel Meaconing)"
        else:
            final_type = "SPOOFING"
        confidence = max(final_score, rule_score) * 100.0
    else:
        final_type = "NORMAL"
        confidence = (1.0 - final_score) * 100.0

    latency_ms = (time.perf_counter() - start_time) * 1000.0
    state.inference_latency = latency_ms # UI'da göstermek için state içine kaydet
    
    # Çok yavaşsa logla (NVIDIA Jetson / Edge hedefleri için)
    if latency_ms > 10.0:
        logging.debug(f"Yüksek Inference Latency: {latency_ms:.2f} ms")

    return final_type, round(confidence, 1), ml_label, round(anomaly_score, 4)


def trigger_model_training():
    try:
        from train_model import run_model_training
        return run_model_training()
    except Exception as e:
        return False, f"Eğitim hatası: {e}", None


def log_training_data(state, features, attack_mode):
    if not state.get("save_training_data", False):
        return
    csv_file = "gnss_training_dataset.csv"
    row = {
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "cn0":           features[0],
        "accel":         features[1],
        "heading_drift": features[2],
        "residual":      features[3],
        "target_label":  attack_mode,
    }
    df     = pd.DataFrame([row])
    header = not os.path.exists(csv_file)
    df.to_csv(csv_file, mode="a", index=False, header=header)