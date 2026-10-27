# Gerçek kayıtlardaki alarm düzeltmesi — 23 Ekim 2026

**En son navigasyon düzeltmesi:** CMU'nun aynı 209 kaydı güncel sürümde
0/257.896 alarm ve bütün GNSS ölçümlerinin kullanılmasıyla tamamlandı.
[Güncel kanıt](NAVIGATION_FIX.md); aşağıdaki başarısız bağımsız test tarihsel
sürüme aittir ve korunur. Yeni sonuç bağımsız saha testi değildir.

**Yeni izleme katmanı:** [Kalıcı küçük sapma kontrolü](SLOW_ATTACK_FIX.md), aşağıdaki
kısa pencere politikasına zaman içinde biriken kanıt ve statik konum referansı ekler.
Yeni gerçek/sentetik ölçümler ayrı raporlanır; eski sayılar tarihsel sürüme aittir.

**Sonraki bağımsız test başarısız:** [209 yeni CMU kaydında](INDEPENDENT_REAL_VALIDATION.md)
nominal örnek alarm oranı %48,98 oldu. Aşağıdaki sıfır alarm sonuçları geliştirmede
kullanılan kayıtlara aittir. [Zaman etiketli TEXBAT ölçümü](TEXBAT_TIMING_VALIDATION.md)
DS3/DS7'de yüksek kaçırma gösterir. Bu düzeltmeler genel saha güvenilirliği sağlamaz.

Bu değişiklik iki farklı hatayı giderir: Zurich kaydında GPS güncelleme
zamanı/ölçüm belirsizliği hatası ve statik TEXBAT alıcısına hareketli sentetik
model uygulanması. Genel fiziksel eşikler yükseltilmedi; RF/VAE model
dosyaları yeniden eğitilmedi veya değiştirilmedi.

## Kanıtlanan nedenler

1. **Görüntü satırı GPS güncellemesi sanılıyordu.** Zurich'in 81.169 GPS
   satırı görüntü saatine hizalıdır; aynı alıcı çözümü yaklaşık altı görüntü
   boyunca tutulur. Tüm satırlar ayrı çözüm sayılınca bir hız değişimi
   yaklaşık 0,2 saniye yerine 0,02–0,03 saniyeye bölünüyordu. Altı küçük
   saat sırası ihlalinde aralık 0,000284 saniyeye kadar inmişti. Başlangıç
   teşhisinde 318 taze ivme alarmı, 1.590 tutma örneği görüldü.
2. **Ölçüm belirsizliği kullanılmıyordu.** Hız/konum hata tahminleri dosyada
   mevcutken filtre yaklaşık 0,5 m konum standart sapması varsayıyordu.
   Ölçüm reddi, karantina ve tahmin sapması 1.908 kural alarmını 45.504
   navigasyon alarmı örneğine büyütüyordu.
3. **Modelin gözlem alanı farklıydı.** Temiz TEXBAT'ta fiziksel kural alarmı
   sıfırdı; RF 2.108, VAE 2.096 örnekte tetiklenmişti. Sentetik NORMAL
   eğitimindeki C/N0 yaklaşık 44–46 dB-Hz; temiz gerçek kayıt yaklaşık
   45,95–47,16 dB-Hz. Sentetik model hareketli aracın ivme/yön/artıklarını
   öğrenmişti. Statik alıcıdaki sıfır hız ve ölçüm gürültüsünden hesaplanan
   yön, aynı fiziksel özellik dağılımı değildi. Birimlerin eşleşmesi yeterli
   olmadı.

Teşhis: `validation_results/real_alarm_fix_20261023/baseline_diagnostics.json`.
Sayılar örnek sayısıdır, bağımsız olay sayısı değildir.

## Yapılan düzeltme

**Zurich:** Özdeş GPS yükleri özgün edinim sırası içinde birleştirilir;
ardından gerçek zaman damgaları sıralanır. Sıralamayı önce yapmak eski/yeni
çözümleri karıştırıp sahte çok kısa aralık üretebiliyordu. Kaynak ZIP
değiştirilmedi; 67.638 tutulmuş tekrar ayrılarak 13.531 güncelleme oynatılır.

`s_variance_m_s` ve `eph_m` kaynağın hız/konum hata tahminleri olarak alınır.
İvme kontrolünde hız farkının üç birleşik standart sapmayı aşan alt sınırı
kullanılır; mevcut 2g sınırı değiştirilmez. Konum hata tahmini filtre
ölçüm kovaryansına aktarılır; yapılandırılmış gürültü tabanından daha küçük
gürültü kabul edilmez. Bunlar bağımsız doğruluk referansı değildir.
Geçersiz belirsizlik bilgisi alarmı susturamaz. Büyük sıçramalar ve gerçek
yüksek ivme hâlâ reddedilir. Kaynak değişiminde bu bilgiler temizlenir.

**TEXBAT:** Bilinen statik GRID kayıtları sentetik hareketli araç RF/VAE
modeline gönderilmez. Bunun yerine `receiver_profile.py`, gerçek gözlem
alanına özel normal kalibrasyon kullanır. Bu sadece modelleri kapatmak
değildir: konum değişim hızı, 10 saniyelik alıcı saat kayması değişimi,
C/N0 değişimi ve alıcının bildirdiği saat kayma hızı izlenir.

