from concurrent.futures import ThreadPoolExecutor
import math
import numpy as np
import pandas as pd
import pytest

from forensic_ledger import Ledger
from imu_processing import navigation_imu
from inertial_monitor import InertialMonitor
from nmea_stream import NMEAStream
from fusion import get_fused_position
from validation import new_state, State
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row, parse_attack_label


def sentence(body):
    checksum = 0
    for character in body:
        checksum ^= ord(character)
    return f"${body}*{checksum:02X}\r\n"


RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\r\n"


def test_nmea_partial_messages_bad_checksums_and_valid_fix():
    stream = NMEAStream()
    assert stream.feed(RMC[:30], now=0) is None
    result = stream.feed(RMC[30:], now=0)
    assert result == pytest.approx((48.1173, 11.5166666667, 22.4*1.852, 84.4))
    assert stream.feed(RMC.replace("*6A", "*00"), now=1) is None
    assert stream.feed("$bad*00\r\n"+RMC, now=1) is not None


def test_gga_does_not_reset_recent_speed():
    stream = NMEAStream()
    stream.feed(RMC, now=0)
    gga = sentence("GPGGA,123520,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,")
    assert stream.feed(gga, now=1)[2] == pytest.approx(22.4*1.852)
    assert stream.feed(gga, now=10) is None


def test_invalid_fix_is_rejected():
    stream = NMEAStream()
    invalid = sentence("GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W")
    assert stream.feed(invalid, now=0) is None
    stream.feed(RMC, now=1)
    assert stream.feed(invalid, now=2) is None
    assert stream.position is None


def test_gsv_measurements_expire():
    stream = NMEAStream()
    stream.feed(sentence("GPGSV,1,1,04,01,40,083,40,02,17,308,42,03,13,172,44,04,09,301,46"), now=0)
    assert stream.cn0(now=1) == 43.
    assert math.isnan(stream.cn0(now=4))


def test_body_gravity_rotation_requires_independent_attitude():
    body = dict(accel=dict(x=0.,y=0.,z=9.80665), frame="body", real=True)
    assert navigation_imu(body)["frame"] == "body"
    body["attitude"] = dict(valid=True, heading_independent=True,
        convention="FRU_to_NEU", roll_deg=0., pitch_deg=0., yaw_deg=90.)
    body["accel"]["x"] = 1.
    transformed = navigation_imu(body)
    assert transformed["frame"] == "navigation"
    assert list(transformed["accel"].values()) == pytest.approx([0.,1.,0.], abs=1e-10)


def test_inertial_monitor_detects_normal_cn0_slow_drift_without_labels():
    monitor = InertialMonitor()
    detections = []
    for index in range(200):
        t = index*.5
        imu = dict(accel=dict(x=0., y=0.), frame="navigation", heading_independent=True, heading_deg=0.)
        result = monitor.update(38.+20*t/111320,
            39.+max(0.,t-60)*.5/(111320*math.cos(math.radians(38.))),72.,imu,.5)
        detections.append(result["detected"])
    assert not any(detections[:120])
    assert any(detections[120:160])
    assert all(detections[160:])


def test_monitor_does_not_invent_independent_sensor():
    result = InertialMonitor().update(38.,39.,40.,dict(accel=dict(x=0,y=0),frame="body"),.5)
    assert not result["available"] and not result["detected"]


def test_degraded_gnss_is_weighted_but_coordinate_attack_rejected():
    state = new_state()
    result = get_fused_position(state, state.prev_lat+.00001, state.prev_lon, 0, 0,
                                gps_trustworthy=False, degraded_cn0=12.)
    assert state.gnss_measurement_used
    before = result
    result = get_fused_position(state, 41.,29.,0,0,gps_trustworthy=False,degraded_cn0=12.)
    assert not state.gnss_measurement_used
    assert abs(result[0]-before[0]) < .001
    assert state.position_sigma_m > 0


def test_concurrent_forensic_events_and_rotations_remain_verifiable(tmp_path):
    ledger = Ledger(tmp_path/"events.jsonl", b"test-key", rotation_bytes=500)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda index: ledger.append("INFO", str(index)), range(24)))
    head, count = ledger.verify()
    assert count == 24 and len(head) == 64
    assert list(tmp_path.glob("*.segment-*.jsonl"))
    ledger.path.write_text(ledger.path.read_text(encoding="utf-8").replace('INFO','WARN'),encoding="utf-8")
    with pytest.raises(ValueError):
        ledger.append("INFO", "should not append")


def test_dataset_rejects_missing_fields_without_replacing_loaded_data():
    state = State(dataset_df="old")
    with pytest.raises(ValueError):
        _process_dataset_dataframe(pd.DataFrame({"lat":[38.],"lon":[39.]}), "bad.csv", state)
    assert state.dataset_df == "old"


