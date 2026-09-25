"""
Güvenlik Duvarı ve Anomali Tespit Algoritmaları (Akademik Versiyon)
Gelen sensör verilerini analiz eder, fiziksel tutarsızlıkları (G-Force, Aerodinamik Sapma)
tespit eder ve performans metriklerini (P_d, P_fa, RMSE) hesaplar.
"""

import math
import time
import config
from sensors import calculate_distance_km

def analyze_kinematics(state, raw_lat, raw_lon, raw_speed, conf_heading, dt=0.5):
    """
    Kinematik analizi (Hız, İvme, Yörünge) gerçekleştirir.
    Literatür: a = dv/dt formülü ile anlık ivme hesaplanır.
    """
    prev_speed = getattr(state, "prev_speed", raw_speed)
    prev_lat = getattr(state, "prev_lat", raw_lat)
    prev_lon = getattr(state, "prev_lon", raw_lon)
    prev_heading = getattr(state, "prev_heading", 0.0)

    # 1. Ivme Hesabı (dV / dt)
    # Literatür: İvme hesabı için varsa IMU verisi (direkt ölçüm) yoksa GPS türevi (dolaylı) kullanılır.
    current_acceleration = getattr(state, "acceleration", 0.0)
    
    # IMU verisi yoksa veya simüle ediliyorsa GPS türevi kullan (m/s^2 birimine çevirerek)
    speed_diff_ms = (raw_speed - prev_speed) / 3.6 # km/sa -> m/s
    calc_accel_ms2 = speed_diff_ms / dt # a = dv/dt
    
    # IMU verisi çok düşükse veya yoksa GPS tabanlı türevi önceliklendir (hata payı için)
    if abs(current_acceleration) < 0.001: 
        current_acceleration = calc_accel_ms2
    
    state.acceleration = current_acceleration # Magnitude m/s2
    
    # 2. Yön Hesabı
    lat_diff = raw_lat - prev_lat
    lon_diff = raw_lon - prev_lon
    
    current_heading = prev_heading
    if abs(lat_diff) > 0.000001 or abs(lon_diff) > 0.000001:
        current_heading = math.degrees(math.atan2(lon_diff, lat_diff))

    heading_diff = abs(current_heading - prev_heading)
    if heading_diff > 180.0:
        heading_diff = 360.0 - heading_diff

    return current_acceleration, heading_diff, current_heading


