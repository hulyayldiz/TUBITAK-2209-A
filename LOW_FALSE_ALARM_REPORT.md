# Düşük yanlış alarm kalibrasyonu — 23 Ekim 2026

Sonraki sürüm: [saldırı sonrası toparlanma düzeltmeleri ve 96 testlik kontrol](RECOVERY_REPORT.md). Aşağıdaki 80001–80005 sonuçları önceki navigasyon politikasına aittir.

## Yapılan değişiklik

VAE'nin önceki eşiği 2.133 normal pencereyle belirlenmiş ve üç ardışık eşik aşımında alarm verilmişti. Ek geliştirme koşularında normal ölçümler 3–9 örneklik şüpheli diziler üretebiliyordu. Bu diziler navigasyonun yeniden kabul süresiyle uzayabiliyordu.

Yeni `vae_calibration.py`, saldırı etiketlerini ve değerlendirme sonuçlarını kullanmadan yalnız ayrı normal koşular üzerinde kalibrasyon yapar:

- 2001–2020 tohumlarında 20 koşu / 24.000 örnek, **23.820 pencere**.
- Normal pencere hatalarının **%99,99 yüzdeliği**: eşik **0,00314789 → 0,00388083**.
- Koşuların sınırları birleştirilmeden, yeni eşiği geçen en uzun normal dizi üç pencere. Bu yüzden doğrulama **4 ardışık örnek ve en az 2 saniye**.
- Gerekli doğrulama beş saniyeyi geçerse kalibrasyon başarısız olur; bekleme sınırsız artırılmaz.
- Eşik ve doğrulama bilgileri model paketine birlikte, atomik olarak yazılır. Önceki model/eşik bu çalışmanın çıktı dizininde SHA-256 adlı yedeklerle korundu.

Bu bekleme yalnız VAE'nin kendi kararını etkiler. Fiziksel ve bağımsız IMU tespitleri önceki gibi çalışır; RF için ayrı doğrulama aşağıda açıklanır. VAE'nin tek başına yakaladığı bir örüntü, önceye göre en az bir örnek (0,5 saniye) daha geç onaylanabilir; eşik artışı bazı anormalliklerin kaçırılma riskini de artırabilir. Bu nedenle ayrı saldırı değerlendirmesi ve önceki ayarla aynı girdilerde karşılaştırma yapıldı.

## Tek örneklik RF kararları

VAE kalibrasyonundan sonraki ara değerlendirmede kalan normal alarmlar iki tek örneklik RF kararından kaynaklandı. Ayrı 2001–2020 normal kalibrasyonunda da sekiz tek örneklik RF kararı görüldü; skorları 0,50–0,575 aralığındaydı.

Son sürümde yalnız GNSS RF katmanının zayıf kararı iki ardışık ölçümde doğrulanır. Saldırı skoru en az 0,90 olan RF kararı, fiziksel kural/IMU kararı ve ayrı AV kinematik modeli bu beklemeye girmez. Skor, kalibre edilmiş saldırı olasılığı değildir. Zayıf RF kararında bir örneklik ek gecikme mümkün olduğundan son saldırı testinde ilk tespit süreleri de karşılaştırılır.

Temiz örnek, kaynak/saat değişimi veya açık konum/sinyal kopuşu sayacı sıfırlar. Model dosyası yeniden yüklendiğinde RF/VAE doğrulama sayaçları yeni model sürümüne taşınmaz.

Bağımsız 2601–2700 RF denetiminde **120.000 normal örnekte 30 ham RF yanlış kararı → 0 doğrulanmış RF alarmı**. Bu tüm sistem oranı değildir; ham kayıt `validation_results/low_false_alarm_final_20261023/normal_rf_audit.json` dosyasındadır.

## Bağımsız normal VAE denetimi

2601–2700 tohumlarında 100 ayrı normal koşu, 120.000 örnek / 1.000 dakika hızlandırılmış simülasyon. VAE **119.100 pencerede 25 alarm örneği** üretti: **%0,021**. Dört koşuda alarm vardı; bu oran ayrı alarm olaylarının sayısı veya tüm sistemin yanlış alarm oranı değildir. Kaynak: `validation_results/low_false_alarm_20261023/normal_vae_audit.json`.

## Yazılım kontrolleri