@pytest.mark.parametrize("value", ["11", "12", "normal1", "unknown", float("nan")])
def test_labels_are_exact_not_substring_guesses(value):
    with pytest.raises(ValueError):
        parse_attack_label(value)


def test_clock_reset_and_canonical_imu_reference_are_used():
    data = pd.DataFrame(dict(timestamp_s=[0,2,0], lat=[38.,38.0001,41.],lon=[39.,39.,29.],
        speed_kmh=[40.,40.,0.], label=[0,1,1], imu_ax_m_s2=[0.,1.,0.], imu_ay_m_s2=[0.,0.,0.],
        imu_frame=["navigation"]*3, reference_lat=[38.,38.,41.], reference_lon=[39.,39.,29.]))
    state = State()
    _process_dataset_dataframe(data,"recording.csv",state)
    get_next_dataset_row(state)
    get_next_dataset_row(state)
    assert state.sample_dt == 2.
    assert state.imu_data["accel"]["x"] == 1.
    state.inertial_monitor = "stale"
    get_next_dataset_row(state)
    assert state.dataset_clock_reset and "inertial_monitor" not in state
    assert state.prev_lat == 41.
    assert state.reference_position == (41.,29.)


def test_atomic_model_write_keeps_previous_version_on_failure(tmp_path):
    from artifact_io import atomic_write
    path = tmp_path/"model"
    path.write_text("old",encoding="utf-8")
    def writer(temporary):
        temporary.write_text("partial",encoding="utf-8")
        raise OSError("disk error")
    with pytest.raises(OSError):
        atomic_write(path, writer)
    assert path.read_text(encoding="utf-8") == "old"
    atomic_write(path, lambda temporary: temporary.write_text("new",encoding="utf-8"))
    assert path.read_text(encoding="utf-8") == "new"


def test_artifact_cache_reloads_externally_replaced_model(tmp_path, monkeypatch):
    from artifact_io import dump_joblib
    import ml_detection
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    monkeypatch.chdir(tmp_path)
    values = np.array([[40.,0,0,0],[10.,1,1,1],[41.,0,0,0],[9.,1,1,1]])
    scaler = StandardScaler().fit(values)
    encoder = LabelEncoder().fit(["NORMAL","SPOOFING"])
    def save(trees):
        model = RandomForestClassifier(n_estimators=trees,random_state=3).fit(scaler.transform(values),[0,1,0,1])
        dump_joblib(dict(model=model,scaler=scaler,label_encoder=encoder,feature_schema=ml_detection.FEATURE_SCHEMA),"gnss_rf_model.pkl")
    save(2)
    first = ml_detection.load_rf_bundle()[0]
    save(3)
    second = ml_detection.load_rf_bundle()[0]
    assert first is not second and second.n_estimators == 3
    assert second._embedded_scaler.mean_ == pytest.approx(scaler.mean_)


def test_vae_windows_do_not_bridge_attack_gaps_or_runs(tmp_path, monkeypatch):
    import torch
    import train_model as training
    batches = []
    class SpyVAE(torch.nn.Module):
        def __init__(self, **kwargs):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.tensor(.9))
        def forward(self, values):
            if self.training:
                batches.extend(values.detach().clone())
            return values*self.weight, torch.zeros(len(values),1), torch.zeros(len(values),1)
    rows = []
    for run in range(4):
        for label in ("NORMAL","SPOOFING","NORMAL"):
            for _ in range(15):
                rows.append(dict(cn0=float(run),accel=float(run),heading_drift=float(run),residual=float(run),
                                 target_label=label,run_id=str(run)))
    monkeypatch.setattr(training,"LSTMVAE",SpyVAE)
    monkeypatch.setattr(training,"VAE_EPOCHS",1)
    monkeypatch.setattr(training,"VAE_PATH",str(tmp_path/"vae.pth"))
    monkeypatch.setattr(training,"THRESHOLD_PATH",str(tmp_path/"threshold.npy"))
    result = training.train_vae(pd.DataFrame(rows))
    assert result[0] is not None and batches
    assert all(torch.allclose(window,window[:1].expand_as(window)) for window in batches)


def test_uploaded_file_is_reloaded_when_same_name_changes_content():
    from dataset_loader import load_dataset_from_uploaded_file
    class Upload:
        name = "same.csv"
        def __init__(self, latitude):
            self.value = f"lat,lon,speed,label\n{latitude},39,40,0\n".encode()
        def getvalue(self):
            return self.value
    state = State()
    assert load_dataset_from_uploaded_file(Upload(38),state)
    assert state.prev_lat == 38
    assert load_dataset_from_uploaded_file(Upload(41),state)
    assert state.prev_lat == 41


