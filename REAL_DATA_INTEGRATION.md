# Gerçek veri entegrasyonu — 23 Ekim 2026

**Güncel bağımsız sonuç:** [CMU'nun 209 yeni kaydı](INDEPENDENT_REAL_VALIDATION.md)
indirildi ve farklı alıcı/platformda sınandı. Nominal örnek alarm oranı %48,98;
önceki temiz kayıttaki sıfır alarm genellenmedi. Yeni indirme komutu
`python download_independent_cmu.py`, değerlendirme `python validate_independent_real.py`.
İlk CMU uçuşu hazır kayıt listesinde bulunur. [TEXBAT zaman/kaçırma ölçümü](TEXBAT_TIMING_VALIDATION.md)
de tamamlandı; saldırı kaydında alarm bulunması yüksek tespit oranı anlamına gelmez.

**Sonraki düzeltme:** Aşağıdaki alarm tablosu ilk entegrasyon bulgusudur. [Gerçek alarm düzeltmesi](REAL_ALARM_FIX.md) GPS tekrarlarını, ölçüm belirsizliğini ve alıcı/model uyumsuzluğunu giderir. Güncel oynatma çıktıları `validation_results/real_alarm_fix_20261023/` altındadır; bu belgedeki ilk alarm sayıları güncel sonuç diye kullanılmamalıdır.

Gerçek İHA uçuş kaydı ve gerçek TEXBAT RF kayıtlarından üretilmiş alıcı çıktıları
indirildi, kaynak adaptörleriyle uygulamaya bağlandı ve tüm satırlar oynatıldı.
Toplam **294.406.091 byte** (294 MB / 281 MiB) içerik `dataset_gercek/external/`
altında yereldir. Adres, boyut ve SHA-256 bilgileri `real_data_manifest.json`
içindedir. Büyük dosyalar Git/Docker kapsamı dışında; kod ve manifest kapsam içindedir.

## İndirilen kayıtlar

| Kaynak | Biçim | Oynatılan örnek | Kullanılan alanlar |
|---|---|---:|---|
| Zurich Urban MAV / Fotokite | `AGZ_subset.zip` | 81.169 | GPS, kuzey/doğu hızı, zaman; 81.155 satırda gövde ivmesi |
| TEXBAT cleanStatic | `navsol.mat` + `channel.mat` | 2.115 | Konum, alıcı hızı, zaman, C/N0 |
| TEXBAT DS2 | Aynı | 2.100 | Aynı |
| TEXBAT DS3 | Aynı | 2.096 | Aynı |
| TEXBAT DS7 | Aynı | 2.175 | Aynı |

Kaynaklar: [University of Zurich](https://rpg.ifi.uzh.ch/zurichmavdataset.html),
[UT Austin TEXBAT](https://radionavlab.ae.utexas.edu/texbat/) ve
[UT işlenmiş veri arşivi](https://rnl-data.ae.utexas.edu/datastore/texbat/processed/).
Zurich sayfası yaklaşık 200 MB dese de mevcut ZIP 279.153.939 byte çıktı.
Görüntü alt kümesinin yanında uçuşun 81.169 GPS satırını içeriyor. Özgün README
ve kaynak sayfaları korunur; görüntü hakları README'de ayrıca belirtilmiştir.
Uygulama görüntüleri açmaz veya çıkartmaz.

**İndirilmeyenler:** Ham TEXBAT `.bin` (saldırı senaryosu başına yaklaşık
39–44 GB) ve [IEEE UAV Attack Dataset](https://ieee-dataport.org/open-access/uav-attack-dataset)
(ücretsiz IEEE hesap girişi gerekir). İşlenmiş MAT gerçek kayıttan gelir,
fakat ham RF I/Q değildir. Bu iki indirilmeyen kaynak üzerinde test yapılmadı.

## Farklı biçimler nasıl birleşiyor?

Akış: **Kaynak dosya → kaynak adaptörü → birim/zaman/kalite kontrolü →
ortak gözlem tablosu → mevcut oynatıcı → uygun tespit katmanları.**

Ortak alanlar: `timestamp_s`, `lat`, `lon`, `speed_kmh`.
İsteğe bağlı alanlar: `cn0`, saldırı etiketi, IMU ve bağımsız referans konum.
Eksik ölçümün yerine sıfır veya yapay normal etiketi konulmaz.

| Girdi | Dönüşüm | Sınır |
|---|---|---|
| AV-GPS CSV | Bilinen sütunlar, m/s→km/sa; AV özellikleri varsa ayrı AV kinematik modeli | C/N0 yoksa sinyal RF/VAE kapalı |
| Genel CSV | Bilinen sütun takma adları ve hız birimleri | Tanınmayan alan/birim için açık sözleşme gerekir |
| Zurich ZIP | GPS/RawAccel dosyaları seçilir; mikrosaniye→saniye; kuzey/doğu hızından yatay hız | C/N0 ve saldırı etiketi yok |
| TEXBAT GRID MAT | Bilinen navsol matrisi transpoze edilir; ECEF metre→WGS84 derece; ECEF hızından yerel yatay km/sa | GRID alan tanımları zorunlu |
| TEXBAT kanal MAT | Geçerli kanalların C/N0 ortalaması geçmişten eşlenir | En çok 0,5 saniye; gelecek ölçüm kullanılmaz |
| ZIP | Tanınan Zurich/TEXBAT paketi veya tek genel CSV | Çoklu genel CSV'de ilk dosya rastgele seçilmez |
| ULog / UBX / RINEX / ROS bag | Doğrudan adaptör henüz yok; uygun ayrıştırıcıyla ortak tabloya çevrilmeli | Uzantıyı CSV yapmak yetmez |
| Ham RF IQ/BIN | Önce GNSS yazılım alıcısı, sonra alıcı çıktısına adaptör | Program ham RF demodülasyonu yapmıyor |

MAT'ta eski “en büyük matrisi seç” davranışı kaldırıldı. Yeni kaynak için
`dataset_adapters.py` içine sütun/birim sözleşmesi ve örnek testler eklenmeli;
ardından `real_data_catalog.py` listesine alınabilir. Bu yapı bütün olası
dosyaları kendiliğinden tanıyan evrensel bir yükleyici değildir.

## Kaynak ayrıntıları ve güven sınırları

- Zurich README 1e7 koordinat gösterimini anlatırken yayımlanan örnek zaten
  ondalık derece içeriyor. Adaptör bu iki temsili ayırır; örnekteki dereceler
  tekrar 1e7'ye bölünmez. İrtifa kullanılmıyor.
- Altı küçük zaman sırası ihlali sabit sıralamayla giderilir; saatler
  değiştirilmez. GPS satırları görüntü saatine hizalıdır ve aynı alıcı
  çözümünü tekrarlayabilir; her satır bağımsız GNSS çözümü değildir.
- Gövde ivmesi en fazla 0,2 saniye geçmişten eşlenir. Eşleşmeyen 14 satırda
  IMU yoktur. Gövde eksenleri veya GPS destekli otopilot yönelimi bağımsız
  navigasyon ivmesi sayılmaz.
- Zurich referansı UTM 32N kamera pozudur. Antenle aynı referans kabul edilip
  RMSE üretilmez. TEXBAT alıcı konumu da kendi doğruluk referansı değildir.
- Bu entegrasyonda saldırı başlangıç/bitiş çizelgeleri doğrulanmadı.
  Etiketsiz satırda dahili `normal` yer tutucusu olsa da
  `ground_truth_available=False` kalır; Pd/FPR/F1/TTD hesaplaması kapalıdır.
- Katalog dosyaları ve TEXBAT kardeş kanal dosyası yüklenmeden manifest
  hash'iyle denetlenir. Değişmiş kaynak reddedilir, açık eski veri korunur.
  SHA-256 yerel bütünlük kontrolüdür; yayıncının imzalı doğruluk sertifikası
  değildir. HTTPS sertifika doğrulaması kapatılmadı.

## Tam oynatma bulguları

**Entegrasyon çalışıyor; mevcut algılayıcılar bu kaynaklarda kullanıma hazır
değil. Temiz kayıtta yüksek alarm, açık bir uyumsuzluk bulgusudur.**

Toplam **89.655 örnek**, mevcut sabit modellerle, yeniden eğitim/eşik ayarı
yapmadan işlendi. Son konumlar sonlu kaldı, etiketsiz veriden başarı oranı
üretilmedi. Çıktılar:

| Kayıt | NORMAL çıktısı | Alarm çıktısı |
|---|---:|---:|
| Zurich | 35.665 | 45.504 |
| cleanStatic | 0 | 2.115 |
| DS2 | 0 | 2.100 |
| DS3 | 1.385 | 711 |
| DS7 | 103 | 2.072 |

Bunlar doğrulanmış saldırı sayısı veya başarı oranı değildir. Özellikle
cleanStatic'te tüm satırların alarm vermesi mevcut sistemin bu temiz
kayıtta hazır olmadığını gösterir. Zurich'te C/N0 ve AV özellik şeması yok;
ML kapalıdır, alarmlar kural/navigasyon akışından gelir. TEXBAT'ta mevcut
sentetik eğitimli RF/VAE çalışır. Aynı birimlere dönüşüm, model dağılımının
uyumlu olduğunu kanıtlamaz. Sonuçlar gizlenmedi ve bu test kayıtlarına bakıp
eşikler değiştirilmedi. Sonraki değerlendirme için doğrulanmış zaman
çizelgesi ve ayrı eğitim/kalibrasyon/test uçuşları gerekir. GPS tekrarları
ve örnekleme farkları ayrıca incelenmelidir.

## Kullanım ve doğrulama

1. Arayüzde **Veri Seti Yükle → Hazır gerçek kayıt** kaynağını seçin.
2. **Gerçek kaydı yükle** düğmesine basın. Eksik alanlar ve sınırlamalar gösterilir.
3. `python download_real_data.py`: eksikleri indirir, manifesti denetler.
4. `python validate_real_data.py`: beş kaydı tamamen oynatır.

Eski `texbat_loader.py` artık veri yokken otomatik sentetik senaryo üretmez.
`download_texbat.py` yeni indiriciye yönlenir. Büyük indirmeler kaynak koddan
ayrıdır; Docker içinde kullanmak için kaynakları ayrıca bağlamak gerekir.

**119 pytest testi geçti.** Beş kayıtta Streamlit AppTest yükleme/oynatma
kontrolünde uygulama istisnası görülmedi. Gerçek alarm bildirimleri çalışma
hatası sayılmadı veya gizlenmedi. Adli hash zinciri de geçerli.

Ham çıktılar `validation_results/real_data_integration_20261023/` içindeki
`replay_results.json` ve `ui_results.json`. Bu offline kayıt oynatımıdır;
bizim yaptığımız saha deneyi veya canlı İHA kontrolü değildir.
