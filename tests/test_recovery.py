import math

from detection import run_firewall_rules
from navigation import process_navigation
from validation import new_state


def stationary_state():
    state = new_state()
    state.prev_speed = 0.
    state.navigation_time = 0.
    process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
    return state


def test_discontinuity_clears_sequence_even_when_heading_reason_has_priority():
    state = new_state()
    state.prev_heading = 0.
    state.vae_buffer = [[1.,2.,3.,4.]]*10
    state.vae_anomaly_streak = state.rf_anomaly_streak = 5
    state.imu_data = dict(frame="navigation",heading_independent=True,heading_deg=0.,
                          accel=dict(x=0.,y=0.))
    # A large eastward jump is also a >45 degree course change.
    label, reason = run_firewall_rules(state,state.prev_lat,state.prev_lon+.01,45.,60.,45.,.5,40.,45.)
    assert label == "SPOOFING" and "değişimi göstergesi" in reason
    assert state.inertial_consistency["discontinuity"]
    assert state.vae_buffer == [] and state.vae_anomaly_streak == state.rf_anomaly_streak == 0


def test_independent_alarm_holds_gnss_across_intermittent_normal_decisions():
    state = stationary_state()
    state.navigation_time = 1.
    state.inertial_consistency = dict(available=True,detected=True,anomalous=True,
                                      monitor_window_s=20.,discontinuity=False)
    process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("SPOOFING","IMU"))
    assert state.inertial_hold_until == 21.
    state.navigation_time = 8.
    state.inertial_consistency = dict(available=True,detected=False,anomalous=False,
                                      warming_up=False,nis=.1,error_m=.1)
    result = process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
    assert result[3] == "SPOOFING" and "IMU" in result[4]
    assert not state.gnss_measurement_used
    state.navigation_time = 22.
    result = process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
    assert result[3] == "NORMAL" and state.gnss_measurement_used


def test_new_inertial_evidence_extends_hold_without_waiting_for_second_streak():
    state = stationary_state()
    state.inertial_hold_until = 20.
    state.navigation_time = 15.
    state.inertial_consistency = dict(detected=False,anomalous=True,monitor_window_s=20.)
    process_navigation(state,state.prev_lat,state.prev_lon,0.,45.,True,.5,40.,decision=("NORMAL",""))
    assert state.inertial_hold_until == 35.
    assert not state.gnss_measurement_used


def test_coordinate_reset_does_not_bypass_quarantine_or_innovation_gate():
    state = stationary_state()
    state.inertial_hold_until = 100.
    state.navigation_time = 2.
    state.inertial_consistency = dict(discontinuity=True,detected=False)
    process_navigation(state,41.,29.,0.,45.,True,.5,40.,decision=("SPOOFING","jump"))
    assert state.inertial_hold_until == 2.
    assert not state.gnss_measurement_used
    state.navigation_time = 10.
    state.inertial_consistency = {}
    result = process_navigation(state,41.,29.,0.,45.,True,.5,40.,decision=("NORMAL",""))
    assert not state.gnss_measurement_used and result[3] == "SPOOFING"


def test_low_signal_cannot_reintroduce_spoofed_gnss_during_inertial_hold():
    state = stationary_state()
    state.navigation_time = 1.
    state.inertial_hold_until = 20.
    state.inertial_consistency = dict(available=False,detected=False)
    process_navigation(state,state.prev_lat,state.prev_lon,0.,12.,True,.5,40.,decision=("JAMMING",""))
    assert not state.gnss_measurement_used
    assert math.isfinite(state.position_sigma_m)


def test_jump_bearing_does_not_become_next_frames_vehicle_heading():
    state = new_state()
    state.prev_heading = 0.
    jumped_lat, jumped_lon = state.prev_lat, state.prev_lon+.01
    label, _ = run_firewall_rules(state,jumped_lat,jumped_lon,45.,60.,45.,.5,40.,45.)
    assert label == "SPOOFING" and state.rule_fresh_evidence
    assert state.heading_difference > 45.
    assert state.observed_heading == 0.
    state.prev_lat, state.prev_lon = jumped_lat, jumped_lon
    state.prev_heading = state.observed_heading
    label, reason = run_firewall_rules(state,jumped_lat+8./111320,jumped_lon,45.,60.,45.,.5,40.,45.)
    assert label == "SPOOFING"  # Retained protection still applies.
    assert not state.rule_fresh_evidence
    assert "kararlılık kuralı" in reason


def test_real_course_change_without_coordinate_jump_is_still_detected():
    state = new_state()
    state.prev_heading = 0.
    label, reason = run_firewall_rules(state,state.prev_lat,
        state.prev_lon+8./(111320*math.cos(math.radians(state.prev_lat))),45.,60.,45.,.5,40.,45.)
    assert label == "SPOOFING" and "değişimi göstergesi" in reason
    assert state.rule_fresh_evidence
    assert not state.inertial_consistency["discontinuity"]
    assert state.observed_heading > 80.
