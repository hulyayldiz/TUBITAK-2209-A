import pandas as pd
import numpy as np

def create_combined_attack(input_file, output_file):
    print("Gerçek veri seti alınıyor, hem Jamming hem Spoofing barındıracak şekilde kombine ediliyor...")
    df = pd.read_csv(input_file)
    
    # İHA Korumaları
    if 'Velocity (m/s)' in df.columns:
        df['Velocity (m/s)'] = np.clip(df['Velocity (m/s)'] * 3.5 + np.random.uniform(-1, 1, size=len(df)), 15.0, 120.0) 
    if 'Relative Altitude (m)' in df.columns:
        df['Relative Altitude (m)'] = df['Relative Altitude (m)'] + 1200.0 + np.random.uniform(-5, 5, size=len(df))
    
    # 0 -> Normal, 1 -> Spoofing, 2 -> Jamming
    Data_Types = []
    SNR_Values = []
    
    for i, dt in enumerate(df['Data Type']):
        snr_noise = np.random.uniform(-1.5, 1.5)
        # SÜPER KOMBİNE SENARYO TASARIMI:
        # Satır 0 - 30: NORMAL
        # Satır 31 - 80: PURE JAMMING (Sinyal Boğma - Süresi Uzatıldı)
        # Satır 81+: SPOOFING (Daha Jamming bitmeden araya sahte ışınlanma koordinatları giriyor)
        
        if i > 8 and i < 50: 
            # JAMMING ALANI! (Data Type = 2)
            Data_Types.append(2)
            SNR_Values.append(15.0 + snr_noise) # Sinyal 40'tan 15'e çakıldı
        elif dt == 1 or i >= 50 and i < 80:
            # SPOOFING ALANI! (Data Type = 1)
            Data_Types.append(1)
            SNR_Values.append(55.0 + snr_noise) # Sahte ve güçlü sinyal
        else:
            # NORMAL ALAN
            Data_Types.append(0)
            SNR_Values.append(42.0 + snr_noise) # Klasik sağlıklı sinyal
            
    df['Data Type'] = Data_Types
    df['Sinyal Gucu (SNR)'] = SNR_Values

    df.to_csv(output_file, index=False)
    print(f"Başarılı! Yeni Kombine Veri Kaydedildi: {output_file}")
    
if __name__ == '__main__':
    create_combined_attack('dataset_gercek/AV-GPS-Dataset-1.csv', 'dataset_gercek/Kombine-Gercek-IHA-Saldirisi.csv')
