# Veri kökeni ve yeniden doğrulama — 23 Ekim 2026

**Yeni bağımsız kaynak:** [CMU AirLab enerji uçuşları](https://theairlab.org/energy-dataset/),
DOI 10.1184/R1/12683453, sürüm 1, CC BY 4.0. Üreticinin 209 kaydının tamamı,
DJI M100/MicroStrain GNSS/INS çıktılarıdır; sentetik değildir. ZIP ve parametrelerin
üretici MD5'i ile yerel SHA-256 değerleri [ayrı manifestte](independent_cmu_manifest.json)
tutulur. Bunlar saldırı etiketli veya bağımsız RF saldırısızlığı kanıtlanmış kayıtlar
değildir; [nominal testin sonucu başarısızdır](INDEPENDENT_REAL_VALIDATION.md).
[TEXBAT saldırı zamanları](TEXBAT_TIMING_VALIDATION.md), UT açıklaması ve AFIT
makalesiyle doğrulandı; DS7 kaynak uyuşmazlığı alternatif skorlarla korunur.

**Sonraki ekleme:** [Gerçek veri entegrasyonu](REAL_DATA_INTEGRATION.md) ile Zurich uçuş paketi ve TEXBAT cleanStatic/DS2/DS3/DS7 işlenmiş MAT kayıtları indirildi. Aşağıdaki ilk denetimdeki “MAT yok” tespiti o ana aittir. Yeni kaynaklar ve yüksek alarm bulguları ayrı raporlanmıştır; ham RF BIN ve IEEE dosyaları hâlâ indirilmedi.

Projede **gerçek deney kayıtları, bu kayıtlardan değiştirilmiş türevler ve tamamen sentetik dosyalar birlikte bulunuyor**. `dataset_gercek` klasör adı bütün içeriğin ham saha kaydı olduğunu göstermiyor.

## Kaynağı doğrulanan AV-GPS dosyaları

Kaynak: [araştırmacının AV-GPS-Dataset deposu](https://github.com/mehrab-abrar/AV-GPS-Dataset), denetlenen commit `81fcce2b88509b2ac22a3ac5e5143af83cb0ca87` (11 Nisan 2024). Yazarların [GPS-IDS makalesi, v2](https://arxiv.org/html/2405.08359v2#S5.SS3) 1–3'ü fiziksel kara aracı deneyleri, 4–6'yı CARLA üretimi olarak ayırıyor. Yerelde 4–6 yok. Deney platformu University of Arizona ACL-Rover; makale Pixhawk, NEO-M8N ve HackRF One kullanımını açıklıyor. Bunlar bizim yaptığımız İHA uçuş ölçümleri değildir.

GitHub içerik API'sindeki Git blob SHA-1 kimlikleri yerel baytlardan bağımsız hesaplandı. Dört CSV **satır sonları dahil birebir aynı** çıktı; dosya adından hareketle sınıflandırılmadı.

| Dosya | Ham satır | Normal / saldırı | Upstream Git blob SHA-1 | Sonuç |
|---|---:|---:|---|---|
| `AV-GPS-Dataset-1.csv` | 62.042 | 46.287 / 15.755 | `a6662ac62caa82e122e11467e3bbee932115734b` | Birebir eşleşti |
| `AV-GPS-Dataset-2.csv` | 6.890 | 5.184 / 1.706 | `93d9d0a084b75bcd967135301993bd6f0307af1d` | Birebir eşleşti |
| `AV-GPS-Dataset-3.csv` | 636 | 231 / 405 | `612aebf07e3d170cb26e7a58c806282683087b4c` | Birebir eşleşti |
| `AV-GPS-Dataset-1-Normal-Data.csv` | 46.287 | 46.287 / 0 | `d540df5fe790af80b4a2b50ab9a55e568eca89ce` | Birebir eşleşti |

Bu kontrol yayımlanan kopyayla özdeşliği kanıtlar; yazarların deneyini bağımsız olarak tekrar yaptığımız anlamına gelmez. Dosyaların bu bilgisayara hangi tarihte ve hangi araçla getirildiğini kanıtlayan eski indirme kaydı bulunamadı.

Makalenin v2 metnindeki sınıf sayıları CSV ile farklı: dosya 1 için 46.787/15.255, dosya 3 için 241/395 yazıyor. Yerel dosyalar upstream ile eşleştiğinden raporda gerçek CSV sayımları kullanıldı. Farkın nedeni doğrulanmadı. Normal-Data dosyası da dosya 1'in normal satırlarıyla bağımsız bir test kümesi sayılmamalı; dört `Yaw Rate` hücresi farklı, diğer hücreler eşleşiyor.

## Gerçek kayıttan değiştirilmiş dosyalar

Üçünde de 62.042 satır ve dosya 1 ile satır satır aynı konum/zaman alanları var. Aşağıdaki alan farkları doğrudan karşılaştırmayla çıkarıldı:

| Dosya | Orijinale göre değişiklik | Uygun tanım |
|---|---|---|
| `IHA-Saha-Verisi.csv` | Hız ve göreli irtifa değişmiş; `Sinyal Gucu (SNR)` eklenmiş. 42 orijinal sütun aynı. | Gerçek kara aracı tabanlı değiştirilmiş senaryo; gerçek İHA saha kaydı değil |
| `Kombine-Gercek-IHA-Saldirisi.csv` | Hız/irtifa ve 41 etiket değişmiş; SNR eklenmiş. 41 orijinal sütun aynı. | Yapay jamming içeren değiştirilmiş senaryo |
| `Gercek-Hibrit-Saldiri.csv` | 443 etiket değişmiş; SNR eklenmiş. 43 orijinal sütun aynı. | Değiştirilmiş senaryo; ek sinyal alanının ölçüm kaynağı belgelenmemiş |

`iha_veri_donusturucu.py` ve `kombine_saldiri_olustur.py`, hız/irtifa değişikliği ve sınıfa göre yapay C/N0/SNR üretimini açıkça içeriyor. Ancak mevcut script, parametre ve rastgele tohumlarla her türevin aynı baytlarını yeniden üreten bir eski üretim manifesti yok. Bu nedenle kesin üretim tarihini/tohumunu iddia etmiyoruz.

Özellikle IHA ve Kombine dosyalarında normal ve saldırı sinyal aralıkları yapay biçimde ayrılmış. Bu dosyalarla ölçülen yüksek sinyal sınıflandırma başarısı gerçek RF saha başarısı sayılamaz: model, etiketle belirlenmiş sinyal üretim kuralını öğrenebilir. Güncel dış veri değerlendirmesi bu türevleri kullanmıyor.

## Sentetik ve kökeni belirsiz dosyalar

- `ornek_dron_saldiri_logu.csv`: 300 satır. `generate_dataset.py` tarafından matematiksel hareket ve rastgele saldırı etkileriyle üretilen örnek; fiziksel uçuş kaydı değil.
- `texbat_scenario1_mock.csv`: 100 satır. `texbat_loader.py` içindeki üreticiyle oluşturulmuş sentetik taklit; resmî TEXBAT deney kaydı değil. [Gerçek TEXBAT kaynağı UT Austin Radionavigation Laboratory'dir](https://radionavlab.ae.utexas.edu/texbat/).
- `validation_results/synthetic_training.csv`: 8.640 satır. Güncel GNSS RF/VAE eğitiminin sentetik kaynağı; eğitim manifestindeki SHA-256 değeri dosyayla eşleşiyor.
- `gnss_training_dataset.csv`: 2.025 satırlık eski özellik/etiket günlüğü. Donanım kaynağını ve toplama koşullarını kanıtlayan manifest yok; gerçek saha kaydı olarak doğrulanamaz. Güncel sentetik eğitim dosyasıyla karıştırılmamalı.

`download_av_gps.py` **veri indirmiyor**: dosya bulunmazsa kökte `AV-GPS-Dataset-1.csv` adıyla 500 satırlık mock üretiyor. Bu, `dataset_gercek/` altındaki hash'i doğrulanmış dosya 1'den farklı yol ve içerik. Bu denetimde üretici çalıştırılmadı.

`download_texbat.py` resmî bağlantıyı gösteriyor ve yerleştirilmiş ZIP'i açıyor; ağdan kendisi indirmiyor. `dataset_gercek` altında `.bin`, `.ubx`, `.iq`, `.zip` veya `.mat` yakalama dosyası bulunmadı. Gerçek TEXBAT ham verisiyle doğrulama yapılmış sayılamaz.

## Antarktika jamming verisi

`GNSS_Jamming/jamming_metadata_by_day_Antarctica.csv`, [aljazblatnik/GNSS](https://github.com/aljazblatnik/GNSS) deposunun `386e09f283c5c4eb7ae26eeea422d59f02a32042` commitindeki özetle satır sonları LF'ye normalize edildiğinde eşleşiyor. Upstream blob `a330b543efa2cf9d5e959f857553d7f4848940b1`; yerelde yalnız CRLF satır sonu farkı var.

Dosya **200 günlük özet satırı**, 81 jamming işaretli gün ve toplam 154.874 olay sayımı içeriyor. Enlem/boylam/hız zaman serisi değil; mevcut navigasyon doğrulamasına örnek örnek verilemez. İlgili gerçek ham gemi GNSS kayıtlarının kaynağı [Zenodo 15783534](https://zenodo.org/records/15783534), fakat o arşiv yerelde yok. Bu özet dosyasıyla ham alıcı davranışı doğrulanmış olmaz.

## Bugün yeniden çalıştırılan doğrulama

- `python -m pytest -q`: **98 test geçti**.
- Streamlit AppTest: simülasyon açılışı ve arayüzden orijinal dosya 3'ün yerel yolla yüklenip oynatılması geçti. `ml_source=AV_KINEMATIC_RF`, `cn0_available=false` doğrulandı; döngü istisnası görülmedi. Bu arayüz testi kısa oynatım kontrolüdür; bütün kaydın sayısal sonuçları aşağıdaki ayrı yeniden değerlendirmedir.
- Güncel 30.000 örneklik sentetik rapordaki kaynak/model SHA-256 değerleri mevcut dosyalarla eşleşiyor. Aynı sentetik koşular yeniden çalıştırılmadı; çekirdek kod/model değişmedi.
- Orijinal AV-GPS dosya 1–3 üzerinde `validation.evaluate_av` yeniden çalıştırıldı; model yeniden eğitilmedi ve eşikler ayarlanmadı.

| Değerlendirme verisi | İşlenen örnek | Ayrı kinematik RF tespiti | Yanlış alarm | TP / FN / FP / TN |
|---|---:|---:|---:|---|
| Dosya 2 | 6.781 | %99,59 | %0,12 | 1695 / 7 / 6 / 5073 |
| Dosya 3 | 633 | %93,55 | %0 | 377 / 26 / 0 / 230 |

Dosya 1, AV modelinin eğitim verisi olduğu için bağımsız RF test skoru verilmedi. Eksik/tekrarlanan zamanlar ve yeni kayıt bölümlerinin başlangıçları nedeniyle işlenen örnek sayısı ham satır sayısından farklıdır. Eğitimdeki zaman/konum/hız kimliğiyle test çakışması iki dosyada da 0. Dosya 2 ile 3 arasında ise 387 ortak kimlik var; birbirinden bağımsız tekrarlar gibi birleştirilmemeli.

**Yukarıdaki skorlar bütün hibrit sistemin gerçek saha skoru değildir.** C/N0'suz kayıtlara uygun ayrı AV modeli yalnız dosya 1 ile eğitildi. `Data Type` ve `EKF Detector` özellik olarak kullanılmıyor. Aynı kayıtlarda tek başına fiziksel kuralların tespiti dosya 1/2/3 için sırasıyla %5,93 / %12,57 / %47,39; fiziksel kurallar tek başına yeterli değil. Orijinal dosyalarda ölçülmüş C/N0 ve bağımsız doğru konum olmadığından GNSS RF/VAE katmanları ve gerçek navigasyon RMSE'si bu dosyalardan doğrulanamaz.

Önceki konuşmadaki %0 normal yanlış alarm ve %2,38 toparlanma oranları **sentetik simülasyon** sonuçlarıydı. Onlar bu gerçek kayıt skorlarıyla veya gerçek cihaz saha testiyle aynı şey değildir.

## Diğer doğrulama sonuçları

- Erişilebilir seri GPS portu yok; gerçek cihaz saha deneyi yapılmadı.
- Docker yürütülebiliri bulunamadı; imaj derleme/çalıştırma doğrulanmadı.
- `python verify_hashes.py` **başarısız, çıkış kodu 1**: `forensic_ledger.jsonl:1` mevcut anahtarla doğrulanamadı. Anahtar uyuşmazlığı veya kayıt değişikliği olasılıkları arasında kesin neden belirlenmedi. Bu sonuç 98 birim testin geçmesinden ayrıdır; mevcut kayıt zinciri doğrulanmış sayılamaz. Veri dosyaları, anahtar ve mevcut kayıt zinciri değiştirilmedi.

## Kanıt dosyaları ve tekrar çalıştırma

- [Upstream commit/blob kayıtları](validation_results/data_audit_20261023/upstream_snapshot.json)
- [Yerel SHA-256, satır/sınıf sayımları ve alan farkları](validation_results/data_audit_20261023/inventory.json)
- [Gerçek AV yeniden değerlendirmesi](validation_results/data_audit_20261023/external_revalidation.json)
- [Kontrol özeti](validation_results/data_audit_20261023/verification_summary.json)

`python audit_data_provenance.py` kaydedilmiş 23 Ekim upstream snapshot'ına karşı yerel envanteri yeniden hesaplar; internette yeni sürüm aramaz. Dosya adları, makale cümleleri veya klasör adı tek başına gerçeklik kanıtı sayılmaz. Hash eşleşmesi, kaynağın yayımladığı kayıtla aynı kopyayı kullandığımızı doğrular; deneyin tüm etiketlerinin doğru olduğunu veya uygulamanın sahada güvenli olduğunu kanıtlamaz.
