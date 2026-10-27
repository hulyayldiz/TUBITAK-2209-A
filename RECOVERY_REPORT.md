# Saldırı sonrası toparlanma düzeltmeleri — 23 Ekim 2026

Son ek düzeltme: sıçramanın yönü artık sonraki ölçümün araç yönü olarak taşınmıyor. **98 test geçti.** Son kaynaklarla yeni 100001–100005 tohumlarına ait [doğrulama raporu](validation_results/course_recovery_20261023/VALIDATION_REPORT.md) ve [ham JSON](validation_results/course_recovery_20261023/validation_results.json). Aşağıdaki 90001–90005 tablosu bu ek düzeltmeden önceki sürümdür.

## Neden bütün koşullarda sıfır garanti edilemiyor?

Bir alıcının saldırı sonrası gerçek konumuna dönmesi, ölçümlerde ani konum/yön değişimi olarak görünebilir. Benzer gözlem gerçek bir konum manipülasyonunda da üretilebilir. Bağımsız ve güvenilir bir mutlak konum referansı olmadan bu iki durumu her koşulda hatasız ayırma garantisi verilemez. Saldırı etiketi yalnız değerlendirmede kullanılır; kabul kararını etkilemez.

Bu çalışma korumayı veya alarm sayımını kapatmadan yazılım hatalarını giderir. Sonuç sıfır değilse raporda korunur.

## Yapılan düzeltmeler

1. **Pencere sınırı:** Büyük konum sıçraması ile yön sapması aynı anda olabiliyor. Fiziksel motor yön sapmasını önce raporlayınca eski kod VAE penceresini temizlemiyordu. Sayısal sıçrama artık bağımsız bir alan olarak bildirilir; mesaj önceliği ne olursa olsun VAE geçmişi ve RF doğrulama sayacı temizlenir. Yeni konum bölümü, önceki saldırının pencere geçmişiyle karıştırılmaz.
2. **Aralıklı normal kararın erken kabulü:** Bağımsız IMU kontrolü saldırı tespit ettikten sonra birkaç normal karar GPS'i yeniden kabul ettirebiliyor, tahmin ve sonraki referanslar saldırıdan etkilenebiliyordu. Doğrulanmış bağımsız IMU alarmından sonra son tutarsızlığın üzerinden monitörün 20 saniyelik penceresi kadar süre geçmesi beklenir. Bu süre içinde yeni bağımsız tutarsızlık beklemeyi yeniler; tek normal karar yeterli değildir. Bu, ilk saldırı tespitine yeni bir bekleme eklemez. Süreli alarm koruması sensör yokluğunda bağımsız doğrulama sağlandığı anlamına gelmez; sonrasında da mevcut filtre yenilik kapısı uygulanır.

Açık koordinat sıçraması yeni bir pencere başlatır. Bu durumda eski pencerenin beklemesi kaldırılır, fakat fiziksel karantina ve EKF yenilik kapısı aynen uygulanır; yeni koordinat otomatik kabul edilmez. Düşük C/N0 da devam eden bağımsız tutarsızlık beklemesini aşarak GPS'i filtreye veremez. Kaynak ve kayıt saati değişiminde yeni durum temizlenir.

Bu değişiklik kısa normal boşluklarda saldırı korumasının sürmesini sağlar; bağımsız IMU'nun yanlış alarm ürettiği sahalarda bekleme uzayabilir. Saha verisi olmadan bunun her araçta yanlış alarmı azaltacağı iddia edilmez.

## Kontrollü kalibrasyon karşılaştırması

101/202/303 tohumlarında aynı normal ve örtülü spoofing girdileri:

| Ölçüm | Önce | Sonra |
|---|---:|---:|
| Normal yanlış alarm | 0/3600 | 0/3600 |
| Örtülü spoofing saldırı dışı yanlış alarmlı örnek | 120/1260 | 33/1260 |
| Saldırı örneklerinde TP / FN | 2261 / 79 | 2268 / 72 |
| Örtülü spoofing navigasyon RMSE | 52,39 m | 43,79 m |

Ham veriler: `validation_results/recovery_before.json` ve `recovery_after.json`. Korunan alarm durumu hibrit metrikte sayılır; tespit oranındaki artış yeni bir model eğitimi sonucu değildir.

## Kontroller

- **96 test geçti.** Yön sapması tarafından maskelenen sıçrama, aralıklı normal karar, yeni tutarsızlıkla bekleme uzaması, koordinat sıfırlamasında fiziksel/yenilik kapısının korunması ve düşük sinyalle beklemenin aşılamaması sınandı.
- Kritik flake8 seçimi **0 hata**; `git diff --check` temiz.
- Streamlit AppTest açılışı geçti.
- Ayrı 90001–90005 değerlendirme tohumlarıyla beş senaryo, 25 koşu, 30.000 örnek. Model ağırlıkları ve RF/VAE eşikleri önceki çalışmayla aynı.

[Son rapor](validation_results/recovery_20261023/VALIDATION_REPORT.md), [ham JSON](validation_results/recovery_20261023/validation_results.json).

