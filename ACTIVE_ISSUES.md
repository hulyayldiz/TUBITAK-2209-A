# Aktif sorunlar — 27 Ekim 2026

## Algılama performansı

1. **DS7'nin ilk saniyelerinde saldırı kanıtı zayıf.** 1 s hızlı CMC penceresi,
   0,4 s onay ve alarm sürdürme kuralından sonra güncel replay kapsamı %98,49;
   1.789 saldırı örneğinin 27'si ilk alarmdan önce kaçıyor. İlk alarm onset'ten
   5,60 s sonra, çekme dönemi boyunca alarm kesilmeden sürüyor. Çok düşük hızlı
   CMC eşikleri temiz kayıtta yanlış alarm üretti; daha duyarlı profilin başka
   alıcıda yanlış alarm oranı bilinmiyor. DS3 örnek kapsamı
   %100 olsa da onset'te alarm önceden açık ve yeni alarm oluşmuyor; bu saldırı
   için yeni tespit süresi ölçülemiyor. [Güncel TEXBAT ölçümü](TEXBAT_CURRENT_VALIDATION.md).
2. **Jammertest saldırılarının çoğunda zamanında uyarı yok.** Fix-kaybı gözlemi
   korunduktan sonra 33 olayın 12'sinde yeni uyarı oluştu; yeni uyarıların ortanca
   gecikmesi 428,3 s. Bu 12 olayın tamamında fix-kaybı yolu görüldü; bu sinyal
   GNSS hizmet kaybını gösterir, tek başına jamming nedeni kanıtlamaz.
   Olay pencereleri dışında 10.349 epoch'un 195'inde alarm var; kaynak bu aralıkları
   doğrulanmış temiz saymadığı için yanlış alarm oranı bilinmiyor. [Jammertest
   raporu](JAMMERTEST_VALIDATION.md).

## Bağımsız doğrulama ve kapsam

3. **Bağımsız konum/yönelim referansıyla saldırı değerlendirmesi tamamlanmadı.**
   HK-UrbanSpoof S2/S3 için doğrulanmış NovAtel SPAN-CPT GNSS/INS izleri ve zaman
   eşleştirme adaptörü hazır. Ancak karşılık gelen alıcı NAV çıktısı yok; ham IF
   kayıtları henüz alıcıdan geçirilmedi. Koherent, hareketle uyumlu saptırmalar
   bağımsız uçuş sensörü olmadan gözlemlenemez kalabilir.
4. **Başka alıcıda doğrulanmış profil yok.** Jammertest alıcısının MON-RF alanları
   korunuyor; durum 0 olan 44.633 örnek “bilinmiyor/devre dışı”, yalnızca bir örnek
   durum 2 idi ve saldırı zamanıyla örtüşmedi. `jamInd` için alıcıya özel temiz
   kalibrasyon olmadığından alarm eşiği uygulanmıyor.
5. **Temiz veride yanlış alarm oranı bilinmiyor.** Jammertest'in saldırı dışındaki
   aralıkları sertifikalı temiz değil. Ayrıca yeni `GNSS_FIX_LOSS` uyarısının
   doğal kapsama kesintilerinde sıklığı, temiz şehir/tünel/kırsal alıcı izleriyle
   ölçülmedi.
6. **RF/VAE ve gerçek IHA performansı kanıtlanmadı.** Jammertest NAV-PVT akışında
   C/N0 yok; RF/VAE ölçümü yapılamadı. HK ham IF dosyaları (dosya başına yaklaşık
   10–13 GB) işlenmedi; kendi IHA/alıcı/IMU zincirinde etiketli sınama da yok.
7. **TEXBAT bağımsız ve kilitli holdout değil.** CMC sınırı cleanStatic kaydından
   kalibre edildi; hızlı pencere/onay parametreleri de DS7 davranışı incelenirken
   değiştirildi. DS2/DS3/DS7 bu nedenle keşifsel, aynı benchmark ailesinden
   geliştirme/değerlendirme kanıtıdır; yeni alıcıda başarı garantisi değildir.
   DS7'nin kalan kaçırmaları ve DS3'ün onset öncesi uyarısı yeni, önceden ayrılmış
   ve temiz veride ayrıca sınanmalı.
8. **Yeni alıcı holdout'u hazır değil.** FGI Jammertest 2025 kaydı Septentrio
   PolaRx5 SBF/RINEX ölçümleri ve yer gerçeği sunduğunu bildiriyor; uygun bir
   adaydır, fakat henüz dosya düzeyinde doğrulanmış test kaynağı değildir. 27 Ekim
   2026 tarihli Metax snapshot'ında CC BY 4.0, 102 dosya ve 874.580.271 bayt
   listeleniyor. Yalnızca 299 baytlık `ground_truth_static.csv` indirildi; SHA-256
   katalog özetiyle eşleşti. Bu dosya statik referans koordinatıdır, saldırı
   başlangıç/bitiş etiketi değildir. Saldırı senaryosu SBF/RINEX ve eşleşen olay
   etiketleri alınmadı; aynı gün dosya kullanılabilirlik uç noktası
   `Download is not enabled` yanıtı verdi. Katalog metadata'sındaki SHA-256'lar
   yerel payload hash'i değildir. Dosyalar, saat eşlemesi, etiket kapsamı ve test
   öncesi kod/eşik dondurması doğrulanmadan bağımsız test sonucu raporlanamaz.
   [Holdout protokolü](INDEPENDENT_HOLDOUT_PROTOCOL.md) ve
   [metadata manifesti](data_manifests/fgi_jammertest_2025.json). Kullanıcı,
   Mika Saajasto'ya 27 Ekim 2026'da veri erişimi ve olay etiketleri hakkında
   e-posta gönderdiğini bildirdi; yanıt ve erişim teyidi bekleniyor.

## Tamamlanan altyapı

- Jammertest 2024 arşivi MD5/SHA-256 ile doğrulandı; 24 senaryo CSV'si ve ayrı
  olay yan dosyaları üretildi, kaynak CEST / NAV UTC saat farkı düzeltildi.
- Fix geçerliliği kaybı veri adaptöründe korunuyor. Daha önce fix edinilmiş
  oturumda kesinti 3 s sürerse ayrı `GNSS_FIX_LOSS` uyarısı veriliyor; başlangıçta
  fix olmaması alarm sayılmıyor ve saldırı türü atfedilmiyor.
- HK-UrbanSpoof S2/S3 referans dosyaları commit, boyut ve özetlerle doğrulandı;
  parser/eşleştirme hazır. Kaynakta lisans bildirimi bulunmadığından dosyalar
  yerel doğrulama amacıyla tutuluyor.
- TEXBAT değerlendirme dondurma listesi artık CMC kodu ve kalibrasyon dosyasını
  da kapsıyor. Güncel replay ayrı dizine yazıldı; eski ölçümler korunuyor.
- Son tam doğrulama: `python -m pytest -q` — 197 geçti (23 Ekim 2026).

Önceki kanıtlar: [navigasyon düzeltmesi](NAVIGATION_FIX.md),
[CMU doğrulaması](INDEPENDENT_REAL_VALIDATION.md),
[yavaş sapma ölçümü](SLOW_ATTACK_FIX.md),
[alıcı profilleri](RECEIVER_PROFILES.md),
[hash kurtarma raporu](HASH_RECOVERY_REPORT.md).
