# TEXBAT saldırı zamanları ve kaçırma ölçümü — 23 Ekim 2026

**Güncellik notu:** Bu dosya CMC entegrasyonu öncesi dondurulmuş sürümün zaman
temelini ve sonuçlarını korur. Güncel algılama zincirinin ayrı replay'i
[burada](TEXBAT_CURRENT_VALIDATION.md).

**Sürüm notu:** Aşağıdaki sayılar ilk zaman doğrulaması yapılan sürüme aittir.
[Sonraki küçük sapma kontrolünün sonuçları](SLOW_ATTACK_FIX.md) ayrı dizinde tutulur;
özellikle DS3'te enjeksiyon öncesi alarm ayrımı korunmalıdır. Kaynak zamanları ve
bu tarihsel sonuç dosyaları değiştirilmedi.

**Gerçek saldırı zamanları kaynaklardan doğrulandı ve ölçüm yapıldı.**
Saldırı kaydında herhangi bir alarm görülmesi yüksek tespit oranı anlamına
gelmiyor: özellikle DS3 ve DS7'de saldırı örneklerinin çoğu kaçırılıyor.

## Kaynak ve zaman ekseni

[Lemmenes, Corbell ve Gunawardena (2016)](https://radionavlab.ae.utexas.edu/images/stories/files/papers/LemmenesGNSSpaper.pdf)
Tablo 1 kayıt başlangıcı farklarını, Tablo 2 DS2 başlangıcına göre olay
zamanlarını verir. İşlenmiş GRID navsol/channel dosyalarından ORT–RRT farkı
hesaplanarak her navigasyon örneği özgün kayıt saatine taşındı. İlk geçerli
navigasyon çözümü yaklaşık 33–36 saniyededir; oynatımın sıfırı saldırı saatinin
sıfırı sanılmadı. Kayıt başlangıçları Tablo 1 ile 1 ms içinde doğrulandı.

| Kayıt | Sinyal enjeksiyonu, kayıt saniyesi | Çekme başlangıcı, kayıt saniyesi |
|---|---:|---:|
| DS2 | 110,1 | 133,0 |
| DS3 | 119,69359668 | 195,79359668 |
| DS7, birincil | 110,0 | 150,0 |

DS3 için dönüşüm `tablo zamanı - (DS3 ofseti - DS2 ofseti)` şeklindedir.
DS7'nin birincil zamanları [UT yazar açıklamasından](https://rnl-data.ae.utexas.edu/datastore/texbat/texbat_ds7_and_ds8.pdf)
alındı: 110 s enjeksiyon, 130 s yakalama, 150 s çekme, 468 s kayıt sonu.
AFIT tablosu kayıt ofsetiyle çevrildiğinde 112,99691752 ve 138,99691752 s verir.
Bu kaynak uyuşmazlığı saklanmadı; alternatif skorlar JSON'a ayrıca yazıldı.
İki PDF'nin SHA-256 değerleri de raporda bulunur.

## Ölçüm sözleşmesi

Etiketler yalnız çıkarım bittikten sonra skorlamaya eklenir. Fiziksel aktivasyon
ile RF enjeksiyonu arası ve başlangıcın ±0,1 s sınırı değerlendirmeden çıkarılır.
Pozitif dönem enjeksiyondan son mevcut navigasyon örneğine kadardır; örnek
gelmeyen kayıt başı/sonu normal sayılmaz. DS2/DS3 için yayımlanmış kapatma
zamanı varsayılmaz. DS7'de 468 s son sınırı ayrıca uygulanır.

Gecikme, enjeksiyondan sonra başlayan **yeni alarm kenarına** göre ölçülür;
önceden süren yanlış alarm sıfır gecikmeli tespit sayılmaz. Örnek bazlı tespit
oranı TP/(TP+FN), kaçırma oranı FN/(TP+FN)'dir. Karantinanın tuttuğu alarmlar
algılayıcı kararıyla karıştırılmadan iki katmanda ayrı raporlanır.

## Sonuçlar

| Kayıt | Algılayıcı tespit / kaçırma | Navigasyon/arayüz tespit / kaçırma | Enjeksiyondan ilk yeni alarma |
|---|---:|---:|---:|
| DS2 | %55,64 / %44,36 | %61,42 / %38,58 | 2,30 s |
| DS3 | %4,52 / %95,48 | %8,98 / %91,02 | 54,91 s |
| DS7 | %6,76 / %93,24 | %8,16 / %91,84 | 296,60 s |

DS7'de ilk alarm kayıt saati 406,60 s; çekme başlangıcından 256,60 s sonradır.
Alternatif AFIT enjeksiyon zamanıyla gecikme 293,60 s olur; iki yorumda da geçtir.
Üç saldırı kaydında da en az bir yeni alarm vardır, fakat **3/3 olay başarısı
saldırı boyunca yüksek tespit oranı değildir**. DS7 enjeksiyon/çekme öncesi
199 değerlendirilen örnekte hiç alarm yoktur.

cleanStatic'te 2.115 örnekte alarm yoktur. Saldırı kayıtlarının değerlendirilen
saldırı öncesi bölümlerinde de alarm yoktur. Ancak bunlar geliştirmede kullanılan
kayıtlardır; bağımsız test sayılmaz. Yeni CMU testinin başarısız sonucu
[ayrı rapordadır](INDEPENDENT_REAL_VALIDATION.md).

## Sınırlamalar ve tekrar üretme

Ham IQ yeniden alıcıdan geçirilmedi; yayımlanmış GRID çözümleri sınandı.
AFIT makalesi DS2/DS3'te cleanStatic/DS7'de bulunmayan donanım kaynaklı
kod/taşıyıcı sürüklenme etkisini açıklar; algılayıcı bu yan etkiyi kullanıyor
olabilir. Bu nedenle sonuç başka saldırı/alıcıya doğrudan genellenemez.
Kod ve modeller değerlendirme boyunca değişmedi; sonuçlara göre eşik ayarlanmadı.

```powershell
python validate_texbat_timing.py
python -m pytest -q tests/test_texbat_timing.py
```

[Ham metrikler](validation_results/texbat_timing_20261023/results.json) ve aynı
dizindeki CSV'ler kayıt saati, oynatım saati, algılayıcı ve arayüz alarmını ayrı
tutar. RF enjeksiyonunun bütün süresini yakalamak hâlâ çözülmesi gereken sorundur.
