# Bağımsız gerçek kayıt testi — 23 Ekim 2026

**Daha sonraki düzeltme:** [Navigasyon regresyonu](NAVIGATION_FIX.md), aynı 209
kaydı güncel sürümde 0/257.896 alarm ve 257.896 kullanılan GNSS ölçümüyle
tamamladı. Aşağıdaki %48,98 ilk dondurulmuş sürüme aittir ve tarihsel kanıt olarak
korunur. Sonraki sonuç geliştirme verisi üzerindedir; yeni bağımsız test değildir.

**Sürüm notu:** Bu rapor dondurulmuş önceki sürüme aittir. Sonraki
[statik alıcı küçük sapma kontrolü](SLOW_ATTACK_FIX.md) `receiver_profile.py` dosyasını
değiştirdi; eski dondurma korunur ve değerlendirici güncel kodla çalıştırılırsa
hash farkı nedeniyle durur. Bu sonuç yeni sürüm için bağımsız başarı sayılmaz.

**Test tamamlandı ve başarısız oldu.** Geliştirmede kullanılan Zurich/cleanStatic
kayıtlarındaki sıfır alarm yeni alıcıya genellenmedi. Bu rapor performans
sorununun giderildiğini değil, bağımsız ölçüm eksikliğinin kapatıldığını gösterir.

## Kaynak ve bağımsızlık

[CMU AirLab](https://theairlab.org/energy-dataset/) tarafından yayımlanan
[Data Collected with Package Delivery Quadcopter Drone](https://kilthub.cmu.edu/articles/dataset/12683453)
(DOI 10.1184/R1/12683453, sürüm 1, CC BY 4.0) kullanıldı.
[Kaynak makale](https://pmc.ncbi.nlm.nih.gov/articles/PMC8213793/), DJI Matrice 100
ve MicroStrain 3DM-GX5-45 GNSS/INS sistemini açıklar. Önceki geliştirme
kayıtlarından farklı bir platform ve alıcıdır; yayımlanan konum zaten GNSS/INS
birleşimidir.

Yeni uçuşlar açılmadan önce algılayıcı kodu ve modellerin SHA-256 değerleri
[donduruldu](validation_results/independent_real_20261023/frozen_detector.json).
Çalıştırma öncesi ve sonrası eşitlik denetlendi. Model eğitilmedi, eşik
değiştirilmedi, sonuçlara göre uçuş seçilmedi. Bu sonuç görüldükten sonra CMU
kayıtları üzerinde yapılacak iyileştirme için başka bir bağımsız test gerekir.

Üreticinin parametre listesindeki **209 kaydın tamamı** değerlendirildi:
196 rota uçuşu, 13 yer/hover/yardımcı kayıt; 257.896 örnek ve toplam 38.717,46
saniye kayıt. Yardımcı kayıtlar da raporda tutuldu. ZIP boyutu ve üretici MD5'i
doğrulandı; her dosya ZIP CRC denetiminden geçti ve SHA-256 ile kaydedildi.
Yerel kaynak özeti: [independent_cmu_manifest.json](independent_cmu_manifest.json).

## Biçim dönüşümü ve kapsam

`position_y` enlem, `position_x` boylamdır. Ölçülen yatay hız
`hypot(velocity_x, velocity_y) * 3.6` ile km/saate çevrilir. CSV'deki `speed`
uçuş komutudur; ölçülen GNSS hızı yerine kullanılmaz. Kayıt saati korunur,
her uçuşta durum sıfırlanır. Yayımlanan 2 m yatay doğruluk, bileşen başına
muhafazakâr 2 m belirsizlik girdisi olarak kullanılır; uçuşlardan uydurulmaz.

C/N0, AV modelinin tam özellik şeması ve bağımsız IMU/yönelim yoktur. Dolayısıyla
RF/VAE devre dışıdır; bu test **fiziksel kurallar ve navigasyon katmanını** sınar.
GPS destekli yönelim/ivme bağımsız referans gibi sunulmaz. Konum RMSE'si veya
saldırı yakalama oranı hesaplanamaz.

## Sonuç

| Ölçüm | Sonuç |
|---|---:|
| Örnek | 257.896 |
| Alarm verilen örnek | 126.321 |
| Nominal örnek alarm oranı | **%48,98** |
| Alarm içeren kayıt | 196 / 209 |
| Fiziksel kuralların NORMAL kararı | 257.896 / 257.896 |
| Filtre yeniliği tutarsızlığı alarmı | 3.784 |
| GNSS yeniden doğrulama bekleme alarmı | 122.537 |

Alarmlar fiziksel saldırı kurallarından değil, navigasyonun filtre ölçüm
reddi ve ardından yeniden kabul beklemesinden geldi. Bu, yeni hareket/alıcı
koşullarında genelleme sorunudur; ölçüm reddi tek başına saldırı kanıtı değildir.
Sonuç düşürülsün diye tutma alarmları silinmedi veya eşikler değiştirilmedi.

Veriler nominal enerji çalışması uçuşlarıdır; üretici örnek bazlı saldırı
etiketi veya bağımsız RF saldırısızlık sertifikası sağlamaz. Bu yüzden %48,98,
**nominal işletim varsayımı altında alarm oranıdır**; etiketli saldırı/temiz
sınıflandırmasından türetilmiş kesin Pfa değildir. Arayüzde bu sınırlama gösterilir.

## Tekrar üretme

```powershell
python download_independent_cmu.py
python validate_independent_real.py
python -m pytest -q
```

Ham sonuçlar ve uçuş bazlı dökümler:
[results.json](validation_results/independent_real_20261023/results.json).
Mevcut dondurulmuş dosyalardan biri değişirse değerlendirici testi geçersiz
sayarak durur; geçmiş dondurma dosyası yeni sürümü onaylamak için yenilenmemelidir.
Hazır kayıt listesinde deterministik ilk uçuş da açılabilir. Öncelikli kalan
sorun, navigasyon filtresinin nominal hareketi reddedip uzun alarm beklemesi
oluşturmasıdır. Tam RF/VAE zinciri ve bağımsız etiketli gerçek saldırı testi de
henüz doğrulanmış değildir.
