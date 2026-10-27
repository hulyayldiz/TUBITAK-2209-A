"""
Sensör Simülasyon ve Donanım Entegrasyonu Modülü (Hareketli Simülasyon v12.0)
Bu modül otonom araçların (İHA/Rover) rotasını, hızını ve GNSS sinyal davranışlarını simüle eder.
"""

import math
import random
import time
import config
try:
    from live_gps import get_gps_from_tcp, get_gps_from_serial
except ImportError:
    get_gps_from_tcp = get_gps_from_serial = None

try:
    from mpu6050 import get_live_imu
except ImportError:
    get_live_imu = None


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Haversine formülü ile iki koordinat arası mesafe hesaplama."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def simulate_sensors(state, use_live_gps=False, gps_mode="Seri", port="COM3", host="0.0.0.0", tcp_port=9000, dt=0.5):
    """Merkezi sensör ve hareket simülasyonu motoru."""
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be positive and finite")

    state.cn0_available = not use_live_gps
    previous_true_speed = state.get("current_speed", state.get("prev_speed", 40.0))
    previous_true_heading = state.get("current_heading", state.get("prev_heading", 45.0))
    # 1. VERİ KAYNAĞI SEÇİMİ (Donanım vs Simülasyon)
    if use_live_gps:
        # Donanımdan (TCP/UDP veya Seri) gerçek veriyi çek
        raw_lat_hw, raw_lon_hw, raw_speed_hw, raw_heading_hw = None, None, None, None
        if gps_mode == "Seri" and get_gps_from_serial:
            raw_lat_hw, raw_lon_hw, raw_speed_hw, raw_heading_hw = get_gps_from_serial(state, port=port)
        elif gps_mode != "Seri" and get_gps_from_tcp:
            raw_lat_hw, raw_lon_hw, raw_speed_hw, raw_heading_hw = get_gps_from_tcp(state, host=host, port=tcp_port)
        
        if raw_lat_hw is not None:
            # Gerçek veri Geldiyse: 'true' değerleri güncelle
            state.true_lat = raw_lat_hw
            state.true_lon = raw_lon_hw
            state.current_speed = raw_speed_hw
            if raw_heading_hw is not None:
                state.current_heading = raw_heading_hw
        else:
            return None
        state.imu_data = (get_live_imu(raw_speed_hw, raw_heading_hw or 0.0) if get_live_imu else
                          {"accel": {"x": 0., "y": 0., "z": 9.81}, "real": False})
        from imu_processing import navigation_imu
        state.imu_data = navigation_imu(state.imu_data)
        sample_time = state.get("gps_sample_time", time.monotonic())
        previous_time = state.get("last_live_sample_time")
        state.sample_dt = sample_time-previous_time if previous_time is not None and sample_time > previous_time else .5
        state.last_live_sample_time = sample_time
        state.acceleration = 0.
        state.cn0_available = math.isfinite(state.get("gps_cn0", float("nan")))
        # RMC/GGA carry no C/N0. Do not fabricate signal measurements or add attacks/noise.
        return raw_lat_hw, raw_lon_hw, raw_speed_hw, state.get("gps_cn0", float("nan"))
    else:
        # HAREKET MODELİ (İHA / Araç Dinamiği - Sadece Donanım Kapalıyken)
        if "current_heading" not in state: state.current_heading = 45.0
        if "current_speed" not in state: state.current_speed = 40.0
        
        # Gerçekçi hız ve yön değişimleri (Sarsıntı/Rüzgar etkisi)
        state.current_speed += random.uniform(-1.0, 1.2)
        state.current_speed = max(30.0, min(120.0, state.current_speed))
        
        state.current_heading += random.uniform(-2.0, 2.0)
        
        # Yeni koordinatları hesapla (Gerçek Hareket)
        dist = (state.current_speed / 3600.0) * dt # km
        rad_h = math.radians(state.current_heading)
        
        # 1 Derece Enlem ~111km, Boylam ~111*cos(lat)km
        d_lat = (dist * math.cos(rad_h)) / 111.32
        d_lon = (dist * math.sin(rad_h)) / (111.32 * math.cos(math.radians(state.true_lat)))
        
        state.true_lat += d_lat
        state.true_lon += d_lon
    
    # 2. SALDIRI ETKİLERİ VE DOĞAL GÜRÜLTÜ (Thermal Noise Model)
    attack_mode = getattr(state, "attack_mode", "normal").strip().lower()
    
    # Gerçekçi C/N0 Jitter (dB-Hz)
    raw_cn0 = config.NOMINAL_CN0 + random.uniform(-1.0, 1.0)
    
    # Konumsal Sapma (Standard Jitter - cm seviyesi)
    noise_lat = random.uniform(-0.000003, 0.000003) 
    noise_lon = random.uniform(-0.000003, 0.000003)
    
    raw_lat, raw_lon = state.true_lat + noise_lat, state.true_lon + noise_lon
    raw_speed = state.current_speed + random.uniform(-0.2, 0.2)

    if attack_mode in ("spoofing", "slow_spoofing", "stealth_spoofing"):
        # Sahte Sinyal (Meaconing/Spooling): Alıcıyı gerçek rotadan saptırır
        if "spoof_offset_lat" not in state: 
            state.spoof_offset_lat = 0.0
            state.spoof_offset_lon = 0.0
            state.spoof_speed_offset = 0.0
        
        # dict.get or handling None directly
        lat_offset = state.get("spoof_offset_lat") or 0.0
        lon_offset = state.get("spoof_offset_lon") or 0.0
        spd_offset = state.get("spoof_speed_offset") or 0.0
        
        if attack_mode in ("slow_spoofing", "stealth_spoofing"):
            # 0.5 m/s eastward pull; plausible C/N0 and reported speed.
            state.spoof_offset_lat = lat_offset
            state.spoof_offset_lon = lon_offset + 0.5 * dt / (111320 * math.cos(math.radians(state.true_lat)))
            state.spoof_speed_offset = spd_offset
        else:
            state.spoof_offset_lat = lat_offset + 0.001 * (dt / 0.5)
            state.spoof_offset_lon = lon_offset + 0.0015 * (dt / 0.5)
            state.spoof_speed_offset = spd_offset + random.uniform(0.5, 2.0) * (dt / 0.5)
        
        raw_lat += state.spoof_offset_lat
        raw_lon += state.spoof_offset_lon
        raw_speed += state.spoof_speed_offset # Kademeli ve gerçekçi sahte hız artışı
        if attack_mode != "stealth_spoofing":
            raw_cn0 = random.uniform(42, 48)
        # Stealth variant preserves the normal C/N0 distribution; it is not in training.
    else:
        # Kademeli sıfırlama (Gradual Recovery - Fiziksel Gerçekçilik)
        # Spoofing biterken araç anında ışınlanmaz; sinyal kademeli normale döner.
        # Exponential decay preserves the 0.5 s behavior at arbitrary sample rates
        # without negative offsets when a sample arrives late.
        decay = 1. - .85 ** (dt / .5)
        state.spoof_offset_lat = state.get("spoof_offset_lat", 0.0) * (1.0 - decay)
        state.spoof_offset_lon = state.get("spoof_offset_lon", 0.0) * (1.0 - decay)
        state.spoof_speed_offset = state.get("spoof_speed_offset", 0.0) * (1.0 - decay)
        
    if attack_mode == "jamming":
        # Interference (Sinyal Boğma): 
        # Literatür: Pozisyon hatası C/N0 ile karesel orantılı artar (Code Tracking Loop Jitter)
        raw_cn0 = random.uniform(8.0, 18.0) # Jamming altındaki C/N0 (dB-Hz)
        
        # Sinyal düştükçe DLL (Delay Locked Loop) jitter'ı artar.
        # Literatür Formülü: Position_Sigma ∝ sqrt(1 / C/N0)
        error_multiplier = max(1.0, math.sqrt(config.NOMINAL_CN0 / max(1.0, raw_cn0)) * (config.JAMMING_ERROR_FACTOR / 10.0))
        
        raw_lat += random.uniform(-0.0001, 0.0001) * error_multiplier
        raw_lon += random.uniform(-0.0001, 0.0001) * error_multiplier
        raw_speed *= random.uniform(0.70, 0.90) 

    # IMU simulation is independent of attacked GNSS speed.
    if use_live_gps and get_live_imu:
        state.imu_data = get_live_imu(state.current_speed, state.prev_heading)
    else:
        heading = math.radians(state.current_heading)
        old_heading = math.radians(previous_true_heading)
        velocity = state.current_speed / 3.6
        old_velocity = previous_true_speed / 3.6
        ax = (velocity * math.cos(heading) - old_velocity * math.cos(old_heading)) / dt
        ay = (velocity * math.sin(heading) - old_velocity * math.sin(old_heading)) / dt
        state.imu_data = {"accel": {"x": ax + random.gauss(0, .02),
                                    "y": ay + random.gauss(0, .02), "z": 9.81},
                          "gyro": {"x": 0.0, "y": 0.0, "z": (state.current_heading-previous_true_heading)/dt},
                          "frame": "navigation", "heading_independent": True,
                          "heading_deg": state.current_heading + random.gauss(0, .2),
                          "heading_std_deg": .2, "noise_std_m_s2": .02,
                          "bias_std_m_s2": .002, "real": False}
    imu = state.imu_data["accel"]
    state.acceleration = math.hypot(imu["x"], imu["y"])

    return raw_lat, raw_lon, raw_speed, raw_cn0

