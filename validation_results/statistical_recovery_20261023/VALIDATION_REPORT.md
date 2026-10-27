# Güncel doğrulama raporu

Tarih: 2026-10-23

Bu rapor yazılım simülasyonu ve yerel AV-GPS kayıtlarının yeniden oynatılmasıdır. GPS/IMU saha testi değildir.

Eğitim, normal eşik kalibrasyonu ve değerlendirme rastgele tohumları ayrıdır. Değerlendirme verisiyle yeniden ayarlama yapılmaz.

Yavaş spoofing 0.5 m/s konum sürüklemesidir. `slow_spoofing` C/N0 değişimi içerir; eğitimde bulunmayan `stealth_spoofing` normal C/N0 dağılımını korur.

`rule` katmanı fiziksel kuralları ve varsa bağımsız IMU/yönelim kontrolünü içerir; `inertial` yalnız tutarlılık kontrolüdür. Değerlendirme tohumları: [60001, 60002, 60003]. Eğitim ve kalibrasyon geçmişi ham JSON'dadır.

Her saldırı koşusunda 60 saniye normal başlangıç ve son çeyrekte normal toparlanma vardır. Yanlış alarmlar toparlanma dönemini de kapsar.

| Senaryo | Katman | Tespit (%) | Yanlış alarm (%) | Kaçırılan / toplam olay | Ortalama TTD (s) |
|---|---|---:|---:|---:|---:|
| normal | rule | — | 0.00 | 0/0 | — |
| normal | rf | — | 0.03 | 0/0 | — |
| normal | vae | — | 0.44 | 0/0 | — |
| normal | hybrid | — | 1.03 | 0/0 | — |
| normal | inertial | — | 0.00 | 0/0 | — |
| jamming | rule | 100.00 | 0.00 | 0/3 | 0.00 |
| jamming | rf | 100.00 | 0.08 | 0/3 | 0.00 |
| jamming | vae | 98.59 | 1.27 | 0/3 | 5.50 |
| jamming | hybrid | 100.00 | 2.94 | 0/3 | 0.00 |
| jamming | inertial | 0.00 | 0.00 | 3/3 | — |
| spoofing | rule | 100.00 | 1.67 | 0/3 | 0.00 |
| spoofing | rf | 96.58 | 0.08 | 0/3 | 0.00 |
| spoofing | vae | 0.00 | 1.51 | 3/3 | — |
| spoofing | hybrid | 100.00 | 7.70 | 0/3 | 0.00 |
| spoofing | inertial | 0.00 | 0.00 | 3/3 | — |
| slow_spoofing | rule | 91.24 | 1.67 | 0/3 | 11.00 |
| slow_spoofing | rf | 65.98 | 0.00 | 0/3 | 0.33 |
| slow_spoofing | vae | 99.53 | 3.89 | 0/3 | 1.83 |
| slow_spoofing | hybrid | 99.91 | 6.90 | 0/3 | 0.33 |
| slow_spoofing | inertial | 85.04 | 0.00 | 0/3 | 11.00 |
| stealth_spoofing | rule | 97.05 | 1.67 | 0/3 | 11.50 |
| stealth_spoofing | rf | 0.04 | 0.00 | 2/3 | 386.00 |
| stealth_spoofing | vae | 0.00 | 3.41 | 3/3 | — |
| stealth_spoofing | hybrid | 97.05 | 6.90 | 0/3 | 11.50 |
| stealth_spoofing | inertial | 96.07 | 0.00 | 0/3 | 11.50 |

### Temiz başlangıç ve toparlanma

Toparlanma alarmları saldırı dışı yanlış alarm hesabına dahildir; temiz başlangıçla ayrı gösterilir. Saldırı etiketi yalnız değerlendirmede kullanılır.

| Senaryo | Temiz örnek / alarm | Toparlanma örnek / alarm |
|---|---:|---:|
| normal | 3600 / 37 | 0 / 0 |
| jamming | 360 / 27 | 900 / 10 |
| spoofing | 360 / 27 | 900 / 70 |
| slow_spoofing | 360 / 27 | 900 / 60 |
| stealth_spoofing | 360 / 27 | 900 / 60 |

