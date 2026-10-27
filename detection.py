"""Configurable measurement-consistency rules and labelled-replay metrics.

Rule labels are anomaly hypotheses, not authenticated attack causes. Thresholds
are project settings rather than universal literature values.
"""

import math
import time
import config
from inertial_monitor import check_inertial_consistency
from sensors import calculate_distance_km

def analyze_kinematics(state, raw_lat, raw_lon, raw_speed, conf_heading, dt=0.5):
    """
    Kinematik analizi (Hız, İvme, Yörünge) gerçekleştirir.
    GPS-derived speed change is an indirect acceleration estimate.
    """
    prev_speed = getattr(state, "prev_speed", raw_speed)
    prev_lat = getattr(state, "prev_lat", raw_lat)
    prev_lon = getattr(state, "prev_lon", raw_lon)
    prev_heading = getattr(state, "prev_heading", 0.0)

    # 1. Ivme Hesabı (dV / dt)
    # Prefer valid navigation-frame IMU acceleration; otherwise use the GPS-derived estimate.
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be positive and finite")
    gps_acceleration = (raw_speed - prev_speed) / (3.6 * dt)
    # Recompute each frame; never reuse the previous GPS-derived acceleration.
    imu_data = state.get("imu_data", {})
    imu = imu_data.get("accel", {})
    if imu_data.get("real", False) and imu_data.get("frame") != "navigation":
        imu = {}  # Body-frame gravity/tilt must not become navigation acceleration.
    imu_acceleration = math.hypot(imu.get("x", 0.0), imu.get("y", 0.0))
    current_acceleration = max(abs(gps_acceleration), imu_acceleration)
    state.acceleration = current_acceleration
    uncertainty = state.get('speed_accuracy_m_s')
    previous_uncertainty = state.get('previous_speed_accuracy_m_s')
    valid_uncertainty = all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0
                            for value in (uncertainty, previous_uncertainty))
    noise = 3*math.hypot(uncertainty, previous_uncertainty) if valid_uncertainty else 0.
    # A reported speed accuracy is a measurement property, not a raised g limit.
    lower_acceleration = max(0., abs(raw_speed-prev_speed)/3.6-noise)/dt
    state.acceleration_lower_bound = max(lower_acceleration, imu_acceleration)

    # 2. Yön Hesabı
    lat_diff = raw_lat - prev_lat
    lon_diff = raw_lon - prev_lon

    current_heading = prev_heading
    if abs(lat_diff) > 0.000001 or abs(lon_diff) > 0.000001:
        current_heading = math.degrees(math.atan2(lon_diff * math.cos(math.radians(raw_lat)), lat_diff))

    heading_diff = abs((current_heading - prev_heading + 180.) % 360. - 180.)

    state.observed_heading = current_heading
    state.heading_difference = heading_diff
    return current_acceleration, heading_diff, current_heading


