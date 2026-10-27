import math
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
import detection
import fusion
import ml_detection
import main as application
from models.lstm_vae import LSTMVAE


class State(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def test_main_module_import_defers_streamlit_startup():
    assert callable(application.run_app)
    assert "state" not in vars(application)


def navigation_function(monkeypatch):
    import navigation
    monkeypatch.setattr(navigation, "time", SimpleNamespace(monotonic=lambda: 100))
    monkeypatch.setattr(navigation, "get_fused_position", lambda *args, **kwargs: (38, 39))
    return navigation.process_navigation


def test_ml_only_alarm_starts_ins_and_never_releases_bad_gps_on_timeout(monkeypatch):
    nav = navigation_function(monkeypatch)
    state = State(ins_active=False, last_good_lat=38, last_good_lon=39,
                  prev_speed=40, prev_heading=45)
    result = nav(state, 40, 41, 50, 45, True, .5, 40,
                 decision=("ANOMALİ (Potansiyel Meaconing)", "VAE"))
    assert state.ins_active
    assert result[:2] == (38, 39)
    state.ins_start_time = 0
    result = nav(state, 40, 41, 50, 45, True, .5, 40,
                 decision=("SPOOFING", "RF"))
    assert result[:2] == (38, 39)
    assert state.ins_degraded


def test_ekf_isolated_between_sessions():
    first, second = State(), State()
    fusion.get_fused_position(first, 38, 39, 0, 0)
    result = fusion.get_fused_position(second, 41, 29, 0, 0, gps_trustworthy=False)
    assert result == (41, 29)
    assert first.ekf_filter is not second.ekf_filter


def test_metrics_count_vae_and_compare_ground_truth():
    state = State(attack_mode="spoofing", true_lat=38, true_lon=39,
                  stats_tp=0, stats_fn=0, stats_fp=0, stats_tn=0,
                  stats_response_times=[], is_attack_detected=True)
    metrics = detection.calculate_metrics(state, "ANOMALİ", 40, 41, 38, 39)
    assert state.stats_tp == 1
    assert metrics[-1] == 0
    state.use_live_gps = True
    assert math.isnan(detection.calculate_metrics(state, "NORMAL", 40, 41, 38, 39)[-1])


def test_vae_uses_training_scale():
    class VAE:
        feature_mean = np.array([45, 2, 3, 4])
        feature_std = np.array([2, 1, 1, 2])

        def __call__(self, inputs):
            assert torch.allclose(inputs, torch.ones_like(inputs))
            return inputs, None, None

    state = State()
    with patch.object(ml_detection, "load_rf_bundle", return_value=(None, None)), \
         patch.object(ml_detection, "load_scaler", return_value=None), \
         patch.object(ml_detection, "load_vae_model", return_value=VAE()):
        result = ml_detection.get_hybrid_decision("NORMAL", [47, 3, 4, 6], state, [[47, 3, 4, 6]] * 10)
    assert result[0] == "NORMAL"


def test_vae_evaluation_is_deterministic():
    model = LSTMVAE(4, 32, 8, 10).eval()
    inputs = torch.zeros(1, 10, 4)
    with torch.no_grad():
        assert torch.equal(model(inputs)[0], model(inputs)[0])


def test_benchmark_counts_false_alarms():
    from validation import classification_summary
    result = classification_summary([False]*3, [True]*3, [0, .5, 1])
    assert result["false_alarm_rate"] == 1.
    assert result["fp"] == 3


def test_training_keeps_signal_loss_and_large_spoofing_jumps(tmp_path):
    import pandas as pd
    from train_model import load_and_validate
    rows = []
    for run in range(3):
        for label in ("NORMAL", "JAMMING", "SPOOFING"):
            for _ in range(20):
                rows.append(dict(cn0=0 if label == "JAMMING" else 45, accel=0,
                                 heading_drift=0, residual=20000 if label == "SPOOFING" else 0,
                                 target_label=label, run_id=f"run-{run}"))
    path = tmp_path / "training.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    data, error = load_and_validate(path)
    assert error is None
    assert len(data) == 180

    path = tmp_path / "no-groups.csv"
    pd.DataFrame([row for row in rows for _ in range(1)]).drop(columns="run_id").to_csv(path, index=False)
    data, error = load_and_validate(path)
    assert data is None and "run_id" in error


def test_invalid_forensic_chain_is_not_extended(tmp_path, monkeypatch):
    ledger = tmp_path / "forensic_ledger.jsonl"
    monkeypatch.setattr(application, "FORENSIC_LEDGER_PATH", ledger)
    monkeypatch.setattr(application, "load_forensic_key", lambda: b"test")
    ledger.write_text('{"invalid":true}\n', encoding="utf-8")
    original = ledger.read_bytes()
    state = State()
    application.init_forensic_chain(state)
    assert state.forensic_chain_valid is False
    application.log_chained_event(state, "WARNING", "test")
    assert ledger.read_bytes() == original
