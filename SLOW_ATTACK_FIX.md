# Kalıcı küçük sapmaların izlenmesi — 23 Ekim 2026

**Güncellik notu:** Bu rapordaki TEXBAT %33,31 / DS7 gecikme 238,80 s sonuçları
CMC code-carrier yolu eklenmeden önceki sürüme aittir. Güncel kodla tekrar oynatım
[ayrı raporda](TEXBAT_CURRENT_VALIDATION.md) bulunur.

Statik GRID alıcı profilindeki kısa pencere kararına iki ek kontrol eklendi.
Tek ölçüm grubundaki zayıf ama sürekli sapma artık süresiz uyarıda kalmıyor.
Modeller, kalibrasyon dosyası ve mevcut güçlü/çoklu grup kuralları değiştirilmedi.

## Eklenen kontroller

1. **Zaman içinde biriken tek-grup kanıtı:** Kalibrasyon merkezi ve sınırlarıyla
   ölçeklenen işaretli sapmalar için iki yönlü, sınırlı CUSUM kullanılır.
   En az 10 saniye aralıklı, çakışmayan gözlem pencereleri sayılır. Her pencerenin
   katkısı en çok 1, toplam eşik 6'dır; tek sıçrama birikimi dolduramaz.
   Normal gözlem birikimi azaltır. İki saat özelliği tek ölçüm grubu olarak kalır;
   karşıt yönlü dalgalanmalar aynı yönde kanıt diye toplanmaz.
2. **Toplam statik konum sürüklenmesi:** İlk 30 saniye sonunda son pencerenin
   medyanından bir konum referansı sabitlenir. Referans canlı konumu takip ederek
   saldırıya uyarlanmaz. Yer değiştirme `max(6 × konum sigma, 3 × hız sınırı × 10 s)`
   sınırını 30 saniye boyunca aşarsa alıcı tutarsızlığı alarmı oluşur.
   Mevcut profilde sınır yaklaşık 12,94 m'dir. Bu kontrol yalnız önceden tanımlı
   **statik** alıcı profilinde çalışır; uçan araca sabit konum varsayılmaz.

Geçersiz gözlem, geriye giden saat, yeni kayıt veya 10 saniyeyi aşan veri boşluğu
kanıtı/referansı sıfırlar ve yeniden ısınma gerektirir. Veri boşluğu devamlılık
kanıtı sayılmaz. Alarmlar mevcut karar/navigasyon zincirine gerçek yeni kanıt
olarak girer; yalnız ekrana yazılan bir uyarı değildir.

CUSUM'un küçük süreç değişimleri için kullanımı
[NIST açıklamasına](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm)
dayanır. Buradaki ölçekler standart sapma değil mühendislik sınırlarıdır;
eşik 6, kalibre edilmiş yanlış alarm olasılığı veya istatistiksel güven düzeyi değildir.

## Önce/sonra kontrolü

Eski kodun SHA-256'sı önceki TEXBAT raporuyla eşleştirildi ve bir kopyası
yeni sonuç dizininde saklandı. Aynı sentetik girdiler eski ve yeni koddan
geçirildi; gerçek saldırı etiketleri çıkarıma verilmedi.

| Kontrollü sentetik değişim | Eski kod | Yeni kod, başlangıçtan gecikme |
|---|---:|---:|
| 5 cm/s tek konum sürüklenmesi, 3 tohum | 0/3 | 3/3; 291,5–295,5 s |
| 10 cm/s sürüklenme, 3 tohum | 0/3 | 3/3; 160–161,5 s |
| 15 cm/s sürüklenme, 3 tohum | 0/3 | 3/3; 116,5–118 s |
| Tek saat özelliğinde sınırın 1,2 katı sapma | 0/3 | 3/3; 290 s |
| Tek saat özelliğinde ±1,5 kat sapma | 0/6 | 6/6; 110 s |

Normal gürültü, sınırlı konum salınımı ve kısa saat sapması içeren 9 kontrol
koşusunda iki sürümde de alarm yoktur (7.560 örnek). Bunlar **sentetik regresyon
ölçümleridir**, bağımsız gerçek saldırı başarısı değildir. Normal gözleme dönüş,
tek büyük sıçrama, örnekleme hızı, saat sıfırlaması, veri boşluğu, çakışan pencere
ve bilinmeyen hareketli kayıt da test edilir.

## Gerçek kayıt yeniden oynatımı

Algılayıcının navigasyon öncesi, örnek bazlı alarm/tutarsızlık oranı:

| Kayıt | Önce | Sonra | RF enjeksiyonundan sonraki ilk yeni alarm |
|---|---:|---:|---:|
| DS2 | %55,64 | %99,36 | 2,30 s |
| DS3 | %4,52 | %98,27 | 54,91 s |
| DS7 | %6,76 | %33,31 | 238,80 s; önce 296,60 s |

**DS3'te yeni kontrol kayıt saati 118,00 s'de, birincil RF enjeksiyonu
119,69 s'den önce alarm verir.** Bu zaman yayımlanan aktivasyon/enjeksiyon
belirsizliği aralığındadır ve asıl protokolde skor dışıdır. Enjeksiyon başlangıcında
alarm zaten aktiftir; bu alarm sıfır gecikmeli yeni saldırı tespiti sayılmadı.
Dolayısıyla %98,27 saldırı kimliğinin kanıtı veya erken RF tespit başarısı değildir.
AFIT'in bildirdiği donanım yan etkisi ve statik referans varsayımı sonuçları
etkileyebilir. Ham zaman izleri ve alternatif DS7 zamanları saklandı.

cleanStatic 2.115 örnekte, Zurich 13.531 GPS güncellemesinde alarm yoktur.
Bu kayıtlar geliştirmede kullanıldı; bağımsız test değildir. CMU'nun ilk uçuşu
590/1.339 örnekte alarm üretmeye devam eder; bu ayrı navigasyon sorunu çözülmedi.
209 kayıtlık eski CMU raporu tarihsel sürüme aittir. Eski dondurma değiştirilmedi;
eski bağımsız değerlendirici yeni sürümde hash farkını görerek durur. Bu değişiklik
CMU profilinde çalışmasa da yeni sürüm için yeni bir bağımsız başarı iddiası yoktur.

## Kalan sınırlar ve doğrulama

Bağımsız IMU/yönelim, güvenilir konum veya farklı bir alıcı kaynağı olmadan,
gerçek hareketle tamamen tutarlı ve gözlemlenebilir fark üretmeyen bir GNSS
saptırması yazılımla kesin ayırt edilemez. Statik referans gerçek konum değildir;
başlangıçta kirlenmiş kayıt güvenilir başlangıç sağlayamaz. Mevcut alıcı dışındaki
verilerde bu kontrol doğrulanmış sayılmaz. DS7'nin örneklerinin %66,69'u hâlâ
alarm dışındadır ve gecikme yüksektir. Çok küçük/kısa sapmalar yine kaçabilir.

**154 test geçti.** Tam oynatım 6 hazır kaydı kapsar; modeller yeniden eğitilmedi.

```powershell
python -m pytest -q
python validate_slow_receiver.py
```

Çıktılar: [sentetik karşılaştırma](validation_results/slow_attack_20261023/synthetic_comparison.json),
[TEXBAT zaman skorları](validation_results/slow_attack_20261023/texbat/results.json),
[altı kaynak oynatımı](validation_results/slow_attack_20261023/replay/replay_results.json).
Önceki sonuç dosyaları üzerine yazılmadı.
