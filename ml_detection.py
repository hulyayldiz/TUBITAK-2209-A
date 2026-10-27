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
import uuid

try:
    from lstm_vae import LSTMVAE
except ImportError:
    from models.lstm_vae import LSTMVAE

import torch
from artifact_io import artifact_cache

MODEL_PATH     = "gnss_rf_model.pkl"
SCALER_PATH    = "gnss_scaler.pkl"
VAE_PATH       = "gnss_lstm_vae.pth"
THRESHOLD_PATH = "vae_threshold.npy"

SEQ_LEN    = 10
VAE_INPUT  = 4
VAE_HIDDEN = 32
VAE_LATENT = 8

from features import FEATURE_SCHEMA
import config as _cfg

@artifact_cache(MODEL_PATH, SCALER_PATH)
def load_rf_bundle():
    if not os.path.exists(MODEL_PATH):
        return None, None
    try:
        obj = joblib.load(MODEL_PATH)
        if isinstance(obj, dict) and "model" in obj:
            if obj.get("feature_schema") != FEATURE_SCHEMA:
                logging.error("RF özellik şeması eski; modeli yeniden eğitin.")
                return None, None
            obj["model"].n_jobs = 1
            if "scaler" in obj:
                obj["model"]._embedded_scaler = obj["scaler"]
            return obj["model"], obj.get("label_encoder")
        logging.error("Unsupported RF artifact; versioned bundle required")
        return None, None
    except Exception as e:
        logging.error(f"RF model yükleme hatası: {e}")
        return None, None


@artifact_cache(MODEL_PATH, SCALER_PATH)
def load_scaler():
    if os.path.exists(MODEL_PATH):
        try:
            bundle = joblib.load(MODEL_PATH)
            if isinstance(bundle, dict) and "scaler" in bundle:
                return bundle["scaler"]
        except Exception:
            pass
    if os.path.exists(SCALER_PATH):
        try:
            return joblib.load(SCALER_PATH)
        except Exception:
            pass
    return None


@artifact_cache(VAE_PATH)
def load_vae_model():
    if not os.path.exists(VAE_PATH):
        return None
    try:
        model = LSTMVAE(input_size=VAE_INPUT, hidden_size=VAE_HIDDEN,
                        latent_size=VAE_LATENT, seq_len=SEQ_LEN)
        checkpoint = torch.load(VAE_PATH, map_location="cpu", weights_only=True)
        if "state_dict" not in checkpoint or checkpoint.get("feature_schema") != FEATURE_SCHEMA:
            logging.error("VAE normalizasyon bilgisi eksik; modeli yeniden eğitin.")
            return None
        model.load_state_dict(checkpoint["state_dict"])
        model.feature_mean = np.asarray(checkpoint["mean"], dtype=np.float32)
        model.feature_std = np.asarray(checkpoint["std"], dtype=np.float32)
        model.anomaly_threshold = float(checkpoint["threshold"])
        model.persistence_samples = checkpoint.get("persistence_samples", 3)
        model.persistence_seconds = checkpoint.get("persistence_seconds", 1.5)
        if (not isinstance(model.persistence_samples, int) or not 3 <= model.persistence_samples <= 100
                or not isinstance(model.persistence_seconds, (int, float))
                or not np.isfinite(model.persistence_seconds) or not 0 < model.persistence_seconds <= 50):
            raise ValueError("Invalid VAE confirmation metadata")
        if (model.feature_mean.shape != (VAE_INPUT,) or model.feature_std.shape != (VAE_INPUT,)
                or not np.isfinite(model.feature_mean).all() or not np.isfinite(model.feature_std).all()
                or not (model.feature_std > 0).all() or not np.isfinite(model.anomaly_threshold)
                or model.anomaly_threshold <= 0):
            raise ValueError("Invalid VAE preprocessing metadata")
        model.eval()
        return model
    except Exception as e:
        logging.error(f"VAE yükleme hatası: {e}")
        return None


