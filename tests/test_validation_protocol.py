import math
from unittest.mock import patch

import pandas as pd

from detection import analyze_kinematics, run_firewall_rules
from features import extract_features
from navigation import process_navigation
from validation import State, new_state, classification_summary, evaluate_av
import ml_detection
import sensors


def test_missed_episode_is_not_zero_latency():
    result = classification_summary([False, True, True, False], [False]*4, [0, .5, 1, 1.5])
    assert result["episode_ttd_s"] == [None]
    assert result["missed_episodes"] == 1
    assert result["fn"] == 2


def test_ttd_measures_first_alarm_relative_to_onset():
    result = classification_summary([False, True, True, True], [True, False, True, True], [0, 1, 2, 3])
    assert result["episode_ttd_s"] == [1.]
    assert result["fp"] == 1


def test_features_cannot_read_ground_truth_or_attack_labels():
    state = new_state()
    observation = (state.prev_lat+.0001, state.prev_lon, 60, 45)
    before = extract_features(state, *observation)
    state.attack_mode = "spoofing"
    state.true_lat, state.true_lon = 0., 0.
    assert extract_features(state, *observation) == before


def test_gps_acceleration_is_recomputed_without_imu():
    state = State(prev_speed=40., prev_lat=38., prev_lon=39., prev_heading=0., acceleration=100.)
    assert analyze_kinematics(state, 38., 39., 40., 45.)[0] == 0.


def test_long_distance_from_old_trusted_point_does_not_latch_alarm():
    state = new_state()
    state.last_good_lat, state.last_good_lon = 0., 0.
    attack, _ = run_firewall_rules(state, state.prev_lat, state.prev_lon, 45., 60., 45., .5, 40., 45.)
    assert attack == "NORMAL"


def test_prediction_continues_beyond_ins_timeout():
    state = new_state()
    state.prev_speed = 36.
    state.prev_heading = 0.
    positions = []
    for index in range(30):
        state.navigation_time = index * .5
        positions.append(process_navigation(state, 41., 29., 100., 45., True, .5, 40.,
                                            decision=("SPOOFING", "test"))[0])
    assert state.ins_degraded
    assert positions[-1] > positions[-2]
    assert positions[-1] < 39.


def test_no_live_fix_does_not_become_synthetic_measurement():
    state = new_state()
    with patch.object(sensors, "get_gps_from_serial", return_value=(None,)*4):
        assert sensors.simulate_sensors(state, use_live_gps=True) is None


def test_live_measurement_is_returned_without_synthetic_noise():
    state = new_state()
    with patch.object(sensors, "get_gps_from_serial", return_value=(38., 39., 50., 60.)), \
         patch.object(sensors, "get_live_imu", return_value={"accel":{"x":0., "y":0., "z":9.81}, "real":False}):
        observation = sensors.simulate_sensors(state, use_live_gps=True)
    assert observation[:3] == (38., 39., 50.)
    assert math.isnan(observation[3])
    assert not state.cn0_available


def test_missing_cn0_disables_models_instead_of_fabricating_features():
    state = State(cn0_available=False)
    with patch.object(ml_detection, "load_rf_bundle", side_effect=AssertionError("must not load")), \
         patch.object(ml_detection, "load_vae_model", side_effect=AssertionError("must not load")):
        decision = ml_detection.get_hybrid_decision("NORMAL", [float("nan"), 0, 0, 0], state, [[0]*4]*10)
    assert decision[0] == "NORMAL"
    assert not state.rf_available and not state.vae_available


def test_repeated_run_clocks_preserve_attack_segments(tmp_path):
    rows = [dict(**{"Run Time": f"0:00:0{i}", "GPS Latitude": 38., "GPS Longitude":39.,
                    "Velocity (m/s)":0., "GPS Course":0., "Data Type": label})
            for label in (0, 1) for i in range(3)]
    path = tmp_path / "av.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    result = evaluate_av(path)
    assert result["segments"] == 2
    assert result["evaluated_rows"] == 4
    assert result["tn"] == 2
    assert result["fn"] == 2
    assert result["hybrid_result"] is None
    assert result["rmse_m"] is None


def test_dataset_playback_uses_record_clock_and_separate_hash():
    from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
    state = State(last_log_hash="forensic-head")
    data = pd.DataFrame({"lat":[38.,38.0001], "lon":[39.,39.], "speed":[30.,30.],
                         "label":[0,1], "Run Time":["0:00:00","0:00:02"]})
    assert _process_dataset_dataframe(data, "test.csv", state)
    get_next_dataset_row(state)
    row = get_next_dataset_row(state)
    assert state.sample_dt == 2.
    assert row[-1] == "spoofing"
    assert state.last_log_hash == "forensic-head"
    assert not state.cn0_available
    assert get_next_dataset_row(state) is None


def test_data_collection_writes_current_feature_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = State(save_training_data=True)
    ml_detection.log_training_data(state, [45., .1, 2., .5], "NORMAL")
    data = pd.read_csv(tmp_path / "gnss_training_motion_v2.csv")
    assert data.loc[0, "target_label"] == "NORMAL"
    assert data.loc[0, "residual"] == .5
    assert isinstance(data.loc[0, "run_id"], str) and data.loc[0, "run_id"]
    assert not (tmp_path / "gnss_training_dataset.csv").exists()


def test_dataset_replay_labels_are_not_collected_as_training_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = State(save_training_data=True, use_dataset_mode=True, ground_truth_available=True)
    ml_detection.log_training_data(state, [45., .1, 2., .5], "SPOOFING")
    assert not (tmp_path / "gnss_training_motion_v2.csv").exists()
