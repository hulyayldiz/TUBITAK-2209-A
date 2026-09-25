import time
import numpy as np
import pandas as pd
import random
from sensors import simulate_sensors, calculate_distance_km
import config
from detection import run_firewall_rules
from ml_detection import get_hybrid_decision, load_rf_bundle, load_vae_model

# Sahte bir Streamlit Session State oluştur (Headless çalışma için)
class MockState(dict):
    def __getattr__(self, name): return self.get(name)
    def __setattr__(self, name, value): self[name] = value

def run_benchmark(scenario="normal", model_type="hybrid", duration_steps=50, seed=42):
    """
    Belirli bir senaryoda belirli bir modeli test eder.
    seed: Tekrarlanabilir sonuçlar için rastgele tohum.
    """
    random.seed(seed)
    np.random.seed(seed)
    
    state = MockState({
        "true_lat": 38.6744, "true_lon": 39.1942,
        "prev_lat": 38.6744, "prev_lon": 39.1942,
        "last_good_lat": 38.6744, "last_good_lon": 39.1942,
        "prev_speed": 84.0, "prev_heading": 45.0,
        "base_heading": 45.0, "acceleration": 0.0,
        "snr_history": [42.0]*30, "vae_buffer": [],
        "attack_mode": scenario, "prev_attack_mode": "normal",
        "force_reset": True, "fw_state": True,
        "jamming_baseline": 40.0, "jamming_state": "none",
        "stats_tp": 0, "stats_fp": 0, "stats_tn": 0, "stats_fn": 0,
        "stats_response_times": [],
        "attack_start_time": time.time(),
        "is_attack_detected": False,
        "spoof_offset_lat": 0.0,
        "spoof_offset_lon": 0.0,
        "current_row_hash": ""
    })

    detected_count = 0
    response_times = []

    for i in range(duration_steps):
        raw_lat, raw_lon, raw_speed, raw_cn0 = simulate_sensors(state, use_live_gps=False, gps_mode="Seri", dt=0.5)
        
        # VAE Buffer
        feat = [raw_cn0, abs(raw_speed - state.prev_speed), abs(state.prev_heading - 45.0), 0.0]
        state.vae_buffer.append(feat)
        if len(state.vae_buffer) > 10: state.vae_buffer.pop(0)

        rule_type, _ = run_firewall_rules(
            state, raw_lat, raw_lon, raw_cn0, raw_speed, 
            config.NOMINAL_CN0, 0.5, 15.0, 45.0)
        
        t_start = time.perf_counter()
        if model_type == "rule":
            is_attack_detected = (rule_type != "NORMAL")
        elif model_type == "rf":
            _, _, ml_label, _ = get_hybrid_decision(rule_type, feat, state, None)
            is_attack_detected = (ml_label != "NORMAL")
        elif model_type == "vae":
            _, _, _, vae_score = get_hybrid_decision("NORMAL", feat, state, state.vae_buffer)
            is_attack_detected = (vae_score > 0.5)
        else: # Hybrid
            final_type, _, _, _ = get_hybrid_decision(rule_type, feat, state, state.vae_buffer)
            is_attack_detected = (final_type != "NORMAL")
        t_end = time.perf_counter()
        
        # Latans Kaydı (Sadece Hibrit Karar Süresi)
        state.stats_response_times.append((t_end - t_start) * 1000) # ms

        if scenario != "normal" and is_attack_detected:
            detected_count += 1
            response_times.append(i * 0.5) # dt=0.5 sn

    # TPR, FPR ve Müdahale Süresini dön
    tpr = (detected_count / duration_steps) * 100 if scenario != "normal" else 0
    fpr = (detected_count / duration_steps) * 100 if scenario == "normal" else 0
    avg_resp = np.mean(response_times) if response_times else 0
    
    return tpr, fpr, avg_resp

def main():
    scenarios = ["jamming", "spoofing", "normal"]
    models = ["rule", "rf", "vae", "hybrid"]
    iterations = 30 # TÜBİTAK/Akademik standart için 30 iterasyon (Ortalama +- Std için)
    
    print(f"\n[BENCHMARK] Akademik Benchmark Motoru (Iterasyon Sayısı: {iterations})")
    print("-------------------------------------------------------")
    
    summary_data = []

    for sc in scenarios:
        for md in models:
            tprs, fprs, resps = [], [], []
            print(f"Testing Scenario: {sc.upper()} | Model: {md.upper()}...   ", end="\r")
            
            for run in range(iterations):
                t, f, r = run_benchmark(sc, md, duration_steps=500, seed=run*100)
                tprs.append(t)
                fprs.append(f)
                resps.append(r)
            
            # İstatistikleri hesapla
            t_m, t_s = np.mean(tprs), np.std(tprs)
            f_m, f_s = np.mean(fprs), np.std(fprs)
            r_m, r_s = np.mean(resps), np.std(resps)
            
            summary_data.append([
                sc.upper(), 
                md.upper(), 
                f"{t_m:.1f} ± {t_s:.1f}%" if sc != "normal" else "-",
                f"{f_m:.1f} ± {f_s:.1f}%" if sc == "normal" else "-",
                f"{r_m:.2f} ± {r_s:.2f}s" if r_m > 0 else "-"
            ])

    df = pd.DataFrame(summary_data, columns=["Senaryo", "Model", "TPR (Doğru Tespit)", "FPR (Hatalı Alarm)", "Müdahale Süresi"])
    print("\n\n[RESULTS] AKADEMIK PERFORMANS ANALIZI (Ortalama +/- Standart Sapma)")
    print(df.to_markdown(index=False))
    print("\n[HINT] Bu ciktilari PROJE_RAPORU.md 'Bulgular' bolumune dogrudan kopyalayabilirsiniz.")

if __name__ == "__main__":
    main()