def run_firewall_rules(state, raw_lat, raw_lon, raw_cn0, raw_speed, conf_cn0_nom, conf_snr_percent, conf_accel, conf_heading, dt=0.5):
    """Apply project-configured rules to measurements and report anomaly labels.

    A low C/N0 or kinematic discontinuity is not sufficient to prove jamming or
    spoofing; callers should describe the result as an indicator or alert.
    """
    if (not all(math.isfinite(value) for value in (raw_lat, raw_lon, raw_speed))
            or not -89.999 <= raw_lat <= 89.999 or not -180 <= raw_lon <= 180 or raw_speed < 0):
        raise ValueError("Invalid GNSS position/speed")
    attack_type = "NORMAL"
    detailed_reason = ""

    # 0. Başlangıç Koşulları
    if "spoof_persistence" not in state: state.spoof_persistence = 0
    if "jamming_state" not in state: state.jamming_state = "none"

    # Kinematic indicators use the sample interval; this does not validate the
    # physical model or make the configured thresholds universal.
    current_accel_ms2, heading_diff, current_heading = analyze_kinematics(
        state, raw_lat, raw_lon, raw_speed, conf_heading, dt=dt)

    # 1. Signal-quality / receiver-interference indicators.
    jamming_state = getattr(state, "jamming_state", "none")
    receiver_rf = state.get("receiver_rf_observables", {})
    receiver_itfm = receiver_rf.get("jamming_state")
    receiver_itfm_alarm = (isinstance(receiver_itfm, (int, float))
                           and math.isfinite(receiver_itfm) and receiver_itfm in (2, 3))
    # A lost navigation fix is evidence of GNSS service loss only after this
    # receiver previously acquired a valid solution. Startup without a fix is
    # not an alarm. Report possible interference rather than asserting cause.
    fix_valid = receiver_rf.get("fix_valid")
    fix_loss_alarm = False
    if isinstance(fix_valid, (bool, int, float)) and math.isfinite(float(fix_valid)):
        if bool(fix_valid):
            state.fix_acquired = True
            state.fix_loss_duration_s = 0.
        elif state.get("fix_acquired", False):
            # Do not infer a continuous outage across an unobserved data gap.
            # Invalid-fix time accumulates only across intervals shorter than
            # the 3 s alarm duration; a larger gap restarts the observation.
            if dt < 3.:
                state.fix_loss_duration_s = float(state.get("fix_loss_duration_s", 0.)) + dt
            else:
                state.fix_loss_duration_s = 0.
            fix_loss_alarm = state.fix_loss_duration_s >= 3. - 1e-6
        else:
            state.fix_loss_duration_s = 0.
    else:
        # Missing fix-validity telemetry breaks the evidence of continuity.
        state.fix_loss_duration_s = 0.

    # Configurable nominal comparison with a project floor; not a receiver-
    # independent or literature-standard jamming threshold.
    dynamic_threshold = max(config.JAMMING_CN0_CRITICAL, conf_cn0_nom * conf_snr_percent)

    if receiver_itfm_alarm:
        attack_type = "JAMMING"
        state.rule_fresh_evidence = True
        detailed_reason = f"INTERFERENCE: Alıcı MON-RF durumu {int(receiver_itfm)}"
    elif fix_loss_alarm:
        attack_type = "GNSS_FIX_LOSS"
        detailed_reason = (f"GNSS fix kaybı {state.fix_loss_duration_s:.1f} s sürdü; "
                           "olası girişim, saldırı türü tek başına belirlenemez")
    elif raw_cn0 < dynamic_threshold or jamming_state == "basarili":
        attack_type = "JAMMING"
        detailed_reason = f"INTERFERENCE: C/N0 Düşüşü ({raw_cn0:.1f} < {dynamic_threshold:.1f} dB-Hz)"

    # 2. Kinematic anomaly indicators (cause is not identified here).
    if attack_type == "NORMAL":
        # A. Derived-acceleration inconsistency indicator. The project setting
        # is not a certified vehicle limit or a literature-derived universal threshold.
        g_equivalent = state.acceleration_lower_bound / 9.81

        # Kullanıcı slider'dan gelen ivme eşiğini g cinsine çeviriyoruz
        # config.ACCEL_SLIDER_TO_G_FACTOR: Slider [0-100] → g dönüşüm faktörü (örn. 40 → 2.0g)
        g_threshold = conf_accel / config.ACCEL_SLIDER_TO_G_FACTOR
        if g_equivalent > g_threshold:
            attack_type = "SPOOFING"
            detailed_reason = f"İvme tutarsızlığı göstergesi (kinematik): türetilmiş ivme ({g_equivalent:.2f}g > {g_threshold:.2f}g proje eşiği)"

        # B. Heading-change indicator; without an independent attitude/course
        # reference it is not proof of an aerodynamic or spoofing event.
        elif heading_diff > conf_heading and raw_speed > 30.0:
            attack_type = "SPOOFING"
            detailed_reason = f"Baş yönü değişimi göstergesi (kinematik): {heading_diff:.0f}°"

        # C. Coordinate discontinuity indicator.
        else:
            dist_km = calculate_distance_km(raw_lat, raw_lon, state.prev_lat, state.prev_lon)
            reachable_km = max(.05, min(abs(state.prev_speed), config.MAX_INS_SPEED) / 3600 * dt * 3)
            if dist_km > reachable_km: # 10 km/s -> İmkansız hız (Mach 30+)
                attack_type = "SPOOFING"
                detailed_reason = f"GNSS konum süreksizliği göstergesi (Konum Sıçraması: {dist_km:.1f} km)"

    previous_cn0 = state.get("previous_observed_cn0")
    if previous_cn0 is not None and math.isfinite(previous_cn0) and math.isfinite(raw_cn0):
        if abs(raw_cn0-previous_cn0) > 10.:
            state.vae_buffer = []
            state.vae_anomaly_streak = 0
            state.rf_anomaly_streak = 0
    state.previous_observed_cn0 = raw_cn0
    if "Konum Sıçraması" in detailed_reason:
        state.vae_buffer = []
        state.vae_anomaly_streak = 0
        state.rf_anomaly_streak = 0
    consistency = check_inertial_consistency(state, raw_lat, raw_lon, raw_speed, dt, raw_cn0)
    if consistency.get("discontinuity", False):
        # Jump detection must not depend on which physical reason won priority.
        # A heading violation can mask the jump reason on GNSS recovery.
        state.vae_buffer = []
        state.vae_anomaly_streak = 0
        state.rf_anomaly_streak = 0
        # The bearing of a coordinate jump is not a measured vehicle course.
        # Preserve the previous course for the next observation; keep this
        # frame's heading_difference intact so the jump still raises an alarm.
        state.observed_heading = state.get("prev_heading", current_heading)
    if attack_type == "NORMAL" and consistency.get("detected", False):
        attack_type = "SPOOFING"
        detailed_reason = f"GNSS/IMU tutarsızlık göstergesi: {consistency['error_m']:.1f} m"

    # 3. KARARLILIK (Hysteresis Loop)
    # A retained alarm is not a fresh observation of an attack.
    state.rule_fresh_evidence = attack_type != "NORMAL"
    if attack_type == "SPOOFING":
        state.spoof_persistence = 5
    elif attack_type == "JAMMING":
        state.spoof_persistence = 0

    if attack_type == "NORMAL" and state.spoof_persistence > 0:
        attack_type = "SPOOFING"
        detailed_reason = "Sinyal kararlılık kuralı: önceki ölçüm tutarsızlığı sürüyor"
        state.spoof_persistence -= 1

    return attack_type, detailed_reason


