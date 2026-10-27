# Proje terimleri ve veri kılavuzu

Bu belge GNSS terimlerini ve projedeki veri türlerini, doğrulanmış uygulama kapsamıyla açıklar. Saldırıya dair bir alarm saldırı kaynağını tek başına ispatlamaz.

## Temel terimler

- **GNSS:** GPS, Galileo, GLONASS ve BeiDou gibi uydu seyrüsefer sistemlerinin ortak adıdır. Projedeki destek, her sistem/alıcı için doğrulanmış olduğu anlamına gelmez; kullanılan giriş şemasına bağlıdır.
- **Spoofing:** GNSS alıcısının sahte uydu benzeri sinyalleri gerçek sanarak hatalı zaman veya konum çözümü üretmesine yol açan saldırı ailesidir. Her spoofing saldırısı alıcı çözümünde ani koordinat sıçraması oluşturmaz.
- **Jamming:** Alım kalitesini veya uydu sinyallerinin kullanılabilirliğini bozmayı hedefleyen girişimdir. Fix kaybı ya da düşük C/N0 tek başına jamming kaynağını kanıtlamaz; doğal kapsama ve alıcı arızaları da benzer belirti üretebilir.
- **C/N0:** Taşıyıcı gücünün gürültü güç yoğunluğuna oranıdır ve çoğunlukla dB-Hz ile verilir. Beklenen değer anten, alıcı, uydu ve ortamla değişir; tek bir evrensel eşik yoktur.
- **CMC (Code Minus Carrier):** Pseudorange ile taşıyıcı fazı uzunluğunun farkıdır. Ortak geometrik ve saat bileşenlerini azaltır; kalan ölçüm multipath, iyonosfer, belirsizlik ve gürültü gibi bileşenler de içerir. Bu projede yardımcı tutarsızlık göstergesi olarak kullanılır, spoofing doğrulaması değildir.
- **IMU/INS:** IMU ivme ve açısal hız ölçer; INS bu ölçümleri entegre ederek hareket kestirir ve hatası zamanla büyüyebilir. Projede bağımsız yönelim/IMU yoksa inertial tutarlılık testi çalışmaz. Arayüz kestirimi uçuşa elverişli yedek navigasyon kanıtı değildir.
- **RF ve VAE skorları:** Random Forest sınıflandırıcı skoru ile LSTM-VAE anomali skoru kalibre edilmiş saldırı olasılığı sayılmaz. Anomali skoru görülmemiş saldırıların tespit edildiğini tek başına göstermez.
- **Gecikme ve kapsam:** Gecikme ilk yeni alarmın tanımlı olay başlangıcından sonraki süresidir. Örnek kapsamı alarm açık olan etiketli epoch'ların payıdır; olay düzeyinde tespit olasılığı, yanlış alarm oranı ve bağımsız genelleme ile aynı metrik değildir.

## Veri kökeni

Projede gerçek yayımlanmış deney kayıtları, bunlardan değiştirilmiş türevler ve sentetik örnekler bulunur. Kaynağı doğrulanan AV-GPS kayıtları kara aracı deneyleridir, fiziksel İHA uçuşu değildir. Yerel `IHA-Saha-Verisi.csv` ve kombine CSV'ler hız/irtifa, etiket veya yapay sinyal alanları eklenerek değiştirilmiştir. `ornek_dron_saldiri_logu.csv` ile `texbat_scenario1_mock.csv` sentetiktir. TEXBAT değerlendirmesinde yayımlanmış işlenmiş GRID NAV/kanal ölçümleri kullanılır; ham RF IQ yeniden alıcıdan geçirilmemiştir. Dosya bazında ayrıntı [DATA_PROVENANCE.md](DATA_PROVENANCE.md) ve [REAL_DATA_INTEGRATION.md](REAL_DATA_INTEGRATION.md) içindedir.

## Bilimsel raporlama

Sentetik veri yazılımın senaryo davranışını sınamak için kullanılabilir; fiziksel saldırı veya saha geçerliliğini kanıtlamaz. Eşikler ve hiperparametreler geliştirme verisinde seçilmeli, bağımsız test öncesinde dondurulmalıdır. Test ve eğitim kayıt/oturum bazında ayrılmalı; olay düzeyinde tespit, kaçırma, gecikme ve temiz kayıttaki yanlış alarm ayrı raporlanmalıdır. Mevcut TEXBAT ölçümleri ile sınırlamalar [TEXBAT_CURRENT_VALIDATION.md](TEXBAT_CURRENT_VALIDATION.md) içinde açıklanır.
