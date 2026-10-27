# 🛠️ Veri Mühendisliği ve Yardımcı Test Araçları Kılavuzu

23 Ekim 2026 kaynak denetimi: [veri kökeni raporu](DATA_PROVENANCE.md). `dataset_gercek` dizininin adı içindeki bütün dosyaların ham saha kaydı olduğu anlamına gelmez.
### GNSS Siber Güvenlik Araştırma Projesi — Yardımcı Betikler

Bu doküman, projede kullanılan veri hazırlama, sentetik veri üretimi, dönüştürme ve kıyaslama (benchmark) araçlarının işlevlerini ve kullanım amaçlarını açıklamaktadır.

---

## 📌 Araçlar ve Kullanım Amaçları

| Dosya Adı | Kategori | Açıklama | Çıktı / Hedef |
| :--- | :--- | :--- | :--- |
| **`benchmark_tests.py`** | Sentetik yazılım testi | Kural tabanlı, RF, VAE ve Hibrit modellerin sentetik senaryolardaki TPR, FPR, F1 ve gecikme çıktısını karşılaştırır. Sentetik sonuçlar saha başarısı veya bağımsız gerçek-veri validasyonu değildir. | Regresyon/PoC karşılaştırması; makalede genelleme sonucu olarak sunulmamalı |
| **`generate_dataset.py`** | Sentetik veri | Matematiksel hareket, jamming ve spoofing örnekleri üretir; saha ölçümü yapmaz. | `ornek_dron_saldiri_logu.csv` |
| **`download_av_gps.py`** | Sentetik örnek | Ağdan indirmez. Kökte dosya yoksa 500 satırlık mock veri üretir; araştırmacının gerçek CSV'si değildir. | Kökte `AV-GPS-Dataset-1.csv` |
| **`download_texbat.py`** | Manuel arşiv açma | Resmî bağlantıyı gösterir; kullanıcının yerleştirdiği ZIP'i açar. Otomatik veri indirmez. | `dataset_gercek/TEXBAT/` |
| **`iha_veri_donusturucu.py`** | Yapay dönüşüm | Hız/irtifayı değiştirir, etikete göre yapay C/N0 ekler; gerçek İHA saha kaydı oluşturmaz. | Çağıranın seçtiği CSV |
| **`kombine_saldiri_olustur.py`** | Yapay saldırı enjeksiyonu | Satır indekslerine göre jamming etiketi/SNR ekler; hız/irtifayı değiştirir. Süre satır sayısıyla aynı değildir. | `Kombine-Gercek-IHA-Saldirisi.csv` |
| **`texbat_loader.py`** | Sentetik örnek / eski araç | Gerçek dosya verilmezse mock CSV üretir. Bu sonuç resmî TEXBAT doğrulaması değildir. | `texbat_scenario1_mock.csv` |
| **`test_gps.py`** | Manuel UDP alımı | Doğrudan çalıştırıldığında UDP paketlerini dinler; pytest sırasında dinleme başlatmaz. | Konsol çıktısı |
| **`incele.py`** | Veri İnceleme | CSV veya log dosyalarının sütun dağılımını, eksik değerlerini (NaN) ve anomali sıklığını hızlıca analiz eder. | Veri seti özet istatistikleri |
| **`verify_hashes.py`** | Adli Bilişim | `forensic_ledger.jsonl` adli sicilindeki tüm HMAC-SHA256 hash zincirini matematiksel olarak baştan sona denetler. | Kriptografik doğrulama raporu |

---

## 🚀 Örnek Kullanım Senaryoları

### 1. Sentetik senaryo benchmark'ını yeniden çalıştırmak:
```bash
python benchmark_tests.py
```

### 2. İndirilen Bir Veri Setini Hızlıca İncelemek:
```bash
python incele.py "dataset_gercek/AV-GPS-Dataset-1.csv"
```

### 3. Çok Aşamalı Elektronik Harp Senaryosu Üretmek:
```bash
python kombine_saldiri_olustur.py
```
