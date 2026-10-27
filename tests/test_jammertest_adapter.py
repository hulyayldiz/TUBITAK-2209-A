import math
import pandas as pd
import pytest

from dataset_loader import get_next_dataset_row, load_dataset_from_local_path
from detection import run_firewall_rules
from jammertest_adapter import adapt_mon_rf, adapt_nav_pvt, event_intervals
from validation import new_state


def test_jammertest_event_z_suffix_is_converted_from_cest_to_utc():
    intervals = event_intervals({"attack_log": [
        {"timestamp_utc": "2024-09-10T16:00:00Z", "event": "Jamming started"},
        {"timestamp_utc": "2024-09-10T16:10:00Z", "event": "Jamming end"},
    ]})
    assert intervals[0]["start_utc"].startswith("2024-09-10T14:00:00")
    assert intervals[0]["end_utc"].startswith("2024-09-10T14:10:00")
    assert intervals[0]["source_clock"].startswith("Europe/Oslo")


def test_jammertest_nav_pvt_normalizes_units_without_inventing_cno_or_imu():
    frame = pd.DataFrame({
        "real_time": ["2024-09-10 14:00:00", "2024-09-10 14:00:01", "2024-09-10 14:00:02"],
        "lat": [6.921e-06, 0., 6.9210001e-06], "lon": [1.585e-06, 0., 1.5850001e-06],
        "gSpeed": [1., 0., 2.], "fixType": [3, 0, 3], "hAcc": [.5, 99., .6], "sAcc": [.1, 99., .1],
    })
    adapted = adapt_nav_pvt(frame, {"attack_parameters": {"Rover states": "dynamic"}})
    assert adapted.lat.iloc[0] == pytest.approx(69.21)
    assert adapted.lon.iloc[0] == pytest.approx(15.85)
    assert adapted.speed_kmh.tolist() == [3.6, 3.6, 7.2]
    assert adapted.timestamp_s.tolist() == [0., 1., 2.]
    assert adapted.fix_valid.tolist() == [True, False, True]
    assert math.isnan(adapted.horizontal_accuracy_m.iloc[1])
    assert adapted.attrs["source"]["cn0_available"] is False
    assert adapted.attrs["source"]["independent_imu"] is False


def test_jammertest_rf_monitor_keeps_receiver_state_and_collapses_band_rows():
    frame = pd.DataFrame({
        "real_time": ["2024-09-10 14:00:00"]*2,
        "jamInd_01": [5, 8], "jamInd_02": [9, 4],
        "jammingState_01": [1, 2], "jammingState_02": [1, 1],
        "noisePerMS_01": [20, 21], "noisePerMS_02": [18, 19],
        "agcCnt_01": [100, 101], "agcCnt_02": [90, 92],
    })
    adapted = adapt_mon_rf(frame)
    assert len(adapted) == 1
    assert adapted.jam_indicator.iloc[0] == 9
    assert adapted.jamming_state.iloc[0] == 2


def test_only_explicit_receiver_warning_raises_jamming_alarm_without_cno():
    state = new_state()
    state.receiver_rf_observables = {"jamming_state": 2., "jam_indicator": 10.}
    alarm, reason = run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
        45., .5, 40., 45., dt=.5)
    assert alarm == "JAMMING"
    assert "MON-RF" in reason

    state = new_state()
    state.prev_speed = 0.
    state.receiver_rf_observables = {"jamming_state": 0., "jam_indicator": 255.}
    alarm, _ = run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
        45., .5, 40., 45., dt=.5)
    assert alarm == "NORMAL"  # 0 means unknown/disabled; jamInd needs a calibrated profile.


def test_fix_loss_alarm_requires_previous_lock_and_three_seconds():
    state = new_state()
    state.prev_speed = 0.
    # A receiver that has not acquired a fix is warming up, not under attack.
    for _ in range(8):
        state.receiver_rf_observables = {"fix_valid": False}
        alarm, _ = run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
            45., .5, 40., 45., dt=.5)
        assert alarm == "NORMAL"
    state.receiver_rf_observables = {"fix_valid": True}
    run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
        45., .5, 40., 45., dt=.5)
    for _ in range(5):
        state.receiver_rf_observables = {"fix_valid": False}
        alarm, _ = run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
            45., .5, 40., 45., dt=.5)
        assert alarm == "NORMAL"
    alarm, reason = run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
        45., .5, 40., 45., dt=.5)
    assert alarm == "GNSS_FIX_LOSS"
    assert "olası girişim" in reason and "saldırı türü tek başına belirlenemez" in reason
    state.receiver_rf_observables = {"fix_valid": True}
    run_firewall_rules(state, state.prev_lat, state.prev_lon, float("nan"), 0.,
        45., .5, 40., 45., dt=.5)
    assert state.fix_loss_duration_s == 0.


def test_exported_receiver_monitor_flows_through_dataset_loader(tmp_path):
    frame = pd.DataFrame({
        "timestamp_s": [0., 1.], "lat": [38.6744, 38.6744], "lon": [39.1942, 39.1942],
        "speed_kmh": [0., 0.], "receiver_id": ["test-ublox", "test-ublox"],
        "receiver_motion": ["static", "static"],
        "receiver_jamming_state": [2., 1.], "receiver_jam_indicator": [10., 10.],
        "receiver_fix_valid": [False, True],
    })
    path = tmp_path/"receiver.csv"
    frame.to_csv(path, index=False)
    state = new_state()
    assert load_dataset_from_local_path(str(path), state)
    row = get_next_dataset_row(state)
    assert math.isnan(row[3])  # C/N0 remains NaN when not measured.
    assert state.receiver_profile_name == "receiver-unvalidated"
    assert state.receiver_rf_observables["jamming_state"] == 2.
    assert state.receiver_rf_observables["fix_valid"] == 0.
    alarm, reason = run_firewall_rules(state, row[0], row[1], row[3], row[2],
        45., .5, 40., 45., dt=state.sample_dt)
    assert alarm == "JAMMING"
    assert "MON-RF" in reason
