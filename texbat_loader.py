"""
TEXBAT Senaryo Entegrasyonu ve Test Aracı
Texas Üniversitesi Spoofing Test Battery (TEXBAT) veri setinin 'Scenario 1: Static Overlap'
senaryosunu yükler, sistemden geçirir ve bağımsız model başarımını raporlar.
Gerçek TEXBAT dosyası yoksa, akademik analiz için TEXBAT özelliklerini taklit eden 
sentetik bir Static Overlap (Sürüklenme) senaryosu üretir.
"""

import pandas as pd
import numpy as np
import datetime
import math

from detection import run_firewall_rules
from ml_detection import get_hybrid_decision
import config

class DummyState:
    def __init__(self):
        self.attack_mode = "normal"
        self.prev_lat = config.DEFAULT_LAT
        self.prev_lon = config.DEFAULT_LON
        self.prev_speed = 40.0
        self.last_good_lat = config.DEFAULT_LAT
        self.last_good_lon = config.DEFAULT_LON
        self.spoof_persistence = 0
        self.jamming_state = "none"
        self.acceleration = 0.0
        
    def get(self, key, default=None):
        return getattr(self, key, default)
        
    def __contains__(self, key):
        return hasattr(self, key)

def create_synthetic_texbat_scenario():
    """Gerçek TEXBAT verisi yoksa, Scenario 1'i (Static Overlap) taklit eder."""
    print("⏳ Gerçek TEXBAT verisi bulunamadı. TEXBAT Scenario 1 (Static Overlap) özellikleri sentetik olarak üretiliyor...")
    
    rows = []
    lat = config.DEFAULT_LAT
    lon = config.DEFAULT_LON
    speed = 40.0
    cn0 = 45.0
    
    # 1. Aşama: 50 saniye NORMAL seyir
    for i in range(50):
        lat += 0.0001
        lon += 0.0001
        cn0 = 45.0 + np.random.normal(0, 0.5)
        speed += np.random.normal(0, 0.2)
        rows.append({"timestamp": i, "lat": lat, "lon": lon, "speed": speed, "cn0": cn0, "label": "NORMAL"})
        
    # 2. Aşama: 50 saniye STATIC OVERLAP (SPOOFING)
    # TEXBAT Scenario 1: Sahte sinyal, gerçek konumda başlar ve yavaş yavaş sürüklenir (Matched power, small offset)
    for i in range(50, 100):
        # Spoofer yavaş yavaş kendi rotasına çeker
        lat += 0.0001 + (i - 50) * 0.00005 
        lon += 0.0001 + (i - 50) * 0.00005
        
        # Power matching (C/N0 hafif artar)
        cn0 = 46.5 + np.random.normal(0, 0.3)
        speed += 1.0 # Spoofing ile oluşan ivmelenme
        rows.append({"timestamp": i, "lat": lat, "lon": lon, "speed": speed, "cn0": cn0, "label": "SPOOFING"})
        
    df = pd.DataFrame(rows)
    df.to_csv("texbat_scenario1_mock.csv", index=False)
    return "texbat_scenario1_mock.csv"

def evaluate_texbat_scenario(csv_path):
    print(f"🚀 TEXBAT Senaryosu '{csv_path}' üzerinden analiz ediliyor...")
    df = pd.read_csv(csv_path)
    
    state = DummyState()
    
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    
    detection_log = []
    
    for idx, row in df.iterrows():
        raw_lat = row['lat']
        raw_lon = row['lon']
        raw_speed = row['speed']
        raw_cn0 = row['cn0']
        true_label = row['label']
        
        # Güvenlik Duvarı
        attack_type, reason = run_firewall_rules(
            state, raw_lat, raw_lon, raw_cn0, raw_speed, 
            config.NOMINAL_CN0, 0.5, 40.0, 45.0, dt=1.0
        )
        
        # ML Analizi (Simüle Edilmiş ML inputları)
        res_err = math.sqrt((raw_lat - state.last_good_lat)**2 + (raw_lon - state.last_good_lon)**2) * 111000
        ml_features = [raw_cn0, state.acceleration, 0.0, res_err]
        
        final_type, conf, ml_label, anomaly = get_hybrid_decision(attack_type, ml_features, state, sequence_buffer=[ml_features]*10)
        
        predicted_attack = final_type != "NORMAL"
        is_actual_attack = true_label != "NORMAL"
        
        if is_actual_attack:
            if predicted_attack: tp += 1
            else: fn += 1
        else:
            if predicted_attack: fp += 1
            else: tn += 1
            
        state.prev_lat = raw_lat
        state.prev_lon = raw_lon
        state.prev_speed = raw_speed
        
        detection_log.append(f"Zaman: {row['timestamp']} | Gerçek: {true_label} | Sistem Kararı: {final_type} ({conf}%)")

    # Metrikleri Hesapla
    pd_rate = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0.0
    pfa_rate = (fp / (fp + tn)) * 100 if (fp + tn) > 0 else 0.0
    precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0.0
    f1 = 2 * (precision * pd_rate) / (precision + pd_rate) if (precision + pd_rate) > 0 else 0.0
    
    report = [
        "=" * 60,
        "TEXBAT SCENARIO 1 (STATIC OVERLAP) DEĞERLENDİRME RAPORU",
        f"Tarih: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        f"Toplam Frame: {len(df)}",
        f"Doğru Pozitif (TP): {tp} | Yanlış Negatif (FN): {fn}",
        f"Doğru Negatif (TN): {tn} | Yanlış Pozitif (FP): {fp}",
        "-" * 60,
        f"Tespit Oranı (Pd): %{pd_rate:.2f}",
        f"Yanlış Alarm Oranı (Pfa): %{pfa_rate:.2f}",
        f"Precision (Kesinlik): %{precision:.2f}",
        f"F1-Score: {f1:.4f}",
        "=" * 60,
        "Özet Log:"
    ]
    report.extend(detection_log[-10:]) # Son 10 frame'i göster
    
    report_text = "\n".join(report)
    print("\n" + report_text)
    
    with open("texbat_evaluation_report.txt", "w", encoding="utf-8") as f:
        f.write(report_text)
    print("\n✅ Sonuçlar 'texbat_evaluation_report.txt' dosyasına kaydedildi.")

if __name__ == "__main__":
    # Never silently substitute synthetic observations for recorded signals.
    from real_data_catalog import available_sources
    if not any(name.startswith('TEXBAT') for name in available_sources()):
        raise SystemExit('Gerçek TEXBAT kaydı yok. Önce python download_real_data.py çalıştırın.')
    from validate_real_data import validate_sources
    validate_sources()
