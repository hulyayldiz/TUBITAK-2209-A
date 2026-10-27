# Sıralı düzeltme çalışması — 23 Ekim 2026

Sonraki çalışma: [kısa yanlış alarmların uzamasını azaltma ve 79 testlik kontrol](FALSE_ALARM_REPORT.md). Aşağıdaki 71 testlik çalışma önceki sürümdür.

## Tamamlanan yazılım düzeltmeleri

1. **Normal navigasyon çıktısı:** Güvenlik duvarı açıkken hesaplanan filtre konumu artık gerçekten döndürülüyor. Kapalı karşılaştırma modu ham GPS döndürmeye devam ediyor.
2. **Alarmın gereksiz uzaması:** Fiziksel alarmın önceki kararı koruyan histerezisi artık yeni saldırı kanıtı sayılmıyor. Yeniden kabul süresi yalnız yeni fiziksel/IMU veya ML kanıtıyla yenileniyor. Şüpheli ölçüm yine filtreye verilmez; süre bitince yenilik kapısı uygulanır. Tespit eşikleri değiştirilmedi.
3. **Model önbelleği:** Aynı dosyaları okuyan RF ve ölçekleyici yükleyicilerinin sonuçları birbirine karışabiliyordu. Önbellek anahtarı artık yükleyici kimliğini de içeriyor.
4. **MPU6050 işaretli sayı sınırı:** `0x8000` artık doğru biçimde `-32768` olarak çözümleniyor.
5. **Geciken simülasyon örneği:** Toparlanma ofseti uzun örnek aralığında ters işaret almıyor. Geçersiz örnek aralığı durum değiştirilmeden reddediliyor. Bağımsız IMU kaybolduğunda pencerenin integralleri temizleniyor.
6. **Docker bağlamı:** `.env`, yerel HMAC anahtarı ve adli kayıtlar imajdan dışlanıyor. Streamlit sağlık kontrolü eklendi.
7. **Değerlendirme:** Temiz başlangıç ve saldırı sonrası toparlanma alarmları ayrı sayılıyor; toplam yanlış alarm hesabı ikisini de içeriyor. Ham rapor yanlış alarmların kural/IMU, ML veya navigasyon kaynağını içeriyor. `--seed-start` ile yeni değerlendirme tohumları seçilebiliyor.

## Kontroller

- `python -m pytest -q`: **71 test geçti**.
- Kritik flake8 seçimi: **0 hata**. `git diff --check`: temiz.
- Son önbellek ve alarm düzeltmelerinden sonra Streamlit AppTest açılışı geçti.
- Son sürümün yeni tohumlarla sonuçları: [takip doğrulaması](validation_results/followup_20261023/VALIDATION_REPORT.md), [ham JSON](validation_results/followup_20261023/validation_results.json).
- Model ve eşikler yeniden eğitilmedi/ayarlanmadı. 40001–40005 tohumlu ara çalışma `navigation_fix_20261023/` altında korunur; son histerezis ve önbellek düzeltmesini içermez. Son çalışma 50001–50003 tohumlarını kullanır.

## Son ölçümler

50001–50003 tohumlarıyla beş senaryoda 15 koşu, **18.000 örnek / 150 dakika hızlandırılmış simülasyon** tamamlandı. Kaynak ve model SHA-256 değerleri sonuç JSON'uyla eşleşiyor.

- Salt normal senaryo: hibrit yanlış alarm **%0,67**; ham GPS RMSE **0,25 m**, navigasyon **0,19 m**.
- Jamming: tespit **%100**, saldırı dışı yanlış alarm **%1,75**; ham GPS RMSE **6,86 m**, navigasyon **2,32 m**.
- Örtülü spoofing: tespit **%96,75**, üç olayın üçü de tespit edildi; ortalama ilk tespit **12,67 s**. Saldırı dışı başlangıç/toparlanma yanlış alarmı **%5,71**. Navigasyon RMSE **26,62 m**; sapma sorunu ortadan kalkmış değildir.
- Farklı tohum ve koşu sayısı nedeniyle önceki rapora göre değişim doğrudan, kontrollü bir iyileşme yüzdesi sayılmaz.

## Açık kalan doğrulama ve performans sınırları

- Yanlış alarm ve kaçırılan saldırı oranları sıfırlanmış değildir. Daha düşük oran için yeni ve temsil edici kalibrasyon kayıtları gerekir; değerlendirme kayıtlarıyla eşik ayarlamak bağımsız test sayılmaz.
- Bağımsız IMU/yönelim olmadan örtülü spoofing kontrolü kullanılamaz. Uzun GNSS kesintisinde yalnız ivmeyle konum hatasını sınırsız süre sıfırlamak mümkün değildir; bağımsız konum/hız referansı gerekir.
- 23 Ekim kontrolünde seri port listesi boştu; gerçek GPS/IMU, zaman eşlemesi, sıcaklık/bias ve saha doğrulaması yapılmadı. [Saha kayıt sözleşmesi](FIELD_VALIDATION.md) uygulanmalı.
- Bu bilgisayarda Docker yok; imaj derleme/çalıştırma doğrulanmadı. CI Docker derleme adımını içerir; uzaktaki CI sonucu bu çalışmada çalıştırılmadı.
- Araç kontrolü/otomatik iniş uygulanmadı; hedef araç ve kontrol arayüzü belirlenmeden buna ilişkin güvenlik başarısı iddia edilemez.

Bu dosya tamamlanan kod düzeltmelerini ve açık sınırları ayırır; tüm olası hataların veya saha risklerinin ortadan kalktığı iddiası değildir.
