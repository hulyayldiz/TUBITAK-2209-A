# Güncel doğrulama raporu

Tarih: 2026-10-22T15:59:34.043627+03:00

Bu rapor yazılım simülasyonu ve yerel AV-GPS kayıtlarının yeniden oynatılmasıdır. GPS/IMU saha testi değildir.

Eğitim, normal eşik kalibrasyonu ve değerlendirme rastgele tohumları ayrıdır. Değerlendirme verisiyle yeniden ayarlama yapılmaz.

Her saldırı koşusunda 60 saniye normal başlangıç ve son çeyrekte normal toparlanma vardır. Yanlış alarmlar toparlanma dönemini de kapsar.

| Senaryo | Katman | Tespit (%) | Yanlış alarm (%) | Kaçırılan / toplam olay | Ortalama TTD (s) |
|---|---|---:|---:|---:|---:|
| normal | rule | — | 0.00 | 0/0 | — |
| normal | rf | — | 0.02 | 0/0 | — |
| normal | vae | — | 0.00 | 0/0 | — |
| normal | hybrid | — | 0.02 | 0/0 | — |
| jamming | rule | 100.00 | 71.43 | 0/5 | 0.00 |
| jamming | rf | 100.00 | 0.00 | 0/5 | 0.00 |
| jamming | vae | 99.74 | 2.57 | 0/5 | 1.00 |
| jamming | hybrid | 100.00 | 71.43 | 0/5 | 0.00 |
| spoofing | rule | 93.03 | 57.48 | 0/5 | 27.20 |
| spoofing | rf | 98.85 | 0.05 | 0/5 | 0.00 |
| spoofing | vae | 99.74 | 2.62 | 0/5 | 1.00 |
| spoofing | hybrid | 100.00 | 57.67 | 0/5 | 0.00 |
| slow_spoofing | rule | 8.18 | 57.48 | 1/5 | 350.12 |
| slow_spoofing | rf | 64.97 | 0.10 | 0/5 | 0.70 |
| slow_spoofing | vae | 99.38 | 2.62 | 0/5 | 1.80 |
| slow_spoofing | hybrid | 99.69 | 57.71 | 0/5 | 0.70 |

TTD, saldırının başlangıcından ilk alarma kadar geçen simülasyon süresidir. Kaçırılan olaylar sıfır saniye sayılmaz.

| Senaryo | Ham GPS RMSE (m) | Navigasyon RMSE (m) | EKF RMSE (m) | Çıkarım p95 (ms), koşular ortalaması |
|---|---:|---:|---:|---:|
| normal | 0.24 | 0.24 | 0.24 | 6.82 |
| jamming | 6.73 | 8343.47 | 122.13 | 4.72 |
| spoofing | 62055.20 | 7759.67 | 102.30 | 6.50 |
| slow_spoofing | 90.73 | 7519.57 | 132.62 | 6.40 |

## Harici veri

AV-GPS dosyaları model eğitiminde kullanılmamıştır. C/N0 ve bağımsız doğru konum bulunmadığından hibrit model başarısı ve konum RMSE'si bu dosyalardan çıkarılamaz. Aşağıdaki değerler yalnız kinematik kuralları ölçer.

| Dosya | Örnek | Tespit (%) | Yanlış alarm (%) |
|---|---:|---:|---:|
| AV-GPS-Dataset-1.csv | 206 | — | 0.00 |
| AV-GPS-Dataset-2.csv | 692 | — | 0.00 |
| AV-GPS-Dataset-3.csv | 633 | 44.17 | 0.00 |

## Sınırlar ve saha doğrulaması

- Simülatörün konumu yalnız hata ölçümüne verilir; tespit özelliklerine ve GPS güven kararına verilmez.
- Yavaş ve fiziksel olarak tutarlı spoofing, bağımsız konum/hız/yön referansı olmadan güvenilir biçimde ayrılamayabilir. Kaçırılan olaylar raporda saklanmaz.
- INS süre sınırından sonra konumu dondurmak simülasyondaki bir davranıştır; gerçek aracı durduran veya indiren donanım komutu değildir.
- Alt metre RMSE, sıfırıncı gün koruması veya saha güvenliği garantisi verilmez.
- Gerçek GPS/IMU saha doğrulaması: tamamlanmadı. Bağımsız referans konum, zaman eşlemeli IMU ve etiketli pasif kayıt gerekir.
- Sentetik eğitimden saha verisine genelleme bu raporla doğrulanmış sayılmaz.

Ayrıntılı sayımlar, her olayın TTD'si, model ve veri SHA-256 değerleri: `validation_results.json`.
