"""Shared navigation response for the UI and offline validation."""
import math
import time
import config
import numpy as np
from detection import run_firewall_rules
from fusion import get_fused_position


def process_navigation(state, raw_lat, raw_lon, raw_speed, raw_cn0, fw_active,
                       conf_cn0_percent, conf_accel, dt=.5, decision=None):
    attack_type, reason = decision if decision is not None else run_firewall_rules(
        state, raw_lat, raw_lon, raw_cn0, raw_speed, config.NOMINAL_CN0,
        conf_cn0_percent, conf_accel, config.DEFAULT_HEADING_THRESHOLD, dt=dt)
    imu_data = state.get("imu_data", {})
    imu = imu_data.get("accel", {})
    state.imu_navigation_available = bool(imu) and imu_data.get("frame") == "navigation"
    if (not state.imu_navigation_available) or (state.get("use_live_gps", False) and (not imu_data.get("real", False)
                                              or not state.imu_navigation_available)):
        imu = {}
        state.imu_navigation_available = False
    now = state.get("navigation_time", time.monotonic())
    previously_quarantined = now < state.get("gnss_quarantine_until", -1.)
    original_type = attack_type
    if (attack_type != "NORMAL" and attack_type != "JAMMING"
            and state.get("hybrid_fresh_evidence", True)):
        statistical_only = (attack_type.startswith("ANOMAL")
                            and not state.get("rule_fresh_evidence", True))
        # A physical/RF episode cannot become eligible for early recovery merely
        # because its last alarm happened to come from the statistical detector.
        state.quarantine_statistical_only = (statistical_only and
            (not previously_quarantined or state.get("quarantine_statistical_only", False)))
        state.gnss_quarantine_until = now+5.
    quarantined = now < state.get("gnss_quarantine_until", -1.)
    consistency = state.get("inertial_consistency", {})
    if consistency.get("discontinuity", False):
        # A new coordinate segment restarts consistency evidence. The physical
        # quarantine and EKF gate still apply; this does not trust the new fix.
        state.inertial_hold_until = now
    elif (consistency.get("detected", False)
          or (now < state.get("inertial_hold_until", -1.) and consistency.get("anomalous", False))):
        state.inertial_hold_until = now+consistency.get("monitor_window_s", 20.)
    inertial_hold = now < state.get("inertial_hold_until", -1.)
    independently_clear = (
        consistency.get("available", False) and not consistency.get("warming_up", True)
        and not consistency.get("detected", False)
        and math.isfinite(consistency.get("error_m", float("inf")))
        and consistency.get("error_m", float("inf")) <= 2.
        and math.isfinite(consistency.get("nis", float("inf")))
        and consistency.get("nis", float("inf")) <= -2*math.log(.001))
    if (quarantined and original_type == "NORMAL"
            and state.get("quarantine_statistical_only", False) and independently_clear):
        state.quarantine_clear_samples = state.get("quarantine_clear_samples", 0)+1
        state.quarantine_clear_duration = state.get("quarantine_clear_duration", 0.)+dt
        if state.quarantine_clear_samples >= 3 and state.quarantine_clear_duration >= 1.5:
            # Only eligibility changes here. The EKF innovation gate below must
            # still accept this measurement before GNSS can be used again.
            state.gnss_quarantine_until = now
            quarantined = False
    else:
        state.quarantine_clear_samples = 0
        state.quarantine_clear_duration = 0.
    state.fused_lat, state.fused_lon = get_fused_position(
        state, raw_lat, raw_lon, imu.get("x", 0.), imu.get("y", 0.), dt=dt,
        gps_trustworthy=(attack_type == "NORMAL" and not quarantined and not inertial_hold),
        degraded_cn0=(raw_cn0 if attack_type == "JAMMING" and math.isfinite(raw_cn0)
                       and not inertial_hold and not consistency.get("detected", False) else None))
    if (attack_type == "SPOOFING" and not state.get("inertial_reference_seeded", False) and consistency.get("detected", False)
            and "reference_position" in consistency and state.get("ekf_filter") is not None):
        # The first detected discrepancy may already have biased the GNSS-derived
        # velocity. Use only the independent window's earlier anchor and IMU prediction.
        ekf = state.ekf_filter
        lat, lon = consistency["reference_position"]
        scale = np.array([111320.,111320*math.cos(math.radians(lat))])
        ekf.x[:2] = [lat,lon]
        ekf.x[2:] = np.array(consistency["reference_velocity"])/scale
        ekf.P = np.zeros((4,4))
        ekf.P[:2,:2] = np.array(consistency["reference_position_covariance"])/np.outer(scale,scale)
        ekf.P[2:,2:] = np.array(consistency["reference_velocity_covariance"])/np.outer(scale,scale)
        state.fused_lat, state.fused_lon = lat, lon
        state.inertial_reference_seeded = True
        state.position_sigma_m = math.sqrt(max(np.linalg.eigvalsh(np.array(consistency["reference_position_covariance"]))))
    if original_type == "NORMAL" and (quarantined or not state.get("gnss_measurement_used", False)):
        attack_type = "SPOOFING"
        reason = ("Bağımsız IMU tutarlılık penceresi yeniden doğrulanıyor" if inertial_hold else
                  "GNSS yeniden doğrulama bekleniyor" if quarantined else "GNSS filtre yeniliği tutarsız")
        if not quarantined and not inertial_hold:
            state.gnss_quarantine_until = now+5.
    state.navigation_mode = ("GNSS_FUSION" if state.get("gnss_measurement_used", False)
                             else "INERTIAL_PREDICTION")
    state.ins_degraded = False
    if attack_type == "NORMAL":
        state.inertial_reference_seeded = False
        state.last_good_lat, state.last_good_lon = raw_lat, raw_lon
        state.ins_active = False
        state.ins_remaining = 0.
    elif fw_active:
        now = state.get("navigation_time", time.monotonic())
        if not state.ins_active:
            state.ins_start_time = now
            state.ins_duration = config.INS_DURATION_MAX
        state.ins_active = True
        state.ins_remaining = max(0., state.ins_duration - (now - state.ins_start_time))
        state.ins_degraded = (state.ins_remaining == 0.
                              or state.get("position_sigma_m", 0.) > 10.)
        # Continue inertial prediction, flag degraded confidence; never freeze a moving
        # vehicle's displayed position or return an attacked GNSS sample on timeout.
        state.ins_lat, state.ins_lon = state.fused_lat, state.fused_lon
        ekf = state.get("ekf_filter")
        if ekf is not None:
            velocity_n = ekf.x[2] * 111320
            velocity_e = ekf.x[3] * 111320 * math.cos(math.radians(ekf.x[0]))
            state.ins_speed = math.hypot(velocity_n, velocity_e) * 3.6
        else:
            state.ins_speed = state.prev_speed
        return state.ins_lat, state.ins_lon, state.ins_speed, attack_type, reason
    if fw_active:
        return state.fused_lat, state.fused_lon, raw_speed, attack_type, reason
    return raw_lat, raw_lon, raw_speed, attack_type, reason
