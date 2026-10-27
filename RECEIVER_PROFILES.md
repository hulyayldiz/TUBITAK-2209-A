# Alıcıya özel profil kapsamı — 23 Ekim 2026

**Sonraki sürüm:** [Navigasyon düzeltmesi](NAVIGATION_FIX.md), bu rapordaki tarihsel
CMU alarmlarını aynı 209 kaydın yeniden oynatımında 0/257.896'ya indirdi. Aşağıdaki
590/1.339 ilk uçuş sayısı önceki sürüme aittir; yeni sonuç bağımsız saha testi değildir.

Tek bir TEXBAT profilini başka alıcıya taşımak yerine, alıcı kimliği ve
`static`/`moving` kullanım türüyle eşleşen ayrı profil kayıt sistemi eklendi.
Bilinen GRID kayıtları eski profili kullanmaya devam eder. Yeni bir alıcı için
normal kalibrasyon ve ayrı bir normal doğrulama oturumu gerekir; çalışma anındaki
şüpheli veriden otomatik öğrenme yapılmaz.

## Desteklenen kapsam

| Girdi/kullanım | Etkinleştirilebilen kontroller |
|---|---|
| Statik, konum + saat + C/N0 | Eski dört özellik, birikimli kanıt ve statik referans |
| Statik, yalnız konum | Konum penceresi ve toplam statik sürüklenme |
| Hareketli, saat ve/veya C/N0 | Mevcut saat/C/N0 özellikleri ve birikimli kanıt |
| Hareketli, yalnız konum/hız | Yeni profil oluşturulmaz; fiziksel kontroller sürer |

Saat özellikleri aynı kanıt grubu olarak kalır. Eksik C/N0 veya saat ölçümü
üretilmez. Hareketli kullanımda konum değişimi statik sapma sayılmaz ve sabit
konum referansı kurulmaz. Hareketli alıcının konum belirsizliği yörünge
yayılımından çıkarılmaz; yayımlanmış/ölçülmüş belirsizlik ayrıca verilmelidir.

Alıcı kimliği operatörün veri sözleşmesidir, RF üzerinden doğrulanmış kimlik
değildir. Profil yerel, güvenilen yapılandırmadır; üçüncü taraf JSON'un içindeki
“passed” sözcüğü bağımsız bir sertifika sayılmaz.

## Profil oluşturma

Normal kayıtlar standart CSV kullanır:

```text
timestamp_s,lat,lon,speed_kmh,cn0,receiver_clock_bias_m,receiver_clock_drift_m_s,receiver_id,receiver_motion,session_id
```

`cn0` ve saat sütunları mevcut değilse çıkarılır. `receiver_id` ve
`receiver_motion` her dosyada sabit olmalı; eğitim ve doğrulama aynı alıcı/kullanım
türüne ait, farklı `session_id` değerlerine sahip ayrı dosyalar olmalıdır.
İki dosyanın SHA-256 değerleri de farklı olmalıdır. İki oturumun gerçekte ayrı
ölçümler olduğunu veri sağlayan kişi doğrular; adını değiştirmek bağımsızlık sağlamaz.
En az 120 saniye kayıt ve yeterli geçerli örnek gerekir. Tanınan saldırı etiketi
taşıyan kayıt reddedilir. Etiket bulunmaması kendiliğinden temiz veri kanıtı değildir;
`--trusted-normal` operatörün normal kayıt beyanıdır.

```powershell
python calibrate_receiver.py --normal normal_oturum_a.csv --validation normal_oturum_b.csv --receiver-id alici-01 --profile-id alici-01-hareketli-v1 --motion moving --position-sigma-m 2 --warmup-s 10 --trusted-normal
```

Komut yalnız eğitim dosyasından merkez/sınır çıkarır; doğrulama dosyasına göre
sınırları yeniden ayarlamaz. Ayrı normal oturumda herhangi bir profil alarmı
veya yetersiz tam değerlendirme varsa aday kurulmaz. Başarılı dosya
`receiver_profiles/<profile-id>.json` olarak oluşturulur; mevcut profil üzerine
yazılmaz. Yalnız dışa aktarmak için `--output-dir <dizin>` kullanılabilir.

