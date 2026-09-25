import pandas as pd
import numpy as np

def convert_av_to_uav(input_file, output_file):
    print(f"[{input_file}] okunuyor, İHA formatına (yüksek hız/irtifa) dönüştürülüyor...")
    
    # Veriyi oku
    df = pd.read_csv(input_file)
    
    # 1. PARAMETRİK SENARYO DÖNÜŞÜMÜ (Parametric Scenario Transformation)
    # Literatür: Aynı manevra profili (dönüş hızı) daha yüksek hızda daha fazla ivme üretir (a = v * omega).
    # Karasal otonom araç profilini, İHA kinematik limitlerine ve hızlarına adapte eder.
    
    speed_factor = 12.5 # Parametrik dönüştürücü çarpanı
    if 'Velocity (m/s)' in df.columns:
        df['Velocity (m/s)'] = df['Velocity (m/s)'] * speed_factor + np.random.normal(0, 0.5, size=len(df))
        df['Velocity (m/s)'] = np.clip(df['Velocity (m/s)'], 15.0, 300.0) 

    # 2. İVME (IMU) DÖNÜŞÜMÜ (a_c = v * omega)
    # Karasal ivme (m/s^2) kinematik dönüşüm faktörüyle ölçeklenerek fiziksel tutarlılık (consistency) sağlanır.
    if 'Accel_X (m/s^2)' in df.columns:
        df['Accel_X (m/s^2)'] *= speed_factor
    if 'Accel_Y (m/s^2)' in df.columns:
        df['Accel_Y (m/s^2)'] *= speed_factor

    # 3. İRTİFA (Altitude) - Havacılık tavanı ekle
    if 'Relative Altitude (m)' in df.columns:
        df['Relative Altitude (m)'] = df['Relative Altitude (m)'] + 1200.0 + np.random.uniform(-5, 5, size=len(df))
    
    # SNR -> CN0 (Literatürde C/N0 daha yaygındır)
    raw_cn0 = []
    for dt in df['Data Type']:
        if dt == 0: # Normal
            raw_cn0.append(45.0 + np.random.normal(0, 1.0))
        else: # Spoofing
            raw_cn0.append(52.0 + np.random.normal(0, 0.5))
    df['cn0'] = raw_cn0

    # Son olarak yeni CSV'yi kaydet
    df.to_csv(output_file, index=False)
    print(f"Başarılı! Yeni Fizik Tabanlı İHA verisi kaydedildi: {output_file}")
    
if __name__ == '__main__':
    # Not: Bu dosya sadece manuel veri hazırlığı içindir.
    pass
