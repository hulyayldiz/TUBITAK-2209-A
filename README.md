# GNSS sinyal bütünlüğü araştırma prototipi

[Güncel aktif sorunlar ve doğrulama sınırları](ACTIVE_ISSUES.md). Kaynak-yöntem izlenebilirliği ve literatür kapsamı [literatür eşlemesinde](LITERATURE_REVIEW.md).

Yeni alıcıda bağımsız sınama için seçilen FGI Jammertest 2025 aday veri kümesi ve
test öncesi dondurma/ölçüm protokolü [holdout protokolünde](INDEPENDENT_HOLDOUT_PROTOCOL.md)
belgelenmiştir; katalog açık erişim bildiriyor ancak dosyalar yerelde alınmış ve
şema doğrulanmış değil. İndirme yolu başvuru öncesi yeniden doğrulanmalı.
TÜBİTAK 2209-A araştırma odağı, bu bağımsız veri üzerinde mevcut GNSS tutarsızlık
izleyicisinin sıfır-atış değerlendirmesidir; [başvuru metni taslağı](output/docs/TUBITAK_2209A_GNSS_TYBS_Metin_Taslagi.docx)
TYBS'ye yüklenmez ve veri erişimi doğrulanana kadar koşullu plan olarak kalır.

GNSS jamming ve spoofing belirtilerini inceleyen Streamlit uygulaması. Simülasyon, etiketli kayıt oynatımı ve pasif seri/TCP/UDP NMEA alımı desteklenir. Gerçek uçuş kontrolü ve saha güvenliği doğrulanmış değildir.

[Alıcıya özel profil sistemi](RECEIVER_PROFILES.md): farklı alıcı ve statik/hareketli kullanım için ayrı normal kalibrasyon + ayrı oturum kontrolü, kimlikle eşleştirme ve mevcut sensörlere göre özellik seçimi eklendi. Edinim süresi profilde tanımlanır; güçlü anlık saat sapması için tüm pencerenin dolması beklenmez. Yeni fiziksel alıcıda saha doğrulaması hâlâ gereklidir.

[Kalıcı küçük sapma kontrolü](SLOW_ATTACK_FIX.md): statik GRID profilinde biriken sapma için geliştirilen önceki kontrol ve sentetik testler belgelenmiştir. Buradaki DS7 sonucu eski sürüme aittir; güncel, yeniden dondurulmuş replay sonuçları [TEXBAT_CURRENT_VALIDATION.md](TEXBAT_CURRENT_VALIDATION.md) içindedir. DS3'te enjeksiyon öncesi tutarsızlık da görüldüğünden alarm kapsamı saldırı kimliğinin kanıtı değildir. Hareketli alıcıda bağımsız IMU ve yeni holdout testi hâlâ gerekir.

**Güncel gerçek veri sonucu:** [Navigasyon düzeltmesi](NAVIGATION_FIX.md) sonrasında CMU'nun 209 kaydında 257.896 örneğin tamamı filtre tarafından kullanıldı ve alarm oluşmadı; önceki bağımsız sürümde oran %48,98'di. Bu veriler artık geliştirmede kullanıldı; sonuç yeni bağımsız başarı veya evrensel sıfır alarm iddiası değildir. DS7 güncel replay'inde %98,49 örnek kapsamı ve +5,60 s ilk alarm ölçülmüştür; 1.789 örneğin 27'si ilk alarm öncesidir. Bu skor DS7 gözlemleri sonrası ayarlandığı için keşifseldir; bağımsız test sayılmaz. Ayrıntılar [güncel replay raporunda](TEXBAT_CURRENT_VALIDATION.md).

## Kurulum ve çalıştırma

Python **3.11 veya üzeri** gerekir; scikit-learn 1.8 Python 3.10'u desteklemez. Komutları proje dizininde çalıştırın:

```powershell
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q
python validation.py --train --runs 5 --steps 1200
streamlit run main.py
```

Model dosyaları Git'e dahil edilmez. Temiz kurulumda `--train` modelleri oluşturur. Model bulunmadığında arayüz ilgili katmanın devre dışı olduğunu belirtir. Küçük LSTM'nin CPU çıkarımı varsayılan tek iş parçacığıyla çalışır; `GNSS_INFERENCE_THREADS` değişkeniyle değiştirilebilir.

### API anahtarı gerektirmeyen yerel sohbet

Genel amaçlı sohbet, bilgisayarda çalışan Ollama ve varsayılan `gemma3:4b` modeliyle yapılır; Gemini/API anahtarı kullanılmaz. Ollama'yı kurduktan sonra modeli bir kez indirin:

```powershell
ollama pull gemma3:4b
ollama serve
```