Bu kontrol **yalnız profil katmanının normal oturumdaki davranışıdır**; fiziksel
kuralların, navigasyon filtresinin ve saldırı yakalama başarısının saha doğrulaması
yerine geçmez. Kalibrasyon kayıtları saldırısızlığı doğrulanmış olmalı; kullanıcının
beyanının doğruluğu yazılım tarafından garanti edilemez.

## Çalışma sırasında seçim ve edinim

Yeni CSV'de `receiver_id` ve `receiver_motion` bildirilir. Tek bir uygun profil
varsa otomatik eşleşir. Birden fazla sürüm varsa sabit `receiver_profile_id` sütunu
ile seçim gerekir. Yanlış alıcı/kullanım, değişken kimlik sütunu veya bozuk profil
reddedilir; önceki yüklü kayıt korunur. Tanımlı kimlik için profil yoksa
`receiver-unvalidated` durumunda fiziksel kontroller çalışır; TEXBAT veya sentetik
RF/VAE profili yeni alıcıya sessizce uygulanmaz. Metadata içermeyen eski CSV'lerin
mevcut davranışı değiştirilmez. Bu ek yol CSV oynatımı içindir; canlı NMEA akışına
otomatik alıcı kimliği/kalibrasyonu eklenmiş değildir.

Isınma bütün alıcılarda zorla sıfırlanmaz. Yeni profilde edinim süresi 10–120 s
arasında seçilip ayrı normal oturumla kontrol edilir; varsayılan 30 s'dir.
10 s fark penceresi için geçmiş gözlem gerekir. Bununla birlikte anlık
`receiver_clock_drift_m_s` varsa güçlü sapma ilk örneklerden başlayarak süreklilik
kontrolüyle değerlendirilebilir. Yaklaşık 2 s onay ve en az üç örnek aranır;
bu alarm için 30 s beklenmez. Arayüz kalan edinim süresini, değerlendirilmiş
özellikleri ve eksik kapsamı gösterir. Fiziksel kurallar her zaman çalışır.

## Doğrulama ve kalan açıklar

171 test geçti. Eski bağımsız deneylerin hash/dondurma dosyaları korunur.

```powershell
python -m pytest -q
python validate_receiver_contracts.py
```

İki **sentetik** alıcı sözleşmesi gerçek CLI → profil kaydı → ortak CSV yükleyici
→ karar motoru → Streamlit arayüzü yolunda sınandı. Biri statik tam gözlemli,
diğeri hareketli ve yalnız C/N0'ludur. Profiller sonuç dizinine dışa aktarıldı;
gerçek donanım profili gibi ana kayıt dizinine kurulmadı. Ayrı normal oturumlar,
alıcı/kullanım uyuşmazlığı, belirsiz sürüm seçimi, eksik sensörler, başarısız aday,
üzerine yazma, bozuk JSON, başlangıç saldırısı ve durum sıfırlamaları test edildi.

Altı mevcut gerçek kaydın yeniden oynatımında karar sayıları önceki sürümle
aynıdır: cleanStatic 0/2.115, Zurich 0/13.531 alarm; CMU ilk uçuşta 590/1.339 alarm.
TEXBAT DS7'nin algılayıcı alarm kapsamı %33,31, gecikme 238,80 s olarak kaldı.
CMU navigasyon sorunu, geciken/kaçan saldırılar ve bağımsız referans eksikliği
bu profil altyapısı tarafından çözülmedi. **Yeni fiziksel alıcıda gerçek saha
doğrulaması henüz yoktur.** Eski bağımsız CMU raporu tarihsel dondurulmuş sürüme
aittir; dondurma/hash dosyaları güncel kodu onaylamak için değiştirilmedi.

Sonuçlar: [sentetik sözleşmeler ve arayüz](validation_results/receiver_profiles_20261023/synthetic_contracts/results.json),
[gerçek kayıt yeniden oynatımı](validation_results/receiver_profiles_20261023/replay/replay_results.json),
[TEXBAT zaman ölçümü](validation_results/receiver_profiles_20261023/texbat/results.json).
