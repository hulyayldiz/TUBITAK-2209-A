import pandas as pd
import numpy as np
import os

def create_mock_dataset():
    print("⏳ AV-GPS-Dataset-1.csv bulunamadı, mock verilerle oluşturuluyor...")
    np.random.seed(42)
    n_samples = 500
    
    data = {
        'time': range(n_samples),
        'lat': np.linspace(40.0, 40.05, n_samples) + np.random.normal(0, 0.0001, n_samples),
        'lon': np.linspace(30.0, 30.05, n_samples) + np.random.normal(0, 0.0001, n_samples),
        'speed': np.random.normal(15.0, 2.0, n_samples), # 15 m/s
        'label': ['NORMAL'] * (n_samples - 100) + ['SPOOFING'] * 100
    }
    
    df = pd.DataFrame(data)
    df.to_csv("AV-GPS-Dataset-1.csv", index=False)
    print("✅ AV-GPS-Dataset-1.csv başarıyla oluşturuldu.")

if __name__ == "__main__":
    if not os.path.exists("AV-GPS-Dataset-1.csv"):
        create_mock_dataset()