TTD, saldırının başlangıcından ilk alarma kadar geçen simülasyon süresidir. Kaçırılan olaylar sıfır saniye sayılmaz.

| Senaryo | Ham GPS RMSE (m) | Navigasyon RMSE (m) | EKF RMSE (m) | Çıkarım p95 (ms), koşular ortalaması |
|---|---:|---:|---:|---:|
| normal | 0.25 | 0.19 | 0.19 | 7.32 |
| jamming | 6.71 | 2.15 | 2.15 | 7.26 |
| spoofing | 62069.58 | 50.51 | 50.51 | 7.51 |
| slow_spoofing | 90.73 | 65.80 | 65.80 | 7.56 |
| stealth_spoofing | 90.73 | 30.88 | 30.88 | 8.73 |

## Harici veri

C/N0 tabanlı RF/VAE modeli AV-GPS dosyalarında eğitilmemiştir. Ayrı C/N0 gerektirmeyen AV modeli yalnız dosya 1'de eğitilir; dosya 2 ve 3 ayrılmış değerlendirmedir. Dosya 1 için AV model test skoru verilmez. Eğitimdeki konum/zaman/hız kimliğiyle çakışan test satırları çıkarılır. Dosya 2 ve 3 birbirleriyle kısmen örtüşür; bağımsız tekrarlar gibi birleştirilmez. Bağımsız doğru konum bulunmadığından konum RMSE'si çıkarılamaz. İlk tablo yalnız fiziksel kuralları ölçer.

| Dosya | Örnek | Tespit (%) | Yanlış alarm (%) |
|---|---:|---:|---:|
| AV-GPS-Dataset-1.csv | 61569 | 5.93 | 0.21 |
| AV-GPS-Dataset-2.csv | 6781 | 12.57 | 0.26 |
| AV-GPS-Dataset-3.csv | 633 | 47.39 | 5.22 |

### Ayrı kinematik RF: eğitim dışı kayıtlar

| Dosya | Tespit (%) | Yanlış alarm (%) | Eğitimle çakışan çıkarılan satır |
|---|---:|---:|---:|
| AV-GPS-Dataset-2.csv | 99.59 | 0.12 | 0 |
| AV-GPS-Dataset-3.csv | 93.55 | 0.00 | 0 |

## Sınırlar ve saha doğrulaması

- Simülatörün konumu yalnız hata ölçümüne verilir; tespit özelliklerine ve GPS güven kararına verilmez.
- Yavaş ve fiziksel olarak tutarlı spoofing, bağımsız konum/hız/yön referansı olmadan güvenilir biçimde ayrılamayabilir. Kaçırılan olaylar raporda saklanmaz.
- Düşük C/N0 koordinat manipülasyonu kanıtı değildir. Jamming'de fiziksel yenilik kapısını geçen ölçümler düşük ağırlıkla birleştirilir; spoofing/tutarsız ölçümde ataletsel tahmin kullanılır. Konum belirsizliği izlenir; gerçek araç kontrol komutu yoktur.
- Jamming simülasyonunda ham GPS hatası ataletsel tahminden düşük olabilir; müdahale her koşulda konum iyileşmesi sağlamaz.
- Bağımsız yönelim ve navigasyon eksenindeki IMU mevcutsa yeni zaman penceresi kontrolü kullanılır. Simülatör bu bağımsız yönelimi 0.2° standart sapmalı varsayar; çıplak MPU6050 mutlak yönelim sağlamaz. Bu girdiler yoksa kontrol devre dışıdır.
- Alt metre RMSE, sıfırıncı gün koruması veya saha güvenliği garantisi verilmez.
- Gerçek GPS/IMU saha doğrulaması: tamamlanmadı. Bağımsız referans konum, zaman eşlemeli IMU ve etiketli pasif kayıt gerekir.
- Sentetik eğitimden saha verisine genelleme bu raporla doğrulanmış sayılmaz.

Ayrıntılı sayımlar, her olayın TTD'si, model ve veri SHA-256 değerleri: `validation_results.json`.