def test_reference_rmse_does_not_require_attack_labels():
    from detection import calculate_metrics
    state = State(use_dataset_mode=True,ground_truth_available=False,reference_position=(38.,39.))
    metrics = calculate_metrics(state,"NORMAL",40.,41.,38.,39.)
    assert all(math.isnan(value) for value in metrics[:5])
    assert metrics[-1] == 0.


def test_spoofing_quarantine_blocks_intermittent_normal_decisions():
    from navigation import process_navigation
    state = new_state()
    state.navigation_time = 0.
    process_navigation(state,state.prev_lat,state.prev_lon,60.,45.,True,.5,40.,decision=("NORMAL",""))
    trusted = (state.last_good_lat,state.last_good_lon)
    state.navigation_time = 1.
    process_navigation(state,41.,29.,60.,45.,True,.5,40.,decision=("SPOOFING","test"))
    state.navigation_time = 1.5
    result = process_navigation(state,41.,29.,60.,45.,True,.5,40.,decision=("NORMAL",""))
    assert result[3] == "SPOOFING"
    assert not state.gnss_measurement_used
    assert (state.last_good_lat,state.last_good_lon) == trusted
    assert result[:2] != (41.,29.)


def test_innovation_gate_rejects_bad_fix_after_quarantine_expires():
    from navigation import process_navigation
    state = new_state()
    state.navigation_time = 0.
    process_navigation(state,state.prev_lat,state.prev_lon,60.,45.,True,.5,40.,decision=("NORMAL",""))
    state.navigation_time = 10.
    result = process_navigation(state,41.,29.,60.,45.,True,.5,40.,decision=("NORMAL",""))
    assert result[3] == "SPOOFING" and not state.gnss_measurement_used


def test_first_independent_reference_repairs_velocity_but_is_not_reseeded_from_attacked_anchors():
    from navigation import process_navigation
    state = new_state()
    state.navigation_time = 0.
    process_navigation(state,state.prev_lat,state.prev_lon,60.,45.,True,.5,40.,decision=("NORMAL",""))
    reference = [38.6745,39.1943]
    state.inertial_consistency = dict(detected=True,reference_position=reference,
        reference_velocity=[10.,0.],reference_position_covariance=[[1.,0.],[0.,1.]],
        reference_velocity_covariance=[[.01,0.],[0.,.01]])
    state.navigation_time = 1.
    result = process_navigation(state,38.7,39.2,60.,45.,True,.5,40.,decision=("SPOOFING","test"))
    assert result[:2] == tuple(reference)
    assert state.ekf_filter.x[2] == pytest.approx(10/111320)
    state.inertial_consistency["reference_position"] = [41.,29.]
    state.navigation_time = 1.5
    second = process_navigation(state,38.7,39.2,60.,45.,True,.5,40.,decision=("SPOOFING","test"))
    assert abs(second[0]-reference[0]) < .001
    assert second[:2] != (41.,29.)


def test_signal_measurement_is_not_mixed_between_network_sources():
    from live_gps import _decode
    state = State()
    assert _decode(state,"tcp:one",RMC) is not None
    assert state.gps_source == "tcp:one" and math.isnan(state.gps_cn0)
    gsv = sentence("GPGSV,1,1,04,01,40,083,40,02,17,308,42,03,13,172,44,04,09,301,46")
    assert _decode(state,"udp:other",gsv) is None
    assert state.gps_source == "tcp:one" and math.isnan(state.gps_cn0)
    assert _decode(state,"udp:other",RMC) is not None
    assert state.gps_source == "udp:other" and state.gps_cn0 == 43.


def test_normal_navigation_returns_filter_output_and_bypass_returns_raw():
    from navigation import process_navigation
    for enabled in (True, False):
        state = new_state()
        raw = (state.prev_lat+.00001, state.prev_lon)
        result = process_navigation(state, *raw, 60., 45., enabled, .5, 40.,
                                    decision=("NORMAL", ""))
        assert state.gnss_measurement_used
        assert result[:2] == ((state.fused_lat, state.fused_lon) if enabled else raw)
        if enabled:
            assert result[:2] != raw


@pytest.mark.parametrize("word, expected", [(0x0000, 0), (0x7fff, 32767),
                                           (0x8000, -32768), (0xffff, -1)])
def test_mpu6050_signed_read_includes_minimum_value(word, expected):
    from mpu6050 import MPU6050
    from types import SimpleNamespace
    sensor = MPU6050.__new__(MPU6050)
    sensor.address = 0x68
    sensor.bus = SimpleNamespace(read_byte_data=lambda address, register:
                                word >> 8 if register == 0x3b else word & 255)
    assert sensor._read_raw_data(0x3b) == expected


