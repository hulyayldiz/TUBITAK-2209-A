# PROJE TEKNİK MİMARİSİ VE VERİ AKIŞI 🛰️🛡️

Bu doküman, "GNSS Sinyal Bütünlüğü için Hibrit Yapay Zeka Destekli Otonom Müdahale Sistemi"nin iç işleyişini ve modüler yapısını görselleştirmek için hazırlanmıştır.

## 1. Veri Akış Diyagramı (Data Flow)

Aşağıdaki şema, ham GPS verisinin sisteme girişinden itibaren nasıl işlendiğini ve otonom müdahalenin nasıl tetiklendiğini gösterir:

```mermaid
graph TD
    A[GNSS Alıcısı / Simülatör] -->|Ham Veri: Lat, Lon, SNR, Hız| B(Sensör İşleme Modülü)
    B --> C{Güvenlik Duvarı - Mod 1: Kural Tabanlı}
    C -->|Fiziksel Kontrol: İvme/Yön| D[ML Özellik Vektörü Hazırlama]
    C -->|Işınlanma Kontrolü| D
    
    subgraph Karar Motoru - Hibrit Karar
        D --> E[Mod 2: Random Forest - Sınıflandırma]
        D --> F[Mod 3: LSTM-VAE - Anomali Tespiti]
        E --> G[Ağırlıklı Oylama Ünitesi]
        F --> G
        C -->|Kritik İhlal| G
    end

    G -->|Skor > 0.5| H{Müdahale Katmanı}
    H -->|TEHDİT| I[INS Otopilot Devrede - Otonom Rota]
    H -->|NORMAL| J[Standart Navigasyon]
    I --> K[Siren ve Olay Kaydı - SIEM]
```

## 2. Modüler Mimari Yapısı

Projenin dosya yapısı ve modüller arası bağımlılıklar:

```mermaid
graph LR
    subgraph UI_Layer
        Main[main.py]
        UI[ui.py]
    end

    subgraph Logic_Layer
        Detect[detection.py]
        ML[ml_detection.py]
        Sat[satellites.py]
    end

    subgraph Data_Layer
        Sensors[sensors.py]
        Live[live_gps.py]
        Models[models/lstm_vae.py]
    end

    Main --> UI
    Main --> Logic_Layer
    Logic_Layer --> Data_Layer
```

## 3. Özgün Teknolojiler ve Yenilikler
1.  **Dinamik Eşikleme:** Hıza duyarlı ivme analizi.
2.  **Zero-Day Koruma:** LSTM-VAE ile imzasız saldırı tespiti.
3.  **Hibrit Oylama:** Üç farklı karar vericinin (Kural, RF, VAE) sonuçları ağırlıklandırması.
