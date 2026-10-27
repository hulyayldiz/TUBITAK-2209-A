# Jammertest 2024 bağımsız veri değerlendirmesi

**Sonuç:** Akım mevcut fiziksel kuralları gerçek bir alıcı veri kümesinde çok sayıda saldırıyı geç algılıyor veya kaçırıyor. Bu çalışma bir performans başarısı değil, dış veri üzerindeki açığı ölçen bir değerlendirmedir.

## Veri ve protokol

Kaynak, Jammertest 2024'ün Zenodo v3 kaydıdır ([DOI 10.5281/zenodo.15911589](https://zenodo.org/records/15911589)). Arşiv 375.338.522 bayt olarak indirildi; yayıncı MD5'i ve yerel SHA-256 özeti doğrulandı. Resmî açıklama 24 senaryoyu kapsar: 7 jamming, 8 spoofing, 5 meaconing ve 4 birleşik saldırı.

Senaryo saldırı loglarındaki Z son eki saat bilgisini yanlış UTC gösteriyor. Kaynak analizindeki saatlerle karşılaştırma, bu günlüklerin CEST (UTC+2) yerel saati olduğunu doğruluyor; adaptör olay saatini Europe/Oslo saatinden UTC'ye çeviriyor. NAV-PVT gerçek zaman damgası UTC olarak kalıyor. Zaman düzeltmesinden sonra saldırı aralıkları kayıt örnekleriyle örtüşüyor.

Saldırı etiketleri çıkarım sırasında algılayıcıya verilmedi. Test 24 senaryoda 44.638 PVT epoch'u ve 33 kayıtlı olay içeriyor. İlk geçerli fix öncesi startup satırları dışarıda bırakıldı; daha önce fix alınmışken sonraki geçersiz-fix epoch'ları tutuldu. Fiziksel kurallar C/N0, IMU veya bağımsız konum almıyor. Üretici MON-RF ve fix geçerliliği ayrı gözlemler olarak ele alınıyor. Kayıt dışındaki zamanlar temiz kabul edilmediğinden yanlış alarm oranı hesaplanmıyor.

## Ölçülen sonuç

- 33 olayın **12'sinde yeni alarm kenarı** oluştu; **13'ünde** olay penceresinde en az bir alarm örneği vardı.
- **6 olayda** alarm enjeksiyon başlangıcında zaten etkindi; bunlar yeni saldırı tespiti sayılmadı.
- Yeni alarm oluşan 12 olay için TTD ortalaması **931,4 s**, ortancası **428,3 s**, aralığı **58–4.317 s**. Ortanca önceki akışa göre kısaldı; ortalama uzadı.
- Olay türüne göre yeni alarm: jamming **4/7**, meaconing **1/7**, spoofing **7/15**, birleşik spoofing+jamming **0/4**.
- Fix kaybı alarmı 12 olayda yeni alarm oluşturdu; bu GNSS hizmet kaybını işaretler, tek başına jamming nedeni atfetmez. Yeni alarmların tamamının bu yoldan gelmesi, bağımsız temiz GNSS kesinti kayıtlarıyla yanlış alarm doğrulamasını özellikle gerekli kılıyor.
- MON-RF verisinde 44.633 örnek durum 0 (bilinmiyor/devre dışı), bir örnek durum 2 idi; bu tek durum kayıtlı saldırı penceresiyle örtüşmedi. Bu nedenle MON-RF bu sette olay yakalamadı.
- Kayıtlı olay pencereleri dışında 10.349 epoch'un 195'inde alarm vardı. Yayıncı bu aralıkları sertifikalı temiz diye tanımlamadığı için bu örnekler yanlış alarm sayısı veya oranı olarak raporlanamaz; yine de temiz saha doğrulamasında özellikle incelenmelidir.

Alarmın kayıtlı pencerede görülmesi saldırı nedenini doğrulamaz; GNSS fix kaybı doğal kapsama kesintisinden de kaynaklanabilir. Saldırı dışı aralıklar sertifikalı temiz olmadığı için bu sonuçlardan precision veya yanlış alarm oranı çıkarılamaz.

## Tekrar üretim ve çıktılar

`python validate_jammertest.py` değerlendirme tablolarını üretir. `python export_jammertest.py` uygulama yükleyicisi için 24 kanonik gözlem CSV'si ve her biri için ayrı `.events.json` yan dosyası üretir. CSV'de saldırı etiketi bulunmaz; `receiver_fix_valid` alanı geçerli PVT çözümünü gösterir. Fix ancak önceki geçerli çözümden sonra kaybolmuş ve en az 3 s sürmüşse “olası girişim” alarmına katkı verir; açılışta hiç fix olmaması alarm değildir. Ham arşiv ve dışa aktarımlar `dataset_gercek/external/` altında tutulur ve Git'e eklenmez.

- [Makinece okunabilir sonuç](validation_results/jammertest_20261023/results.json)
- [Olay ölçümleri](validation_results/jammertest_20261023/event_metrics.csv)
- [Senaryo ölçümleri](validation_results/jammertest_20261023/scenario_metrics.csv)
- [Kaynak indirme manifesti](jammertest_2024_manifest.json)
- [Dışa aktarım manifesti](dataset_gercek/external/jammertest_2024/normalized/manifest.json)

## Sınırlamalar

Bu, IHA uçuşu veya bağımsız IMU/konum referansı değildir. NAV-PVT konumu ve hızı alıcının kendi çıktısıdır. C/N0 bulunmadığı için RF/VAE modelleri sınanmadı. `jamInd` yalnızca korundu; farklı alıcıda temiz kalibrasyon olmadan evrensel alarm eşiği uygulanmadı. Jammertest bu çalışmada incelendiğinden artık mühürlü holdout değildir; sonraki ayarların başarısını doğrulamak için yeni, ayrılmış saha kaydı gerekir.