- **91 test geçti.** Kalibrasyon verisi doğrulama, koşu sınırları, aşırı beklemenin reddi, modeldeki doğrulama bilgisinin kullanımı, gerçek örnek aralığı ve kesintide sayaç sıfırlama kapsandı. Zayıf RF doğrulaması ve güçlü kanıtın hemen işlenmesi ayrıca sınandı.
- Fiziksel/RF alarmının VAE onayını beklemediği test edildi.
- Kritik flake8 seçimi **0 hata**; `git diff --check` temiz. Streamlit AppTest açılışı geçti.

## Tam sistem değerlendirmesi

Son birleşik RF/VAE sürümü **80001–80005** tohumlarıyla beş senaryo / 25 koşu / 30.000 örnek içerir. Eğitim ve kalibrasyonla ayrıdır. [Son rapor](validation_results/low_false_alarm_final_20261023/VALIDATION_REPORT.md), [ham JSON](validation_results/low_false_alarm_final_20261023/validation_results.json), [normal VAE kalibrasyonu](validation_results/low_false_alarm_20261023/normal_calibration.json). 70001–70005 tohumlu yalnız VAE ara çalışması `low_false_alarm_20261023/` altında korunur; son RF düzeltmesini içermez.

Normal, yavaş spoofing ve örtülü spoofing için aynı son tohumlarda önceki eşik/doğrulama politikası da çalıştırıldı. Model ağırlıkları ve navigasyon politikası değişmedi. Önceki RF davranışı tek örnekte doğrulama, önceki VAE davranışı eski eşik ve üç örnek/1,5 saniyeyle yeniden üretildi. Karşılaştırma son çalışma dizinindeki `paired_previous_policy.json` dosyasındadır; eski politikayı çalıştırmak son değerlendirmede yeni ayar yapmak için kullanılmadı.

### Son sonuçlar

Kaynak ve model SHA-256 değerleri ham raporla eşleşiyor. Kontrollü karşılaştırmanın özeti `policy_comparison.json` dosyasındadır.

| Aynı girdilerde senaryo | Önceki yanlış alarmlı örnek | Son yanlış alarmlı örnek | Son yanlış alarm oranı | Önceki → son tespit |
|---|---:|---:|---:|---:|
| Salt normal | 62/6000 | **0/6000** | **%0 gözlendi** | — |
| Yavaş spoofing, saldırı dışı örnekler | 129/2100 | 100/2100 | %4,76 | %99,95 → %99,95 |
| Örtülü spoofing, saldırı dışı örnekler | 342/2100 | 300/2100 | %14,29 | %95,64 → %95,64 |

Yavaş spoofing TP/FN **3898/2**, örtülü spoofing **3730/170**; önceki politikayla aynı. İlk tespit süreleri koşu bazında da değişmedi. Jamming ve ani spoofing son sürümde **%100** tespit edildi. Toplam 20 saldırı olayının 20'si en az bir kez tespit edildi; bu, bütün saldırı örneklerinin tespit edildiği anlamına gelmez.

Normal simülasyonda hedeflenen çok düşük oran bu 6.000 örnekte sağlandı; sonsuz süreli veya saha garantisi değildir. Özellikle örtülü spoofing sonrasındaki yeniden kabul/güven belirsizliği çözülmüş değildir: bu senaryonun saldırı dışı oranı hâlâ %14,29. Bu alarmlar sıfırmış gibi gösterilmedi. Örtülü spoofing navigasyon RMSE'si **60,32 m**; önceki politikayla aynı. Uzun süreli konum sapması bu çalışmanın giderdiği bir sorun değildir.

## Yeniden üretim ve sınırlar

`python vae_calibration.py --apply` mevcut uyumlu VAE'yi bu normal simülasyon protokolüyle kalibre eder. `python validation.py --train` de artık aynı kalibrasyonu uygular. Başka bir model eğitildiğinde bu sonuçların geçerliliği otomatik olarak korunmaz; o model yeniden kalibre edilmeli ve ayrı veride değerlendirilmelidir. Mevcut çalışmanın eğitim kökeni `validation_results/training_manifest.json` dosyasına işlendi.

Normal simülasyondaki çok düşük oran gerçek sahaya garanti değildir. Bağımsız IMU/yönelim varsayımı, sensör gürültüsü dağılımı ve araç manevraları farklı olabilir. Saldırı sonrası yeniden kabul alarmları rapordaki saldırı dışı yanlış alarm hesabında tutulur; temiz başlangıçtan ayrıca gösterilir. Uzun GNSS kesintisindeki konum sapması ve gerçek GPS/IMU doğrulaması açık kalır.
