# Saha doğrulaması ve kayıt sözleşmesi

**Sonraki navigasyon düzeltmesi:** CMU'daki tarihsel alarm sorunu, aynı 209
kaydın yeniden oynatımında 0/257.896 oldu; tüm ölçümler filtre tarafından
kullanıldı. [Güncel rapor](NAVIGATION_FIX.md). Bu kayıtlar artık geliştirme
verisidir; kendi donanımımızda ve yeni bağımsız kayıtta doğrulama ihtiyacı sürer.

**Bağımsız yayımlanmış uçuş testi artık mevcut, sonuç başarısız:**
[CMU değerlendirmesi](INDEPENDENT_REAL_VALIDATION.md) 209 kaydı ve farklı GNSS/INS
alıcısını kapsar; nominal örneklerin %48,98'inde alarm vardır. RF/VAE bu şemada
çalışmaz; kendi donanımımızda saha testi ve bağımsız saldırı testi hâlâ eksiktir.
[TEXBAT saldırı zamanları/kaçırma ölçümü](TEXBAT_TIMING_VALIDATION.md) ayrıca raporlanır.

23 Ekim 2026'da erişilebilir seri GPS portu bulunmadı. Gerçek GPS/IMU saha testi yapılmadı. Güncel rapor hızlandırılmış simülasyon ve mevcut AV-GPS kayıtlarını kapsar; gerçek araca kontrol komutu gönderilmez.

## NMEA alımı

Seri, TCP ve UDP mesajları parça sınırlarından bağımsız birleştirilir. Sağlama toplamı ve fix geçerliliği denetlenir. RMC/VTG'den ölçülmüş hız gerekir; GGA hızı sıfırlamaz. GSV varsa alıcının bildirdiği sinyal değerleri kullanılır ve 3 saniyeden eski ölçüm kullanılmaz. C/N0 veya yeni fix yoksa ölçüm üretilmez. C/N0'suz yapılandırılmış AV kayıtlarında ayrı kinematik model kullanılabilir.

## CSV

En az `lat`, `lon`, `speed_kmh` (veya `speed_m_s`) gerekir. `timestamp_s` sayısal kayıt zamanı, `timestamp` ISO tarih-saat veya `Run Time` süre biçimi kullanılabilir. Zaman yoksa 0.5 saniye varsayımı arayüzde belirtilir. Saatin geriye dönmesi yeni kayıt bölümü sayılır. `label`: 0/normal, 1/spoofing veya 2/jamming; bilinmeyen etiket reddedilir. Etiket yoksa Pd/Pfa/F1/TTD hesaplanmaz.

İsteğe bağlı `cn0`, `reference_lat`, `reference_lon` sütunları gerçek ölçüm/reference içermelidir. Referans konum, tespit özelliklerine veya GNSS güven kararına verilmez; yalnız hata hesabı ve harita içindir. Sütunun adı tek başına referansın doğruluğunu kanıtlamaz: kayıt kaynağı ayrıca belgelenmelidir.

## IMU ve yönelim

`imu_ax_m_s2`, `imu_ay_m_s2`, isteğe bağlı `imu_az_m_s2` m/s² birimindedir. `imu_frame=navigation` açıkça kuzey/doğu/yukarı eksenindeki, yerçekimi çıkarılmış ivmeyi belirtir. Bağımsız yönelim kontrolü için `imu_heading_deg` ve `heading_independent=true` gerekir; bu işaret yalnız gerçek bağımsız AHRS/yönelim kaynağı varsa kullanılmalıdır.

Gövde eksenindeki özgül kuvvet için `imu_frame=body`, `roll_deg`, `pitch_deg`, `yaw_deg`, `attitude_convention=FRU_to_NEU` ve bağımsız yönelim bilgisi verilebilir. Yazılım ileri/sağ/yukarı gövde eksenlerinden kuzey/doğu/yukarıya döndürür ve 9.80665 m/s² yerçekimini çıkarır. Eksen, birim, bias kalibrasyonu ve yönelim kaynağı bilinmiyorsa bu dönüşüm geçerli sayılmaz. MPU6050 tek başına mutlak yaw sağlamaz; sanal sensör gerçek ölçüm sayılmaz.

## Henüz doğrulanmayanlar

Gerçek cihaz zaman eşlemesi, sıcaklık/bias kalibrasyonu, bağımsız referans doğruluğu ve uzun süreli alan performansı fiziksel cihazlarla sınanmalıdır. Eğitim ve değerlendirme ayrı oturumlarda yapılmalı, özgün dosyalar SHA-256 ile korunmalıdır. Simülatördeki bağımsız yönelim 0.2° standart sapmalı varsayımdır. Bu varsayımın sahada sağlandığı gösterilmeden örtülü spoofing sonuçları sahaya taşınamaz.