def calculate_metrics(state, attack_type, raw_lat, raw_lon, final_lat, final_lon):
    """
    Labelled-replay or simulation metrics; not a field-performance estimate.
    """
    # 2. RMSE (Root Mean Square Error) Hesaplama
    # Gerçek (true) konum ile kararlaştırılan (final) konum arasındaki mesafe (hata)
    # Hardware GPS is not an independent position reference.
    reference = state.get("reference_position")
    has_reference = reference is not None or (not state.get("use_live_gps", False) and not state.get("use_dataset_mode", False))
    if reference is None and has_reference:
        reference = (state.true_lat, state.true_lon)
    current_error_m = calculate_distance_km(*reference, final_lat, final_lon)*1000 if has_reference else None
    if "rmse_buffer" not in state: state.rmse_buffer = []
    if current_error_m is not None:
        state.rmse_buffer.append(current_error_m**2)
    if len(state.rmse_buffer) > 30: state.rmse_buffer.pop(0)

    rmse = math.sqrt(sum(state.rmse_buffer) / len(state.rmse_buffer)) if has_reference and state.rmse_buffer else float("nan")

    if state.get("use_live_gps", False) or (state.get("use_dataset_mode", False)
                                               and not state.get("ground_truth_available", True)):
        return (float("nan"),) * 5 + (rmse,)
    is_actual_attack = (state.attack_mode != "normal")
    is_detected = (attack_type != "NORMAL")

    # 1. Pd ve Pfa Sayaçları
    if is_actual_attack:
        if is_detected:
            state.stats_tp += 1
            if not getattr(state, "is_attack_detected", False): # Time to Detect (TTD) Başlangıcı
                state.is_attack_detected = True
                if not hasattr(state, "attack_counts"):
                    state.attack_counts = {"Jamming": 0, "Spoofing": 0}
                state.attack_counts["Jamming" if "JAMMING" in attack_type else "Spoofing"] += 1

                if getattr(state, "attack_start_time", None):
                    if state.get("use_dataset_mode", False) and state.get("attack_start_sample_time") is not None:
                        ttd = max(0., state.sample_time_s - state.attack_start_sample_time) * 1000
                    else:
                        ttd = (time.time() - state.attack_start_time) * 1000 # ms
                    state.stats_response_times.append(ttd)
                    state.last_resp = ttd
        else:
            state.stats_fn += 1
    else:
        if is_detected:
            state.stats_fp += 1
        else:
            state.stats_tn += 1

    # 3. İstatistiksel Hesaplamalar (P_d, P_fa, F1)
    tp, fp, fn, tn = state.stats_tp, state.stats_fp, state.stats_fn, state.stats_tn

    p_d = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else float("nan")
    p_fa = (fp / (fp + tn)) * 100 if (fp + tn) > 0 else float("nan")
    precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else float("nan")
    f1 = 200 * tp / (2*tp + fp + fn) if (2*tp + fp + fn) > 0 else float("nan")

    ttd_avg = sum(state.stats_response_times) / len(state.stats_response_times) if state.stats_response_times else float("nan")

    return p_d, p_fa, precision, f1, ttd_avg, rmse