def get_hybrid_decision(rule_attack_type, simulation_features, state, sequence_buffer=None):
    start_time = time.perf_counter()
    # A static GRID receiver has clock observables but no vehicle dynamics.
    # Use its separately calibrated observation contract, rather than treating
    # synthetic moving-vehicle RF/VAE scores as validated attack probabilities.
    profile_name = str(state.get('receiver_profile_name', ''))
    if (state.get('use_dataset_mode', False) and
            (profile_name in ('texbat-grid-static-v1', 'grid-unvalidated', 'receiver-unvalidated')
             or profile_name.startswith('receiver:'))):
        from receiver_profile import receiver_decision
        result = (receiver_decision(state, float(simulation_features[0]))
                  if profile_name == 'texbat-grid-static-v1' or profile_name.startswith('receiver:') else
                  dict(available=False, detected=False, status='unavailable',
                       reason='Bu alıcı/kullanım için doğrulanmış profil yok; fiziksel kurallar çalışıyor.'))
        if profile_name == 'texbat-grid-static-v1':
            from code_carrier import decision as code_carrier_decision
            cmc = code_carrier_decision(state, state.dataset_df.iloc[state.dataset_index-1])
            result['code_carrier'] = cmc
            if cmc['detected']:
                result['detected'], result['status'] = True, 'alarm'
                result['detection_paths'] = result.get('detection_paths', [])+['code_carrier_inconsistency']
        state.receiver_profile_result = result
        state.ml_source = 'TEXBAT_RECEIVER_PROFILE' if profile_name in ('texbat-grid-static-v1', 'grid-unvalidated') else 'RECEIVER_PROFILE'
        state.rf_available = state.vae_available = False
        state.rf_confirmed = state.vae_detected = False
        state.rf_attack_score = 0.
        state.rf_anomaly_streak = state.vae_anomaly_streak = 0
        state.hybrid_fresh_evidence = bool(
            (rule_attack_type != 'NORMAL' and state.get('rule_fresh_evidence', True))
            or result['detected'])
        final = (rule_attack_type if rule_attack_type != 'NORMAL' else
                 'ANOMALİ (Alıcı tutarsızlığı)' if result['detected'] else 'NORMAL')
        state.inference_latency = (time.perf_counter()-start_time)*1000
        # This detector returns a categorical anomaly decision, not a calibrated
        # probability. Do not manufacture a confidence percentage for the UI.
        return final, None, 'ALICI_PROFILI', float(result['detected'])
    
    rule_score = 1.0 if rule_attack_type != "NORMAL" else 0.0
    ml_label   = "NORMAL"
    ml_score   = 0.0

    channels_available = (state.get("cn0_available", True) and np.asarray(simulation_features).shape == (4,)
                          and np.isfinite(np.asarray(simulation_features, dtype=float)).all())
    rf_model, label_encoder = load_rf_bundle() if channels_available else (None, None)
    scaler = (getattr(rf_model, "_embedded_scaler", None) if rf_model is not None else None)
    if scaler is None and channels_available:
        scaler = load_scaler()

    if rf_model is not None:
        try:
            X = np.array(simulation_features, dtype=np.float32).reshape(1, -1)
            if scaler is not None:
                X = scaler.transform(X)
            probs = rf_model.predict_proba(X)[0]
            prediction = rf_model.classes_[int(np.argmax(probs))]
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

    state.ml_source = "GNSS_RF" if rf_model is not None else "unavailable"
    if not channels_available and state.get("kinematic_features") is not None:
        from domain_model import av_probabilities, load_av_model
        bundle = load_av_model()
        probabilities = av_probabilities([state.kinematic_features], bundle) if bundle is not None else None
        if probabilities is not None:
            ml_score = float(probabilities[0])
            ml_label = "SPOOFING" if ml_score >= bundle["threshold"] else "NORMAL"
            rf_model = bundle["model"]
            state.ml_source = "AV_KINEMATIC_RF"

    anomaly_score = 0.0
    is_anomaly    = False
    vae_model = load_vae_model() if channels_available else None

    if vae_model is not None and sequence_buffer is not None and len(sequence_buffer) >= SEQ_LEN:
        try:
            buf = np.asarray(list(sequence_buffer)[-SEQ_LEN:], dtype=np.float32)
            buf = (buf - vae_model.feature_mean) / vae_model.feature_std
            X_vae = torch.tensor(buf[None, ...], dtype=torch.float32)
            with torch.no_grad():
                recon, _, _ = vae_model(X_vae)
                mae = torch.mean(torch.abs(recon - X_vae)).item()
            threshold = getattr(vae_model, "anomaly_threshold", None)
            if threshold is None and os.path.exists(THRESHOLD_PATH):
                threshold = float(np.load(THRESHOLD_PATH))
            if threshold is not None:
                anomaly_score = min(1.0, mae / max(threshold, 1e-8))
                is_anomaly    = mae > threshold
        except Exception as e:
            logging.exception(f"VAE anomali hatası: {e}")
    elif vae_model is None and hasattr(state, 'vae_error_logged') and not state.vae_error_logged:
        logging.warning("VAE modeli yüklenemedi. Anomali tespiti (LSTM-VAE) şu an devre dışı.")
        state.vae_error_logged = True

    # Require persistence for the statistical detector; physical alarms remain immediate.
    detector_version = (id(vae_model), getattr(vae_model, "anomaly_threshold", None),
                        getattr(vae_model, "persistence_samples", 3),
                        getattr(vae_model, "persistence_seconds", 1.5))
    if state.get("vae_detector_version") != detector_version:
        state.vae_anomaly_streak = 0
        state.vae_anomaly_duration = 0.
        state.vae_detector_version = detector_version
    previous_streak = state.get("vae_anomaly_streak", 0)
    interval = float(state.get("sample_dt", .5))
    if not np.isfinite(interval) or interval <= 0:
        interval = 0.  # An invalid clock cannot advance confirmation.
    state.vae_anomaly_streak = previous_streak+1 if is_anomaly else 0
    state.vae_anomaly_duration = ((state.get("vae_anomaly_duration", 0.) if previous_streak else 0.)
                                  + interval) if is_anomaly else 0.
    required_samples = getattr(vae_model, "persistence_samples", 3)
    required_seconds = getattr(vae_model, "persistence_seconds", 1.5)
    is_anomaly = (is_anomaly and state.vae_anomaly_streak >= required_samples
                  and state.vae_anomaly_duration+1e-9 >= required_seconds)
    state.vae_detected = bool(is_anomaly)
    state.vae_available = vae_model is not None
    state.rf_available = rf_model is not None
    state.rf_attack_score = ml_score

    # Each detector retains its own decision rule. Their uncalibrated scores
    # are not added as if they shared a probabilistic scale.
    raw_ml_detected = (ml_label not in ("NORMAL", "RF_HATASI", "?") and ml_score >= 0.5)
    rf_version = (state.ml_source, id(rf_model))
    if state.get("rf_confirmation_version") != rf_version:
        state.rf_anomaly_streak = 0
        state.rf_confirmation_version = rf_version
    state.rf_anomaly_streak = state.get("rf_anomaly_streak", 0)+1 if raw_ml_detected else 0
    # Normal calibration produced isolated, weak GNSS RF positives. Do not turn
    # those single observations into long navigation quarantines. Strong RF,
    # physical rules, and the separate AV model retain their immediate response.
    ml_detected = raw_ml_detected and (
        state.ml_source != "GNSS_RF" or ml_score >= _cfg.RF_IMMEDIATE_ATTACK_SCORE
        or state.rf_anomaly_streak >= _cfg.RF_CONFIRMATION_SAMPLES)
    state.rf_confirmed = bool(ml_detected)
    
    # Tehdit durumu: Kural alarmı VEYA ML sınıflandırması VEYA VAE anomali eşik aşımı
    is_threat = (rule_score > 0.5) or ml_detected or is_anomaly
    state.hybrid_fresh_evidence = bool(
        (rule_score > .5 and state.get("rule_fresh_evidence", True))
        or ml_detected or is_anomaly)

    if is_threat:
        if rule_attack_type != "NORMAL":
            final_type = rule_attack_type
        elif ml_detected:
            final_type = ml_label
        elif is_anomaly:
            final_type = "ANOMALİ (Potansiyel Meaconing)"
        else:
            final_type = "SPOOFING"
            
    else:
        final_type = "NORMAL"

    latency_ms = (time.perf_counter() - start_time) * 1000.0
    state.inference_latency = latency_ms # UI'da göstermek için state içine kaydet
    
    # Çok yavaşsa logla (NVIDIA Jetson / Edge hedefleri için)
    if latency_ms > 10.0:
        logging.debug(f"Yüksek Inference Latency: {latency_ms:.2f} ms")

    return final_type, None, ml_label, round(anomaly_score, 4)


def trigger_model_training():
    try:
        from train_model import run_model_training
        result = run_model_training()
        if result[0]:
            load_rf_bundle.clear()
            load_scaler.clear()
            load_vae_model.clear()
        return result
    except Exception as e:
        return False, f"Eğitim hatası: {e}", None


def log_training_data(state, features, attack_mode):
    if (not state.get("save_training_data", False) or state.get("use_dataset_mode", False)
            or state.get("use_live_gps", False)):
        return
    csv_file = "gnss_training_motion_v2.csv"
    run_id = state.get("training_session_id")
    if not isinstance(run_id, str) or not run_id.strip():
        run_id = uuid.uuid4().hex
        state["training_session_id"] = run_id
    row = {
        "run_id":        run_id,
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