## Ayrı değerlendirme sonuçları

90001–90005 tohumlarında 30.000 örnek tamamlandı. Kaynak ve model SHA-256 değerleri ham raporla eşleşiyor. Aşağıdaki yanlış alarm oranı senaryonun saldırı dışı başlangıç ve toparlanma örneklerini birlikte kapsar.

| Senaryo | Tespit | Yanlış alarmlı / saldırı dışı örnek | Yanlış alarm |
|---|---:|---:|---:|
| Normal | — | **0/6000** | **%0 gözlendi** |
| Jamming | %100 | 31/2100 | %1,48 |
| Ani spoofing | %100 | 55/2100 | %2,62 |
| Yavaş spoofing | %99,97 | 55/2100 | %2,62 |
| Örtülü spoofing | %96,69 | 55/2100 | %2,62 |

20 saldırı olayının 20'sinde en az bir tespit var. Örtülü spoofing örneklerinde TP/FN 3771/129, ortalama ilk tespit 12,90 saniye; navigasyon RMSE 30,87 m. Ayrı tohumlar kullanıldığından önceki 80001–80005 oranlarıyla doğrudan kontrollü iyileşme yüzdesi hesaplanmaz; kontrollü karşılaştırma yukarıdaki kalibrasyon tablosudur.

**Bütün koşullarda sıfır sağlanmadı.** Saldırı sonrası gerçek konuma dönüş sıçraması ve yeniden kabul beklemesi hâlâ alarm oluşturuyor. Bu örnekler alarm hesabından çıkarılmadı; rapor etiketleri değiştirilmedi. Normal senaryodaki sıfır gözlem de gerçek sahaya veya sonsuz süreli çalışmaya garanti değildir.

## Ek düzeltme: sıçrama yönünün sonraki örneğe taşınması

Koordinat sıçramasının açısı aracın fiziksel hareket yönü değildir. Önceki kod bu açıyı `observed_heading` olarak sonraki örneğe taşıyor, sonraki normal hareketi ters yönde ikinci bir ani dönüş gibi değerlendirebiliyordu. Sıçrama tespitinde artık önceki hareket yönü korunur. Sıçramanın kendi yön farkı, ilk alarmı ve model girdisini korumak için o örnekte değiştirilmez. Sıçrama olmayan gerçek keskin dönüşler normal biçimde kontrol edilir.

Aynı 101/202/303 girdilerinde örtülü spoofing saldırı dışı yanlış alarm **33/1260 → 30/1260** (%2,62 → %2,38): yaklaşık **%9 ek azalma**. TP/FN **2268/72** olarak değişmedi; normal 3600 örnekte önce/sonra 0 yanlış alarm. Karşılaştırma `recovery_after.json` ile `course_recovery_after.json` arasındadır. Model ağırlıkları, karar eşikleri ve bekleme süreleri değiştirilmedi. İki yeni regresyon testiyle toplam **98 test geçti**; kritik flake8 seçimi ve `git diff --check` temiz.

Bu oran sonlu bir kalibrasyon karşılaştırmasıdır; bütün koşullar için ulaşılabilecek en küçük oran veya saha garantisi olarak yorumlanmamalıdır.

Buradaki yaklaşık %9 azalma alarm durumunda geçirilen örnek sayısı içindir; ayrı yanlış alarm olaylarının %9 azaldığı anlamına gelmez. İlk şüpheli sıçrama kontrolü korunurken aynı olayın sonraki örnekte yapay olarak yeniden tetiklenmesi önlenmiştir.

### Son ek düzeltmenin ayrı değerlendirmesi

100001–100005 tohumlarıyla 25 koşu / **30.000 örnek** tamamlandı. Kaynak ve model SHA-256 değerleri ham raporla eşleşiyor.

| Senaryo | Tespit | Saldırı dışı yanlış alarmlı örnek | Yanlış alarm oranı |
|---|---:|---:|---:|
| Normal | — | **0/6000** | **%0 gözlendi** |
| Jamming | %100 | 10/2100 | %0,48 |
| Ani spoofing | %100 | 50/2100 | %2,38 |
| Yavaş spoofing | %99,97 | 50/2100 | %2,38 |
| Örtülü spoofing | %97,36 | 50/2100 | %2,38 |

20 saldırı olayının 20'si en az bir kez tespit edildi; örtülü spoofing örneklerinde TP/FN **3797/103**. Örtülü spoofing navigasyon RMSE'si **38,52 m**; uzun GNSS reddindeki konum sapması çözülmüş değildir. Normal veride RMSE 0,18 m, jamming'de 2,17 m. Bunlar yeni tohumların ölçümleridir; önceki 90001–90005 tablosuyla doğrudan kontrollü iyileşme yüzdesi hesaplanmaz. Kontrollü karşılaştırma 101/202/303 tablosudur.

Bu düzeltme doğrulanmış bir ek azalma sağlar; matematiksel olarak en küçük hata oranına ulaşıldığı veya bütün saha koşullarında bu oranların korunacağı iddia edilmez.