def test_sensor_recovery_offsets_never_reverse_on_delayed_sample():
    from sensors import simulate_sensors
    state = new_state()
    state.spoof_offset_lat, state.spoof_offset_lon, state.spoof_speed_offset = .1, .2, 10.
    simulate_sensors(state, dt=5.)
    assert 0 < state.spoof_offset_lat < .1
    assert 0 < state.spoof_offset_lon < .2
    assert 0 < state.spoof_speed_offset < 10.


@pytest.mark.parametrize("dt", [0., -1., float("nan"), float("inf")])
def test_sensor_rejects_invalid_interval_before_changing_state(dt):
    from sensors import simulate_sensors
    state = new_state()
    previous = dict(state)
    with pytest.raises(ValueError, match="dt"):
        simulate_sensors(state, dt=dt)
    assert state == previous


def test_retained_alarm_does_not_renew_quarantine_but_new_evidence_does():
    from navigation import process_navigation
    state = new_state()
    state.navigation_time = 0.
    process_navigation(state, state.prev_lat, state.prev_lon, 60.,45.,True,.5,40.,
                       decision=("SPOOFING", "fresh"))
    assert state.gnss_quarantine_until == 5.
    state.navigation_time = 2.
    state.hybrid_fresh_evidence = False
    process_navigation(state,state.prev_lat,state.prev_lon,60.,45.,True,.5,40.,
                       decision=("SPOOFING", "retained"))
    assert state.gnss_quarantine_until == 5.
    assert not state.gnss_measurement_used
    state.hybrid_fresh_evidence = True
    process_navigation(state,state.prev_lat,state.prev_lon,60.,45.,True,.5,40.,
                       decision=("SPOOFING", "new evidence"))
    assert state.gnss_quarantine_until == 7.


def test_hybrid_marks_hysteresis_as_retained_without_disabling_new_rules(monkeypatch):
    import ml_detection
    monkeypatch.setattr(ml_detection, "load_rf_bundle", lambda: (None, None))
    monkeypatch.setattr(ml_detection, "load_vae_model", lambda: None)
    state = new_state()
    for fresh in (False, True):
        state.rule_fresh_evidence = fresh
        result = ml_detection.get_hybrid_decision("SPOOFING", [45.,0.,0.,0.],state)
        assert result[0] == "SPOOFING"
        assert state.hybrid_fresh_evidence is fresh


def test_artifact_loaders_for_same_files_have_separate_cache_values(tmp_path):
    from artifact_io import artifact_cache
    path = tmp_path / "shared.bin"
    path.write_bytes(b"same artifact")
    @artifact_cache(path)
    def model_loader():
        return ("model", "labels")
    @artifact_cache(path)
    def scaler_loader():
        return "scaler"
    assert model_loader() == ("model", "labels")
    assert scaler_loader() == "scaler"
    assert model_loader() == ("model", "labels")


def statistical_quarantine_state():
    from navigation import process_navigation
    state = new_state()
    state.prev_speed = 0.
    state.navigation_time = 0.
    process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
    state.rule_fresh_evidence = False
    state.hybrid_fresh_evidence = True
    state.navigation_time = .5
    process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,
                       decision=("ANOMALİ (Potansiyel Meaconing)","VAE"))
    return state


def test_statistical_alarm_recovers_after_three_independently_clear_samples():
    from navigation import process_navigation
    state = statistical_quarantine_state()
    state.inertial_consistency = dict(available=True,warming_up=False,detected=False,error_m=.5,nis=.1)
    for index in range(3):
        state.navigation_time = 1.+index*.5
        result = process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
        assert state.gnss_measurement_used is (index == 2)
    assert result[3] == "NORMAL"


@pytest.mark.parametrize("invalid", [dict(available=False),dict(warming_up=True),dict(detected=True),
                                  dict(error_m=3.),dict(error_m=float("nan")),dict(nis=100.)])
def test_statistical_early_recovery_requires_independent_confirmation(invalid):
    from navigation import process_navigation
    state = statistical_quarantine_state()
    state.inertial_consistency = dict(available=True,warming_up=False,detected=False,error_m=.5,nis=.1)
    state.inertial_consistency.update(invalid)
    for index in range(3):
        state.navigation_time = 1.+index*.5
        process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
        assert not state.gnss_measurement_used


def test_early_recovery_still_rejects_filter_innovation_and_physical_episode():
    from navigation import process_navigation
    state = statistical_quarantine_state()
    state.inertial_consistency = dict(available=True,warming_up=False,detected=False,error_m=.5,nis=.1)
    for index in range(3):
        state.navigation_time = 1.+index*.5
        process_navigation(state,41.,29.,0.,45.,True,.5,40.,decision=("NORMAL",""))
    assert not state.gnss_measurement_used
    assert state.gnss_quarantine_until > state.navigation_time
    state.navigation_time = 2.5
    process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("SPOOFING","physical"))
    assert not state.quarantine_statistical_only
