from types import SimpleNamespace

import numpy as np
import pytest

import ml_detection
from validation import State
from vae_calibration import calibration_policy


def test_calibration_does_not_join_streaks_at_run_boundaries():
    result = calibration_policy([[0.]*8+[1.,3.], [4.]+[0.]*9], quantile=.8)
    assert result["longest_normal_streak"] == 2
    assert result["persistence_samples"] == 3


@pytest.mark.parametrize("runs", [[], [[]], [[float("nan")]], [[-1.]], [[[1.]]], [[0.]*5]])
def test_invalid_or_insufficient_calibration_is_rejected(runs):
    with pytest.raises(ValueError):
        calibration_policy(runs)


def test_calibration_rejects_excessive_confirmation_delay():
    with pytest.raises(ValueError, match="excessive"):
        calibration_policy([[0.]*10+[1.]*10, [0.]*20], quantile=.6)


class FixedErrorVAE:
    feature_mean = np.zeros(4)
    feature_std = np.ones(4)
    anomaly_threshold = .5
    persistence_samples = 4
    persistence_seconds = 2.
    error = 1.

    def __call__(self, values):
        return values+self.error, None, None


def setup_detector(monkeypatch):
    model = FixedErrorVAE()
    monkeypatch.setattr(ml_detection, "load_vae_model", lambda: model)
    monkeypatch.setattr(ml_detection, "load_rf_bundle", lambda: (None, None))
    monkeypatch.setattr(ml_detection, "load_scaler", lambda: None)
    return model, State(sample_dt=.5)


def decide(state, rule="NORMAL"):
    return ml_detection.get_hybrid_decision(rule, [45.,0.,0.,0.], state, [[45.,0.,0.,0.]]*10)[0]


def test_vae_uses_bundle_confirmation_and_resets_on_clean_sample(monkeypatch):
    model, state = setup_detector(monkeypatch)
    for _ in range(3):
        assert decide(state) == "NORMAL"
    assert decide(state).startswith("ANOMAL")
    model.error = 0.
    assert decide(state) == "NORMAL"
    assert state.vae_anomaly_duration == 0.
    model.error = 1.
    for _ in range(3):
        assert decide(state) == "NORMAL"


def test_confirmation_uses_real_sample_time_and_external_buffer_reset(monkeypatch):
    _, state = setup_detector(monkeypatch)
    state.sample_dt = .25
    for _ in range(7):
        assert decide(state) == "NORMAL"
    assert decide(state).startswith("ANOMAL")
    # A discontinuity/source switch already resets the streak in the caller.
    state.vae_anomaly_streak = 0
    assert decide(state) == "NORMAL"
    assert state.vae_anomaly_duration == .25


def test_physical_and_rf_evidence_do_not_wait_for_vae_confirmation(monkeypatch):
    _, state = setup_detector(monkeypatch)
    assert decide(state, "SPOOFING") == "SPOOFING"
    assert decide(state, "JAMMING") == "JAMMING"
    class RF:
        classes_ = np.array([0, 1])
        _embedded_scaler = SimpleNamespace(transform=lambda values: values)
        def predict_proba(self, values):
            return np.array([[0., 1.]])
    encoder = SimpleNamespace(classes_=np.array(["NORMAL", "SPOOFING"]),
                              inverse_transform=lambda values: ["SPOOFING"])
    monkeypatch.setattr(ml_detection, "load_rf_bundle", lambda: (RF(), encoder))
    state.vae_anomaly_streak = 0
    assert decide(state) == "SPOOFING"


def test_weak_gnss_rf_requires_confirmation_and_clean_observation_resets(monkeypatch):
    vae, state = setup_detector(monkeypatch)
    vae.error = 0.
    class RF:
        classes_ = np.array([0, 1])
        _embedded_scaler = SimpleNamespace(transform=lambda values: values)
        score = .6
        def predict_proba(self, values):
            return np.array([[1-self.score,self.score]])
    model = RF()
    encoder = SimpleNamespace(classes_=np.array(["NORMAL", "SPOOFING"]),
                              inverse_transform=lambda values: ["NORMAL" if values[0] == 0 else "SPOOFING"])
    monkeypatch.setattr(ml_detection, "load_rf_bundle", lambda: (model, encoder))
    assert decide(state) == "NORMAL"
    assert not state.rf_confirmed
    assert decide(state) == "SPOOFING"
    model.score = .1
    assert decide(state) == "NORMAL"
    model.score = .6
    assert decide(state) == "NORMAL"
    model.score = .95
    state.rf_anomaly_streak = 0
    assert decide(state) == "SPOOFING"