Kalibrasyon verisi yalnız `cleanStatic` dosyasıdır. Gözlem sınırları
30–120. saniyelerdeki 450 normal örnekten, konum kovaryansı ilk 120 saniyeden
hesaplanır. Sabit politika normal en büyük sapmasının 1,5 katını ve açık
çözünürlük tabanlarını kullanır. Anten konumu sigma tahmini yaklaşık 2,156 m.
Saldırı etiketleri veya dosya adı sınıflandırıcı girdisi değildir.

Saatin iki göstergesi tek kanıt grubu sayılır. Tek küçük sapma **advisory**
olarak kaydedilir. İki ölçüm grubunda sapma veya bir grupta kalibre sınırın
üç katı güçlü sapma en az üç örnek ve iki saniye sürerse **alıcı tutarsızlığı
anomalisi** oluşur. Bu bir saldırı kimliği kanıtı veya kalibre olasılık değildir.
İlk 30 saniye profil ısınmasıdır; fiziksel kurallar bu sırada çalışır.
Kalibrasyon/ölçüm yoksa durum açıkça `unavailable` gösterilir.

Profil `models/texbat_grid_profile.json` içinde, normal kaynak hash'leri ve
parametreleriyle tutulur. `python receiver_profile.py` aynı normal bölümden
yeniden üretir. Bu profil genel İHA uçuşuna veya başka alıcıya uygulanmaz.

## Güncel tam oynatma

| Kayıt | Önce alarm örneği / oynatılan örnek | Sonra alarm örneği / GPS güncellemesi |
|---|---:|---:|
| Zurich | 45.504 / 81.169 | **0 / 13.531** |
| cleanStatic | 2.115 / 2.115 | **0 / 2.115** |
| DS2 | 2.100 / 2.100 | 1.062 / 2.100 |
| DS3 | 711 / 2.096 | 151 / 2.096 |
| DS7 | 2.072 / 2.175 | 146 / 2.175 |

Zurich paydaları farklıdır; yeni örnekler gerçek GPS güncelleme yüklerini
temsil eder. Ham satırlar silinmedi. Toplam 89.655 ham satırdan 22.017
oynatılan gözlem vardır. cleanStatic'in 151 örneği profil ısınmasıdır;
kalan 1.964 örnekte 1.927 normal profil durumu ve 37 küçük sapma uyarısı
vardır. Uyarılar gizlenmedi, doğrulanmış saldırı diye etiketlenmedi.

DS2/DS3/DS7'de alarm sürer. Ancak bu sayılar gerçek saldırı sayısı, recall
veya TTD değildir: başlangıç/bitiş çizelgeleri bu çalışmada doğrulanmadı.
Alarm azalması tek başına duyarlılığın korunduğunu kanıtlamaz. Kontrollü
testler güçlü saat çekmesinin, koordinat sürüklenmesi + RF değişiminin,
kritik jamming'in ve büyük fiziksel ihlallerin hâlâ alarm verdiğini doğrular.

**Bu kayıtlar geliştirmede kullanılmıştır.** İlk normal kalibrasyon ayrı
zaman bölümündendir; devam kaydındaki küçük bir saat sapması da kanıt
birleştirme politikasının geliştirilmesinde incelenmiştir. Bu nedenle kalan
kısmı hiç görülmemiş bağımsız holdout diye sunmuyoruz. Başka uçuş/alıcıda
sıfır yanlış alarm garantisi yoktur. Çok küçük ve tek ölçüm grubundaki
saldırılar uyarı seviyesinde kalabilir; bağımsız sensörler hâlâ önemlidir.

## Doğrulama

- **133 pytest testi geçti.** GPS tekrarları, saat sırası, hata tahminleri,
  büyük saldırının korunması, profil ısınması, bozuk/eksik profil ve kaynak
  değişimi için yeni regresyon kontrolleri eklendi.
- Beş kaydın tamamı güncel adaptör ve karar motorundan geçirildi; son
  navigasyon konumları sonlu, etiketsiz başarı ölçümleri kapalı kaldı.
- Streamlit AppTest beş kaydı yükleyip oynattı; simülasyona dönüşte alıcı
  profili ve belirsizlik bilgilerinin temizlendiği kontrol edildi.
- Sentetik model dosyaları korunur. Önceki 25 koşulun sayısal regresyonu
  `synthetic_regression.json` dosyasında ayrıca kaydedilir: 30.000 örnekte
  katmanların TP/FP/TN/FN, gecikme olayları ve evre alarm sayıları önceki
  sürümle aynıdır; uyuşmayan koşul yoktur.

Çıktılar `validation_results/real_alarm_fix_20261023/` altında:
`replay_results.json`, `ui_results.json`, `baseline_diagnostics.json` ve
`synthetic_regression.json`. Güncel kod/model hash'leri rapora yazılır.
Tekrar çalıştırma: `python validate_real_data.py`.