def update_ins_model(state, dt=2.0):
    """INS (Ataletsel Navigasyon) / Otopilot Modeli."""
    # Otopilot, en son 'güvenli' bilinen hızı ve yönü kullanarak tahmin yürütür.
    if "ins_lat" not in state or state.get("ins_lat") is None:
        state.ins_lat = getattr(state, "last_good_lat", config.DEFAULT_LAT)
        state.ins_lon = getattr(state, "last_good_lon", config.DEFAULT_LON)
    
    # Keep INS velocity/course distinct from the raw IMU channels. Their
    # independence depends on the input source and must be verified per dataset.
    ins_speed = getattr(state, "ins_speed", 40.0)
    if ins_speed is None: ins_speed = 40.0
    
    ins_heading = getattr(state, "ins_heading", 0.0)
    if ins_heading is None: ins_heading = getattr(state, "current_heading", 45.0) or 0.0
    
    # Rastgele Drift (Hata Birikimi) Simülasyonu
    drift = random.uniform(-config.INS_DRIFT_RATE, config.INS_DRIFT_RATE)
    ins_heading += drift * dt
    state.ins_heading = ins_heading
    
    # Gerçekçi INS karesel büyüme (t^2 error): Yavaş drift eden sabit ivme (Random Walk)
    accel_bias = getattr(state, 'accel_bias', None)
    if accel_bias is None:
        accel_bias = random.uniform(-0.05, 0.05)
    accel_bias += random.uniform(-0.005, 0.005) * dt
    state.accel_bias = accel_bias
    
    # Doğru fiziksel yaklaşım: İvme hatasını (bias) hıza entegre et (V = V0 + a*t)
    # Burada çifte entegrasyondan kaçınmak için sadece hız güncellenip mesafeye dönüştürülüyor
    ins_speed_ms = ins_speed / 3.6
    ins_speed_ms += state.accel_bias * dt
    ins_speed_ms = max(0.0, ins_speed_ms)
    
    ins_speed = ins_speed_ms * 3.6
    state.ins_speed = ins_speed
        
    # Tahmini ilerleme (Kör uçuş) - Hızı entegre ederek mesafe (X = V*t)
    dist_m = ins_speed_ms * dt
    rad_h = math.radians(ins_heading)
    
    state.ins_lat += (dist_m / 111320.0) * math.cos(rad_h)
    state.ins_lon += (dist_m / (111320.0 * math.cos(math.radians(state.ins_lat)))) * math.sin(rad_h)
    
    return state.ins_lat, state.ins_lon, ins_speed
