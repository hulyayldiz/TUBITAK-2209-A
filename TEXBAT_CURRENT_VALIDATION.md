# TEXBAT güncel kodla replay — 23 Ekim 2026

Bu replay güncel algılama zincirini kullanır ve önceki raporlardan ayrıdır. Sonuçlar saldırı etiketleri çıkarıma verilmeden üretildi. Dondurma listesi CMC kodunu, kısa/uzun CMC hesaplarını, TEXBAT veri adaptörünü ve kalibrasyon profilini içeriyor. Ham RF IQ yeniden alıcıdan işlenmedi; TEXBAT'ın yayımlanmış GRID NAV ve kanal ölçümleri kullanıldı.

## Güncel sonuçlar

| Kayıt | Karar örnek kapsamı | Navigasyon/arayüz kapsamı | İlk yeni karar alarmı | Onset'te alarm önceden etkin mi? |
|---|---:|---:|---:|---|
| cleanStatic | temiz pencerede 0 yanlış alarm / 2.115 örnek | aynı | — | — |
| DS2 | %99,77 | %99,77 | onset +0,90 s | Hayır |
| DS3 | %100 | %100 | Yeni alarm yok; onset'te alarm zaten açık | Evet |
| DS7 | %98,49 | %98,49 | onset +5,60 s | Hayır |

DS7'de 1.789 skorlu saldırı örneğinin 1.762'si alarma girdi, 27'si ilk alarm gelene kadar kaçtı. İlk alarm kayıt saati 115,60 s'de oluştu (onset +5,60 s). Yayınlanan ana zaman çizelgesine göre enjeksiyon 110 s, yakalama 130 s, çekme 150 s'dir. Çekme sonrasındaki yaklaşık 21 saniyelik CMC kanıt zayıflığında alarmı düşürmeme kuralı kesintisiz alarm sağladı. Alternatif AFIT zamanlaması onset'i 113 s kabul ettiği için aynı izde kapsam %99,32 ve gecikme 2,60 s olur; zaman çizelgesi çelişkisi nedeniyle iki skor da korunuyor.

## Ölçümlerin gösterdiği neden

**DS7:** NAV, hız, clock ve C/N0 ölçümleri saldırının ilk saniyelerinde yeterince ayırt edici değil. Hızlı CMC yolu 1 saniyelik eğim penceresi, altı örnek ve 0,4 saniyelik üç örnekli onay kullanıyor; uzun CMC yolu 20 saniyelik pencere ve üç saniyelik onayla yedekte kalıyor. Hızlı eşik cleanStatic'in 50–120 s kalibrasyon aralığından türetiliyor; en az dört uydu ve %75 uyum koşulu uygulanıyor. Kayıtta yeterli uyumlu CMC sapması yaklaşık 115 s'de belirginleşiyor ve onay sonrası alarm 115,60 s'de geliyor. Onaylanmış alarm, bir uzun CMC penceresi artı onay süresi (23 saniye) boyunca yeni anormal kanıt görülmezse kapanıyor. Saldırı türünü tek başına ispatlamaz.

CMC'nin bu kayıtta yakalaması, önceki rapordaki %33,31 / 238,80 s ölçümünün neden artık güncel olmadığını açıklıyor: önceki dondurma listesi CMC kodu ve kalibrasyonunu içermiyordu. Doğrulama betiği düzeltildi; bundan sonraki replay'ler bu bağımlılıkları donduruyor.

**DS3:** Zaman kaynakları bir “activation” anını yaklaşık 114,9 s, RF enjeksiyonunu 119,7 s olarak veriyor. Alıcı profilindeki `reported_clock_drift_m_s` uyarısı yaklaşık 118 s'de, tanımlı enjeksiyon başlangıcından önce oluşuyor; CMC o anda alarm vermiyor. Güncel replay'de alarm onset'te zaten açık ve tüm saldırı örnekleri boyunca açık kaldığı için örnek kapsamı %100 olsa da yeni bir yükselen alarm ölçülemiyor. Clock sapmasının nedenini bu kayıttan tek başına doğrulayamıyoruz.

## Sınırlamalar

`cleanStatic` kalibrasyon verisi olarak kullanıldı; oradaki 0/2.115 alarm bağımsız yanlış-alarm oranı değildir. Hızlı pencere aynı temiz kaydın 50–120 s önekiyle kalibre edilmiştir. Sonraki temiz bölüm mühürlenmiş bağımsız holdout değildir. Hızlı pencere ve onay parametreleri DS7 davranışı incelenirken değiştirildi; bu nedenle bu rapordaki DS7 skoru aynı veriden bağımsız, önceden kilitlenmiş doğrulama sonucu değildir ve keşifsel sonuç olarak ele alınmalıdır. Denenen çok düşük hızlı-CMC eşikleri bu kayıt üzerinde yanlış alarm üretti; daha hassas ayarlar başka alıcıda ayrıca sınanmalıdır. DS7 ana zaman çizelgesinde kalan 27 kaçırma ilk alarmdan önce toplanır. DS3'te kapsam %100 görünse de onset'te alarm zaten açık olduğundan yeni saldırı tespit süresi ölçülemiyor. Zamanlama kaynakları DS7 için de farklı sonuç verir. Bu nedenle TEXBAT'ta her saldırı kaçırmasını sıfırladığımızı ya da gerçek alıcı/IHA performansını kanıtladığımızı söyleyemeyiz; bağımsız holdout, ham RF IQ işleme ve bağımsız IMU/yönelim gerekir.

## Tekrar üretim

`validate_texbat_timing.py` değerlendirmeyi tekrar üretir. Tarihsel raporları ezmemek için bu replay `validation_results/texbat_current_20261023/` dizinine kaydedildi.

- [Güncel makinece okunabilir sonuç](validation_results/texbat_current_20261023/results.json)
- [DS7 karar izleri](validation_results/texbat_current_20261023/ds7_predictions.csv)
- [CMC kalibrasyonu](models/grid_cmc_profile.json)
