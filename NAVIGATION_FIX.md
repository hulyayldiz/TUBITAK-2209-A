# IMU'suz navigasyonda yanlış alarm düzeltmesi — 23 Ekim 2026

**209 CMU kaydının tamamı yeniden oynatıldı: 257.896 örnekte alarm yok.**
Eski bağımsız değerlendirmede aynı veride 126.321 örnek (%48,98) alarm üretmişti.
Yeni koşuda bütün 257.896 GNSS ölçümü gerçekten filtre tarafından kullanıldı;
reddedilen ölçüm veya alarm yeniden etiketlenerek gizlenmedi.

Bu sonuç artık bilinen geliştirme verisinin regresyonudur. Önceki bağımsız
deneyin başarısız raporu ve dondurma dosyası korunur; yeni sonuç bağımsız saha
başarısı veya bütün uçuşlarda sıfır yanlış alarm garantisi değildir.

## Neden ve değişiklik

Filtre, bağımsız navigasyon IMU'su yokken ivme girdisi olarak sıfır alıyordu.
Buna rağmen ivme ölçülmüş gibi küçük süreç gürültüsü (`0,05 m²/s⁴`) kullanılıyordu.
Sabit hız tahmini normal dönüş/ivmelenmeyi izleyemediğinde gerçek GNSS ölçümü
yenilik kapısından reddediliyor, 5 s karantina bu uyumsuzluğu büyütüyordu.

Eksik ivme ölçümü, bilinen sıfır ivme sayılmıyor. Mevcut fiziksel hareket
sınırı `a = (ivme ayarı / 20) × 9,81` kullanılarak bilinmeyen ivme için
`max(mevcut varyans, a²/3)` süreç varyansı uygulanıyor. `a²/3`, bir bileşenin
`[-a,a]` aralığında düzgün dağıldığı mühendislik varsayımıdır; alıcıdan öğrenilmiş
veya istatistiksel olarak doğrulanmış olasılık değildir. Varsayılan 40 ayarında
sınır 2 g, varyans yaklaşık 128,31 m²/s⁴ olur. Mevcut zaman/konum birimi dönüşümü
korunur. Sınır GNSS yeniliğinden veya saldırı etiketinden çıkarılmaz.

Bağımsız navigasyon IMU'su veya geçerli statik alıcı sözleşmesi varsa eski
süreç varyansı korunur. GPS destekli yönelim, bağımsız IMU gibi kullanılmaz.
IMU'suz ölçüm reddinde çıktı `MOTION_PREDICTION` olarak tanımlanır; bağımsız
ataletsel çözüm olduğu iddia edilmez.

Fiziksel eşikler, RF/VAE modelleri, alıcı profil sınırları, NIS kapısının
`-2 ln(0,001)` sayısal eşiği ve saldırı karantinası değiştirilmedi. **Tahmin
kovaryansı arttığında kapının kabul ettiği fiziksel bölge de genişler.** Bu,
normal manevraları kapsayan model düzeltmesidir; saldırı duyarlılığının her
koşulda aynı kaldığının kanıtı değildir. Reddedilen bir ölçümü kabul ettirmek
için yeniliğe bakarak tekrar tekrar kovaryans büyütülmez.

## Ölçülen sonuçlar

| Kontrol | Sonuç |
|---|---:|
| CMU kayıtları | 209 / 209; kaynak hash'leri eski testle aynı |
| Toplam nominal örnek | 257.896 |
| Eski alarmlı örnek | 126.321 (%48,98) |
| Yeni alarmlı örnek | **0** |
| Gerçekten kullanılan GNSS ölçümü | **257.896** |
| Normal kararda kullanılmayan GNSS ölçümü | **0** |
| CMU ilk uçuş | Eski 590 / 1.339; yeni 0 / 1.339 alarm |
| Sonuç üretirken değişen kod/model | Yok; koşu öncesi/sonrası hash kontrolü |

Veriler nominal enerji uçuşlarıdır; üretici saldırı etiketi sağlamaz. Alarm
oranı nominal işletim varsayımı altındadır. GNSS/INS çıktısı zaten birleşiktir;
filtre ile ölçüm arasındaki fark bağımsız gerçek konum hatası veya RMSE değildir.
RF/VAE bu C/N0'suz şemada değerlendirilmiş sayılmaz.

TEXBAT zaman değerlendirmesi de yeniden çalıştırıldı ve önceki son sürümle
aynı kaldı: DS2 algılayıcı alarm kapsamı %99,36; DS3 %98,27; DS7 %33,31.
DS3'te enjeksiyon öncesi başlayan alarm ayrımı korunur; bu oran saldırı kimliğini
kanıtlamaz. DS7 gecikmesi 238,80 s ve kaçırma %66,69 olarak devam ediyor.
Temiz TEXBAT kaydında 2.115 örnekte alarm yok. Zurich'in 13.531 GPS
güncellemesindeki ilk yeniden oynatımda da alarm yok.

177 birim/regresyon testi geçti. Ek testler normal dairesel manevranın tüm
ölçümlerini kullanarak izlenmesini, 20 m sıçramanın reddini, karantinanın devamını,
bağımsız IMU/statik profilde eski varyansın korunmasını ve geçersiz varyansın
filtreyi bozmamasını doğrular. Aynı modellerle 15 sentetik güvenlik koşusunun
eski/yeni karşılaştırması ayrı sonuç dosyasındadır; bu da gerçek saha kanıtı değildir.
CMU ve DS7 uygulamada açılarak hata/ölçüm kullanımı ve profil varyansı kontrol edildi.

```powershell
python -m pytest -q
python validate_navigation_real.py
python validate_navigation_attacks.py
```

[Tam CMU regresyonu](validation_results/navigation_fix_20261023/cmu_regression.json),
[sentetik önce/sonra](validation_results/navigation_fix_20261023/synthetic_security_comparison.json),
[TEXBAT zaman skorları](validation_results/navigation_fix_20261023/texbat/results.json).
Bağımsız yeni alıcı/uçuş testi, gerçek saldırıdaki gecikme ve bağımsız
IMU/yönelim ihtiyacı hâlâ [aktif sorunlar](ACTIVE_ISSUES.md) arasındadır.
