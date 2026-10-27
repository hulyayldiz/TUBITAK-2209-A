# Kısa istatistiksel alarmlardan toparlanma — 23 Ekim 2026

Sonraki çalışma: [RF/VAE yanlış alarm düzeltmeleri ve 91 testlik kontrol](LOW_FALSE_ALARM_REPORT.md). Aşağıdaki üç örneklik VAE ayarı önceki sürümdür.

## Sorun ve değişiklik

Normal GNSS üzerinde kısa VAE alarmları görülebiliyor. Alarm sona erdikten sonra beş saniyelik yeniden kabul beklemesi, bu kısa olayın çok sayıda navigasyon alarmına dönüşmesine yol açabiliyordu.

Yalnız VAE kaynaklı istatistiksel bir olaydan sonra, tüm koşullar sağlandığında GNSS erken yeniden değerlendirilebilir:

- Karar yeniden normal olmalı.
- Bağımsız IMU/yönelim kontrolü mevcut ve ısınmasını tamamlamış olmalı.
- Kontrol saldırı tespit etmemeli; artık hata en fazla 2 metre olmalı ve normalize hata mevcut tutarlılık eşiğini geçmemeli.
- Bu koşullar kesintisiz en az üç örnekte ve en az 1,5 saniyelik örnek süresinde sağlanmalı.
- GNSS yine EKF yenilik kapısından geçmeli; erken değerlendirme ölçümün otomatik kabulü değildir.

Fiziksel, bağımsız IMU veya RF kaynaklı olayda erken yol açılmaz. Böyle bir olaya sonradan istatistiksel alarm eklenmesi de yolu açmaz. Kanıt eksik veya tutarsız olduğunda mevcut beş saniyelik bekleme korunur. Model ve saldırı tespit eşikleri değiştirilmedi; saldırı etiketleri karar mantığına verilmedi.

## Kontrollü geliştirme karşılaştırması

- 101/202/303 tohumlarında normal ve örtülü spoofing öncesi/sonrası karşılaştırması: normal 3.600 örnekte iki sürüm de 0 yanlış alarm. Örtülü spoofing TP **2261**, FN **79**, saldırı dışı FP **120**; her iki sürümde aynı. Koşu başına konum RMSE değerleri de değişmedi.
- Ek normal geliştirme koşuları 1001–1005: aynı 6.000 örnekte FP **25 → 18** (%0,417 → %0,300). 1003'te 11 alarm değişmedi; bağımsız kontrol erken toparlanma için kesintisiz yeterli kanıt sağlamadı. 1005'te 14 → 7 oldu. Bu, alarm uzamasının koşullu azaltılmasıdır; modelin kendisindeki hataların giderildiği iddiası değildir.
- Önceki davranış, geliştirme karşılaştırmasında istatistiksel olayın erken toparlanma uygunluğu kapatılarak çalıştırıldı. Kodun diğer kararları ve rastgele tohumlar aynı tutuldu.
- Ham kayıtlar: `validation_results/quarantine_calibration_before.json`, `quarantine_calibration_after.json`, `quarantine_normal_development.json`.

## Kontroller ve ayrı değerlendirme

- **79 test geçti.** Eksik/ısınan IMU, yüksek veya geçersiz artık, konum yeniliği reddi ve fiziksel alarm durumları kapsandı.
- Kritik flake8 seçimi **0 hata**; `git diff --check` temiz.
- Yeni 60001–60003 değerlendirme tohumları; modeller ve eşikler yeniden ayarlanmadı. [Son rapor](validation_results/statistical_recovery_20261023/VALIDATION_REPORT.md) ve [ham JSON](validation_results/statistical_recovery_20261023/validation_results.json).
- 15 koşu / **18.000 örnek** tamamlandı; kaynak/model SHA-256 değerleri raporla eşleşiyor. Bu yeni tohumlarda salt normal yanlış alarm **%1,03** (37/3600); örtülü spoofing tespiti **%97,05**, bu senaryonun saldırı dışı yanlış alarmı **%6,90**. Önceki 50001–50003 tohumlarının %0,67 değeriyle doğrudan karşılaştırılamaz.
- Aynı yeni 60001–60003 tohumlarında önceki yeniden kabul davranışı ayrıca çalıştırıldı: normal yanlış alarmlı örnek **44/3600 → 37/3600** (%1,22 → %1,03; örnek sayısında yaklaşık %16 azalma). Bu aynı girdilerle kontrollü karşılaştırmadır; sonuç görüldükten sonra ayar değiştirilmedi. Önceki davranışın ham sonuçları `validation_results/statistical_recovery_20261023/normal_paired_baseline.json` dosyasındadır. Bu sayılar ayrı alarm olaylarının sayısı değildir.
- Örtülü spoofing navigasyon RMSE'si **30,88 m**; konum sapması sürüyor. Jamming RMSE'si ham/filtre tablosunda, tespit oranı **%100** olarak raporlandı. Bu ölçümler saha sonucu değildir.

Bu değişiklik bağımsız sensör bulunmadığında beklemeyi kısaltmaz. Gerçek GPS/IMU saha doğrulaması ve uzun kesintide biriken konum hatası açık kalır.