def run_firewall_rules(state, raw_lat, raw_lon, raw_cn0, raw_speed, conf_cn0_nom, conf_snr_percent, conf_accel, conf_heading, dt=0.5):
    """
    Akademik Güvenlik Duvarı Kontrol Motoru (IEEE/ION Standartları).
    Hiyerarşi: Interference (Denial of Service) > Meaconing/Spoofing (Signal Manipulation)
    """
    attack_type = "NORMAL"
    detailed_reason = ""
    
    # 0. Başlangıç Koşulları
    if "spoof_persistence" not in state: state.spoof_persistence = 0
    if "jamming_state" not in state: state.jamming_state = "none"

    # Kinematik analiz (dt parametresi ile akademik doğruluk sağlandı)
    current_accel_ms2, heading_diff, current_heading = analyze_kinematics(
        state, raw_lat, raw_lon, raw_speed, conf_heading, dt=dt)

    # 1. INTERFERENCE ANALİZİ (Jamming - Root Cause Hiyerarşisi)
    # Literatür: C/N0 (Carrier-to-Noise density ratio) birimi dB-Hz'dir. 
    # Sinyal gücü nominalden belirli bir % (Adapatif Eşik) altına düşerse DoS/Jamming kabul edilir.
    jamming_state = getattr(state, "jamming_state", "none")
    
    # Dinamik Eşik: Nominal (45) * Kullanıcı % (örn. 0.5) = 22.5 dB-Hz
    # Kullanıcı 0 yapsa bile kritik alt limit (15.0) korunur.
    dynamic_threshold = max(config.JAMMING_CN0_CRITICAL, conf_cn0_nom * conf_snr_percent)
    
    if raw_cn0 < dynamic_threshold or jamming_state == "basarili":
        attack_type = "JAMMING"
        detailed_reason = f"INTERFERENCE: C/N0 Düşüşü ({raw_cn0:.1f} < {dynamic_threshold:.1f} dB-Hz)"
    
    # 2. MEACONING / SPOOFING ANALİZİ (Sinyal manipülasyonu)
    if attack_type == "NORMAL":
        # A. Kinematik Tutarsızlık (G-Kuvveti İhlali)
        # Literatür: Kara araçları 1.5g, İHA'lar manevra tipine göre 2g-5g arası limitlere sahiptir.
        g_equivalent = abs(current_accel_ms2) / 9.81
        
        # Kullanıcı slider'dan gelen ivme eşiğini (km/sa per frame) m/s2 -> g cinsine çevirip kontrol ediyoruz
        # Proje kolaylığı için slider'daki '40' değeri yaklaşık 2g'ye tekabül eder.
        if g_equivalent > (conf_accel / 20.0): # Eşik normalize edildi
            attack_type = "SPOOFING"
            detailed_reason = f"MEACONING: Fiziksel İvme İhlali ({g_equivalent:.2f}g)"
            
        # B. Aerodinamik Tutarsızlık (Keskin Sapma)
        elif heading_diff > conf_heading and raw_speed > 30.0:
            attack_type = "SPOOFING"
            detailed_reason = f"SPOOFING: Aerodinamik Sapma ({heading_diff:.0f}°)"
            
        # C. Kita Değiştirme (Işınlanma - Jump Detection)
        else:
            dist_km = calculate_distance_km(raw_lat, raw_lon, state.last_good_lat, state.last_good_lon)
            if dist_km > 10.0: # 10 km/s -> İmkansız hız (Mach 30+)
                attack_type = "SPOOFING"
                detailed_reason = f"MEACONING: Konum Sıçraması ({dist_km:.1f} km)"

    # 3. KARARLILIK (Hysteresis Loop)
    if attack_type == "SPOOFING":
        state.spoof_persistence = 5 
    elif attack_type == "JAMMING":
        state.spoof_persistence = 0 
        
    if attack_type == "NORMAL" and state.spoof_persistence > 0:
        attack_type = "SPOOFING"
        detailed_reason = "Sinyal Kararlılık Takibi: Potansiyel Tehdit Devam Ediyor"
        state.spoof_persistence -= 1

    return attack_type, detailed_reason


def calculate_metrics(state, attack_type, raw_lat, raw_lon, final_lat, final_lon):
    """
    Akademik Performans Metriklerini (Pd, Pfa, RMSE, TTD) hesaplar.
    """
    is_actual_attack = (state.attack_mode != "normal")
    is_detected = (attack_type in ["JAMMING", "SPOOFING"])

    # 1. Pd ve Pfa Sayaçları
    if is_actual_attack:
        if is_detected:
            state.stats_tp += 1
            if not getattr(state, "is_attack_detected", False): # Time to Detect (TTD) Başlangıcı
                state.is_attack_detected = True
                if not hasattr(state, "attack_counts"):
                    state.attack_counts = {"Jamming": 0, "Spoofing": 0}
                atype = "Interference (Jamming)" if "JAMMING" in attack_type else "Meaconing (Spoofing)"
                state.attack_counts["Jamming" if "JAMMING" in attack_type else "Spoofing"] += 1
                
                if getattr(state, "attack_start_time", None):
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

    # 2. RMSE (Root Mean Square Error) Hesaplama
    # Gerçek (true) konum ile kararlaştırılan (final) konum arasındaki mesafe (hata)
    current_error_m = calculate_distance_km(raw_lat, raw_lon, final_lat, final_lon) * 1000
    if "rmse_buffer" not in state: state.rmse_buffer = []
    state.rmse_buffer.append(current_error_m**2)
    if len(state.rmse_buffer) > 30: state.rmse_buffer.pop(0)
    
    rmse = math.sqrt(sum(state.rmse_buffer) / len(state.rmse_buffer))

    # 3. İstatistiksel Hesaplamalar (P_d, P_fa, F1)
    tp, fp, fn, tn = state.stats_tp, state.stats_fp, state.stats_fn, state.stats_tn
    
    p_d = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0.0
    p_fa = (fp / (fp + tn)) * 100 if (fp + tn) > 0 else 0.0
    precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0.0
    f1 = 2 * (precision * p_d) / (precision + p_d) if (precision + p_d) > 0 else 0.0
    
    ttd_avg = sum(state.stats_response_times) / len(state.stats_response_times) if state.stats_response_times else 0.0

    return p_d, p_fa, precision, f1, ttd_avg, rmse
