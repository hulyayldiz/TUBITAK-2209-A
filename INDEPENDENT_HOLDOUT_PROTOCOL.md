# Yeni alıcıda bağımsız holdout protokolü

**Durum:** Protokol hazır; FGI Jammertest 2025 dosyaları henüz indirilemedi.  
**Son kontrol:** 23 Ekim 2026.

## Aday veri ve erişim durumu

Fairdata Etsin'deki [FGI Jammertest 2025 GNSS interference dataset](https://etsin.fairdata.fi/dataset/095782a8-4e31-456e-8719-7021b4c96362)
Septentrio PolaRx5 alıcısından SBF/RINEX, ground-truth ve alıcı-durumu kayıtları
sağlıyor. Katalogda iki istenmeyen girişim, beş jamming, altı spoofing, iki
meaconing ve beş birleşik girişim senaryosu açıklanıyor. Veri CC BY 4.0 lisanslı,
102 dosya ve toplam 874.580.271 bayt olarak listeleniyor; katalog veri kümesinin
büyüyebileceğini belirtiyor. Deneyde kullanılan her dosyanın sürümü, boyutu,
SHA-256 özeti ve katalog gözlem zamanı sabitlenmelidir.

Metax dosya listesi anonim erişimle sorgulanabildi; ancak 23 Ekim 2026'da resmi
`/v3/download/available/<dataset-id>` uç noktası `Download is not enabled` yanıtı
verdi. Veri içeriği alınamadığı için henüz alıcı çıktıları çözümlenmedi ve hiçbir
performans sonucu üretilmedi. İndirme açılana veya yayıncı tarafından erişim yolu
sağlanana kadar bu kayıt yalnızca doğrulanacak holdout adayıdır.

## Test başlamadan önce dondurulacaklar

1. Algılayıcı kaynak kodu, modeller, alıcı profili, özellik şeması ve eşikler
   SHA-256 manifestiyle dondurulur. Dondurma manifesti test dosyaları açılmadan
   oluşturulur; sonuç görüldükten sonra güncellenerek aynı test yeniden
   "bağımsız" sayılmaz.
2. Etsin veri sürümü/gözlem tarihi, dosya yolları, her dosyanın boyutu ve özeti;
   olay takviminin kaynağı/sürümü ve saat dilimi birlikte kaydedilir. Veri kümesi
   büyüdüğünden test kapsamı tanımlanmış dosya listesiyle sınırlanır.
3. Olay etiketleri yalnızca algılayıcı kararları üretildikten sonra uygulanır.
   Saatler UTC'ye çevrilir; alıcı saatiyle olay takvimi arasındaki fark ve
   belirsizlik raporlanır. Belirsiz sınırlar için duyarlılık analizi ayrı verilir.
4. RINEX/SBF dönüştürmesi sürümlü, deterministik adaptörle yapılır. Ölçüm kaybı,
   epoch atlama, cycle slip ve alıcı resetleri raporlanır; olmayan C/N0, IMU veya
   bağımsız konum alanı türetilmez. RF/VAE, gerekli özellikler kaynakta yoksa
   sınanmış sayılmaz.

## Önceden tanımlı sonuçlar

- **Saldırı olayları:** olay düzeyinde en az bir yeni alarm oranı ve kaçırılan
  olay sayısı/türü. Alarm zaten açık olan olay yeni tespit sayılmaz.
- **Gecikme:** her olay için ilk yeni alarmın olay başlangıcından itibaren süresi;
  tespit edilmeyen olaylar sansürlü/kaçırılmış olarak ayrıca gösterilir. Ortalama
  tek başına verilmez; medyan, aralık ve olay bazlı değerler de raporlanır.
- **Temiz işletim:** yalnızca yayıncı tarafından açıkça temiz/nominal olarak
  işaretlenmiş süre kullanılır. Yanlış alarm örnek yüzdesi yanında olaylaştırılmış
  yanlış alarm / alıcı-saati verilir. Saldırı dışı fakat temizliği bilinmeyen
  zamanlar yanlış alarm paydasına katılmaz.
- **Alan aktarımı:** yeni Septentrio alıcı sonucu, mevcut TEXBAT/CMU sonuçlarıyla
  birleştirilmez; yeni alıcıdaki alan aktarımı olarak ayrı raporlanır. Olay ve
  kayıt düzeyindeki belirsizlik, bağımsız kümeler korunarak hesaplanır.

Bu yaklaşım alıcı ölçüm modelini kalibre etme ve hedef yanlış alarm oranını
önceden tanımlama gereğini izler; projede bu koşullar sağlanmadığı sürece FAR
garantisi iddia edilmez [1]. Farklı veri kümeleri arasındaki başarım kaybı
nedeniyle yeni alıcı sonucu ayrıca sunulur [2].

## Kaynaklar

1. F. Rothmaier et al., “GNSS Spoofing Detection through Metric Combinations:
   Calibration and Application of a General Framework,” ION GNSS+ 2021.
   [Yayın ve özet](https://www.ion.org/publications/abstract.cfm?articleID=18126).
2. N. Khan et al., “GNSS-Spoofing Detection via Machine Learning With In-Domain
   and Cross-Domain Testing and Open-Access I/Q Data,” IEEE Access, 2026.
   [Yayın ve özet](https://ieeexplore.ieee.org/abstract/document/11517370).