Ollama zaten arka planda çalışıyorsa `ollama serve` adımını atlayın. Model yanıtı tamamen yerelde üretir; ilk yanıt model yüklenirken gecikebilir. Farklı bir model veya Ollama adresi için `.env` içinde `OLLAMA_MODEL` ve `OLLAMA_BASE_URL` değerlerini ayarlayın. Ollama, Python `requirements.txt` paketlerinden bağımsız kurulur.

Eğitim verisi toplama yalnızca simülasyon döngülerini oturum kimliğiyle kaydeder; veri kümesi replay etiketleri eğitim dosyasına eklenmez. Model eğitimi en az üç ayrı toplama oturumu ister ve satır bazlı rastgele bölme yapmaz. RF grouped-CV/oturum holdout ile, VAE oturum bazlı normal eğitim ve ayrı sentetik-normal kalibrasyon koşularıyla eğitilir. Bu kalibrasyonlar saha yanlış-alarm garantisi değildir.

## Karar ve navigasyon

- Fiziksel kurallar C/N0, ivme, yön ve ardışık konum tutarlılığını inceler.
- GNSS Random Forest ve LSTM-VAE ortak, sürümlenmiş dört özellik kullanır. VAE, normalizasyonu ve eşiğiyle birlikte saklanır. İstatistiksel alarm için süreklilik aranır; skorlar kalibre edilmiş olasılık değildir.
- Bağımsız yönelim ve navigasyon eksenindeki IMU mevcutsa zaman penceresi içindeki beklenen hareket GNSS ile karşılaştırılır. Bu girdiler yoksa kontrol çalışmaz. MPU6050 tek başına mutlak yönelim kaynağı sayılmaz.
- C/N0 olmayan AV-GPS kayıtları için ayrı kinematik RF modeli vardır. Yalnız dosya 1 ile eğitilir; dosya 2 ve 3 eğitim dışı değerlendirilir. Bu model GNSS RF/VAE modelinin yerini bütün sensörlerde otomatik olarak almaz; gerekli AV sütunları bulunmalıdır.
- Jamming'de düşük kaliteli fakat fiziksel olarak tutarlı GNSS ölçümleri düşük ağırlıkla birleştirilir. Spoofing'de şüpheli GNSS reddedilir. Yeniden kabul için süreklilik ve filtre yenilik kontrolü uygulanır; bağımsız pencerenin uygun referansı varsa başlangıçtaki hız/konum kirlenmesi giderilir.
- Uzun kesintide belirsizlik artar ve arayüzde gösterilir. Yazılım araç motorlarına, otopilota veya iniş sistemine komut göndermez.

## Gerçek veri

23 Ekim 2026 [kaynak ve doğrulama denetimi](DATA_PROVENANCE.md): Orijinal AV-GPS dosya 1–3 ve Normal-Data kaynakla birebir eşleşiyor. İHA/Hibrit/Kombine dosyaları değiştirilmiş türevlerdir; TEXBAT mock ve dron örnek logu sentetiktir. Antarktika dosyası yalnız günlük özet içerir. Gerçek kayıtlar ve sentetik simülasyon başarı oranları ayrı değerlendirilmelidir.

[Gerçek İHA/TEXBAT entegrasyonu](REAL_DATA_INTEGRATION.md): Zurich uçuş paketi ve dört işlenmiş TEXBAT kaydı indirildi; arayüzde hazır kayıt listesinden açılır. `python download_real_data.py` indirme/hash denetimi, `python validate_real_data.py` tam oynatma yapar. **Temiz gerçek kayıtlarda yüksek alarm görüldü; mevcut kurallar/modeller bu kaynaklarda saha kullanımı için doğrulanmış değildir.**

[Gerçek alarm düzeltmesi](REAL_ALARM_FIX.md): GPS tekrarları ve ölçüm belirsizliği düzeltildi; statik GRID alıcısında ayrı normal kalibrasyonlu gözlem profili kullanılıyor. Güncel yeniden oynatmada Zurich 13.531 GPS güncellemesinde ve cleanStatic 2.115 örnekte alarm yok; saldırı kayıtlarında alarm sürüyor. Bu kayıtlar geliştirmede kullanıldığı için bağımsız saha başarısı veya evrensel sıfır yanlış alarm iddiası değildir.

NMEA parçaları birleştirilir, sağlama toplamı ve fix geçerliliği kontrol edilir. GGA hızı sıfırlamaz; uygun RMC/VTG hızı olmadan yeni navigasyon örneği oluşturulmaz. GSV varsa ölçülmüş C/N0 alınır; eski ölçüm zaman aşımına uğrar. Yeni fix gelmezse simülasyon verisi üretilmez.

CSV oynatımı kayıt zamanını kullanır; ayrı kayıtların saat sıfırlamaları filtre durumunu sıfırlar. Konum/hız eksikse, etiket bilinmiyorsa veya sayılar geçersizse veri reddedilir. Aynı isimle değiştirilen dosya yeniden yüklenir. Bağımsız referans olmadan RMSE/gerçek konum katmanı, etiket olmadan sınıflandırma metrikleri gösterilmez.

