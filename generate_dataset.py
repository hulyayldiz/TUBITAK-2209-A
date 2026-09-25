import pandas as pd
import numpy as np
import math

def generate_realistic_trajectory():
    rows = []
    
    # Başlangıç parametreleri (Elazığ civarları)
    lat = 38.6744
    lon = 39.1942
    speed = 84.0
    heading = 45.0 # derece
    snr = 42.0

    for t in range(300):
        attack_flag = "normal"
        out_speed = speed + np.random.uniform(-1, 1)
        out_snr = snr + np.random.uniform(-1.5, 1.5)
        out_lat = lat
        out_lon = lon

        # 1. Senaryo: 40-70 saniyeleri arası JAMMING
        if 40 <= t <= 70:
            attack_flag = "jamming"
            out_snr = 15.0 + np.random.uniform(-5, 5) # SNR çok düşüyor
            
        # 2. Senaryo: 120-150 saniyeleri arası SPOOFING (Işınlanma / Teleport)
        elif 120 <= t <= 150:
            attack_flag = "spoofing"
            out_snr = 55.0 + np.random.uniform(-1, 1) # Spoofing sinyali güçlü gelir
            out_lat = 40.0 + np.random.uniform(-0.01, 0.01) # Konum bambaşka bir yere uçtu
            out_lon = 45.0 + np.random.uniform(-0.01, 0.01)
            out_speed = 220.0 + np.random.uniform(-10, 10) # 3500 hızı çok gerçek dışıydı, 220 km/h İHA sınırına çekildi
            
        # Fiziksel hareket devam ediyor
        step = (speed / 3600.0) / 111.0
        lat += step * math.cos(math.radians(heading))
        lon += step * math.sin(math.radians(heading))

        rows.append({
            "Zaman": f"2026-04-04 14:{t//60:02d}:{t%60:02d}",
            "Latitude": out_lat,
            "Longitude": out_lon,
            "Speed": out_speed,
            "SNR": out_snr,
            "Attack_Flag": attack_flag
        })

    df = pd.DataFrame(rows)
    df.to_csv("ornek_dron_saldiri_logu.csv", index=False)
    print("CSV başarıyla oluşturuldu!")

if __name__ == "__main__":
    generate_realistic_trajectory()
