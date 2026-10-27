# Düzeltme özeti — 23 Ekim 2026

Sonraki sıralı düzeltmeler ve **71 testlik** güncel kontrol için [takip raporuna](FOLLOWUP_REPORT.md) bakın. Aşağıdaki 58 testlik ölçümler önceki sürüme aittir.

Bilinen yazılım hataları için tespit, navigasyon, veri alımı, eğitim ve adli kayıt akışları düzeltildi. Bu çalışma tüm olası hataların giderildiği veya saha güvenliğinin sağlandığı anlamına gelmez.

## Yapılan düzeltmeler

- Bağımsız IMU/yönelim varsa örtülü konum sürüklemesi için zaman pencereli kontrol.
- Kaliteye göre GNSS ağırlıklandırma, yenilik kapısı ve spoofing sonrası kontrollü yeniden kabul. Uygun ilk bağımsız pencere referansıyla konum/hız kirlenmesini giderme.
- C/N0'suz AV kayıtları için ayrı kinematik RF: dosya 1 eğitim, dosya 2/3 değerlendirme; eğitim kimliği çakışması denetimi.
- Parçalı NMEA, sağlama toplamı, geçersiz fix, hız korunması, GSV tazeliği, bağlantı yeniden denemesi ve kaynakların karışması düzeltmeleri.
- IMU birimi, açık eksen/yönelim dönüşümü ve yerçekimi giderme; kaynak/saat değişiminde durum sıfırlama ve gerçek örnek aralığı.
- CSV alan/etiket kontrolleri, aynı adlı dosyanın yeniden yüklenmesi ve isteğe bağlı IMU/referans sözleşmesi. Referans olmadan gerçek konum/RMSE gösterilmez.
- Koşu gruplarıyla RF holdout/CV, CV içinde ölçekleme, saldırı/kayıt sınırlarını köprülemeyen VAE pencereleri.
- Atomik model yazımı ve dosya sürümüne bağlı önbellek yenileme.
- Kilitli adli kayıt yazımı ve doğrulanan segment rotasyonu. Başarısız yazmada oturum başı ilerlemez; bozuk zincire eklenmez.
- Kök pytest'in UDP dinlemesine takılması ve Python 3.10 bağımlılık uyumsuzluğu giderildi. Belgelerdeki doğrulanmamış saha, sertifika ve iniş iddiaları düzeltildi.

## Doğrulama

- `python -m pytest -q`: **58 test geçti**.
- CI'nin kritik flake8 seçimi: **0 hata**; `git diff --check`: temiz.
- Streamlit AppTest: simülasyon, sıcak model çıkarımı ve eğitim dışı CSV/kinematik RF oynatımı geçti.
- 25 koşu, 30.000 örnek, 250 dakikalık hızlandırılmış simülasyon; yeni 30001–30005 değerlendirme tohumları.
- Güncel kaynak ve model SHA-256 değerleri ham raporla karşılaştırıldı.
- Docker bulunmadığından imaj derlemesi; seri GPS portu bulunmadığından saha testi çalıştırılmadı.

## Sonuçlar ve kalan sınırlar

Örtülü spoofing tespiti bağımsız IMU/yönelim varsayımı altında **%96,38**; ortalama ilk tespit **10,10 saniye**. Jamming RMSE'si ham GPS'te **6,73 m**, navigasyonda **2,21 m**. Eğitim dışı AV-GPS dosya 2/3 kinematik RF tespit oranları **%99,59** ve **%93,55**.

Yanlış alarmlar sıfır değildir: salt normal koşuda **%1,17**; örtülü spoofing koşusunun saldırı dışı/toparlanma örneklerinde **%15,71**. Uzun kesintide belirsizlik ve kaçırılan saldırı örnekleri sürer. Sonuçlar bütün saldırılara veya gerçek sahaya garanti vermez. Gerçek araç kontrol komutu uygulanmamıştır.

Ayrıntılar: [doğrulama raporu](validation_results/VALIDATION_REPORT.md), [ham JSON](validation_results/validation_results.json), [saha sözleşmesi](FIELD_VALIDATION.md).