IMU eksenleri ve kayıt şeması için [saha doğrulama belgesine](FIELD_VALIDATION.md) bakın. Gövde ekseninden dönüşüm ancak açıkça verilen bağımsız yönelimle ve belirtilen eksen sözleşmesiyle yapılır; yerçekimi çıkarılır.

## Tekrarlanabilir değerlendirme

[Son toparlanma düzeltmeleri](RECOVERY_REPORT.md), [güncel ölçümler](validation_results/course_recovery_20261023/VALIDATION_REPORT.md), [ham sonuçlar](validation_results/course_recovery_20261023/validation_results.json) ve [eğitim kökeni](validation_results/training_manifest.json) birlikte değerlendirilmelidir. Önceki RF/VAE çalışmasında aynı normal girdilerde 62/6000 yanlış alarmlı örnek 0/6000 oldu. Son sürüm koordinat sıçraması sonrası pencere temizliğini, erken GNSS kabulünü ve sıçrama açısının sonraki hareket yönünü bozmasını düzeltir; toparlanma alarmları raporda tutulur.

```powershell
python validation.py --runs 5 --steps 1200
```

Yeni bir değerlendirme için örneğin `--seed-start 60001 --output validation_results/new_evaluation` eklenebilir. Eğitim kökeninin raporda korunması için `training_manifest.json` yeni çıktı dizinine de kopyalanmalıdır. Son takip çalışması `--runs 3 --seed-start 50001 --output validation_results/followup_20261023` ile 18.000 örnek içerir.

Beş senaryo beşer kez çalışır: normal, jamming, spoofing, yavaş spoofing ve normal C/N0 dağılımını koruyan örtülü spoofing. Her koşu 10 dakikalık hızlandırılmış simülasyondur; toplam 250 dakika ve 30.000 örnek. Bu süre gerçek saha kayıt süresi değildir. Eğitim, eşik kalibrasyonu ve değerlendirme tohumları ayrıdır. RF holdout/CV ayrımı koşu gruplarını korur; VAE pencereleri saldırı veya kayıt sınırlarını köprülemez. Dosya 2 ve 3 kısmen örtüştüğünden birbirinden bağımsız tekrarlar gibi birleştirilmez.

Eski sunumlardaki %98,5 doğruluk, alt metre RMSE, sıfırıncı gün koruması ve standart uyumluluğu ifadeleri doğrulanmış güncel sonuç değildir. Gerçek GPS/IMU saha doğrulaması tamamlanmadı. Simülasyondaki iyileşme her araca veya saldırıya genellenemez.

## Adli kayıtlar

`.env` içindeki `FORENSIC_SECRET_KEY` kullanılır. Tanımlanmazsa `.forensic_secret` içinde kurulum başına rastgele anahtar oluşturulur. Anahtarı kayıtlarla birlikte koruyun; eski kayıtlar ancak oluşturuldukları anahtarla doğrulanabilir.

HMAC zinciri dosya kilidi altında yazılır; döndürülmüş segmentler de zincir sırasıyla doğrulanır. Yazma başarısızsa oturum başı ilerletilmez; bozuk zincire ekleme yapılmaz. `python verify_hashes.py` doğrulama başarısızsa sıfırdan farklı çıkış kodu döndürür.

[23 Ekim hash düzeltmesi](HASH_RECOVERY_REPORT.md): Eski 19 kayıt aynen arşivlendi; dört tarihsel zincir kopukluğu raporlandı. Yeni özel anahtarlı zincir, arşiv ve rapor hash'lerini imzalı başlangıç kaydında korur. Uygulama ve doğrulayıcı aynı sabit proje yolunu kullanır.

Bu mekanizma değişiklik tespiti sağlar. Yerel HMAC kayıtları tek başına bütün bir geçmişin silinmesini veya eski geçerli bir geçmişe dönülmesini kanıtlayamaz; bunun için harici güvenilir kayıt çapası gerekir. NIST uyumluluğu veya değiştirilemez depolama sertifikası iddia edilmez.

## Temel modüller

`detection.py`, `features.py`, `ml_detection.py`, `inertial_monitor.py`, `domain_model.py`: tespit. `fusion.py`, `navigation.py`: kestirim ve GNSS kabul politikası. `nmea_stream.py`, `live_gps.py`, `imu_processing.py`, `dataset_loader.py`: veri alımı. `artifact_io.py`: atomik model güncelleme/önbellek. `forensic_ledger.py`: eşzamanlı ve segmentli kayıt. `validation.py`: değerlendirme. `main.py`: arayüz koordinasyonu.

Lisans: [MIT](LICENSE).
