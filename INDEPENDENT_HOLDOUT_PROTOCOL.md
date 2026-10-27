# Yeni alıcıda bağımsız holdout protokolü

**Durum:** FGI Jammertest 2025 uygun bir adaydır; saldırı kayıtları ve olay etiketleri henüz edinilmediği için bağımsız test başlamamıştır.
**Metax metadata snapshot'ı:** 27 Ekim 2026. **Dosya indirme kontrolü:** 27 Ekim 2026.

## Aday veri ve erişim durumu

[FGI Jammertest 2025 GNSS interference dataset](https://etsin.fairdata.fi/dataset/095782a8-4e31-456e-8719-7021b4c96362)
kataloğu Septentrio PolaRx5 ölçümlerini, SBF/RINEX biçimlerini, alıcı durum
kayıtlarını ve yer gerçeğini bildiriyor. Senaryo özeti iki istenmeyen girişim,
beş jamming, altı spoofing, iki meaconing ve beş çoklu girişim senaryosunu listeliyor.
Katalog erişimi Open ve lisansı CC BY 4.0 olarak gösteriyor.

27 Ekim 2026 Metax dosya metadata'sı 102 kayıt ve toplam 874.580.271 bayt
(yaklaşık 834,06 MiB) içeriyor: 20 SBF, 20 RINEX gözlem (`.25O`), 20 RINEX
navigasyon (`.25P`), 20 RTCM3, 20 JSON senaryo metadata dosyası, bir log ve bir
statik referans CSV'si. Kayıt yolları, boyutlar ve yayıncı SHA-256 değerleri
[`data_manifests/fgi_jammertest_2025.json`](data_manifests/fgi_jammertest_2025.json)
dosyasında saklıdır; metadata manifesti veri payload'larının indirildiğini veya
yerel hash'lerinin doğrulandığını göstermez.

Yalnızca `/Static/ground_truth_static.csv` (299 bayt) indirildi ve SHA-256 özeti
katalogdaki değerle eşleşti. Bu dosya statik referans koordinatları içerir; saldırı
başlangıç/bitiş zaman etiketleri değildir. Senaryo SBF/RINEX, JSON metadata ve
olay zaman çizelgeleri henüz yerelde incelenmedi. 27 Ekim 2026'da Metax dosya
kullanılabilirlik uç noktası `405: Download is not enabled` yanıtı verdi. Bu nedenle
katalogdaki açık erişim etiketi, dosyaların fiilen indirilebilir olduğu anlamına
gelmiyor. Erişim sorusu gönderilmedi; başvuru sahibi/veri sorumlusu bu konuyu
doğrudan netleştirmelidir.

Uygulama şu anda CSV/MAT/NMEA benzeri ortak şemaya çevrilmiş navigasyon kayıtlarını
oynatır; SBF veya RINEX için hazır bir alıcı adaptörü yoktur. Bu biçimler için
deterministik dönüştürücü, alan eşlemesi, zaman sistemi ve olay etiketleri doğrulanmadan
prototipin bu veride çalıştığı iddia edilmemelidir. Ham IQ verisi bu veri kümesinde
hedeflenmiyor; bu çalışma SBF/RINEX alıcı ölçümleriyle sınırlıdır.

## Veri erişim kapısı

Performans ölçümüne başlamadan önce aşağıdakilerin tümü sağlanmalıdır:

1. En az bir jamming veya spoofing senaryosunun SBF ya da RINEX ölçüm dosyası
   ve ona eşleşen kaynak olay zaman çizelgesi indirilebilmeli.
2. Alıcı ölçüm zamanı ile olay çizelgesinin zaman referansı, zaman dilimi ve
   senaryo başlangıç/bitiş tanımları kaynak belgeleriyle açıklanmalı.
3. Senaryo JSON dosyası, varsa temiz/normal zaman aralığı tanımı da dahil edilerek
   incelenmeli. Saldırı dışı süreler otomatik olarak temiz kabul edilmemeli.
4. Gerekli GNSS alanları (zaman, fix/geçerlilik, konum/hız veya ölçüm düzeyi
   özellikler) ve dönüştürücü uyumluluğu tek kayıt üzerinde doğrulanmalı.
5. İndirilen her payload'ın boyutu ve SHA-256 özeti katalog metadata'sıyla
   karşılaştırılmalı; lisans ve veri sürümü kaydedilmeli.

Kapı geçilemezse bu veri kümesinde performans testi başlatılmaz. Başvuru kapsamı,
danışmanla birlikte fiilen erişimi ve gerekli zaman etiketleri doğrulanmış başka bir
kaynağa göre değiştirilir. Salt metadata veya koordinat dosyası bağımsız test için
yeterli değildir.

## Test başlamadan önce dondurulacaklar

1. Algılayıcı kodu, modeller, alıcı profili, özellik şeması, dönüştürücü sürümü,
   eşikler ve yapılandırma SHA-256 manifestiyle dondurulur. Dondurma, test
   senaryolarının ölçüm içeriği açılmadan yapılır.
2. Katalog snapshot'ı, testte kullanılacak dosya yolları, payload boyut/hash'leri,
   olay çizelgesinin kaynağı/sürümü ve zaman sistemi birlikte kaydedilir.
3. Birincil analiz mevcut algılayıcı ve eşiklerle sıfır-atış aktarım testidir.
   Jammertest 2025 test kayıtlarında eşik, model veya profil ayarı yapılmaz.
   Olay etiketleri algılayıcı kararları üretildikten sonra uygulanır.
4. SBF/RINEX dönüştürmesi deterministik olmalı; epoch atlama, eksik değer, geçersiz
   fix, saat kayması, cycle slip ve alıcı resetleri raporlanmalıdır. Kaynakta olmayan
   C/N0, pseudorange, taşıyıcı fazı, IMU veya temiz etiketi türetilmez.

## Önceden tanımlı sonuçlar

- **Saldırı olayları:** jamming ve spoofing ayrı raporlanır. Olay başına en az bir
  yeni alarm oranı, kaçırılan olay sayısı ve olay tipi verilir. Saldırı başlangıcında
  zaten açık olan alarm yeni tespit sayılmaz.
- **Gecikme:** olay başlangıcından ilk yeni alarma kadar süre raporlanır. Kaçırılan
  olaylar ayrıca gösterilir; medyan, aralık ve olay bazlı değerler verilir.
- **Yanlış alarm:** yalnızca yayıncı tarafından açıkça temiz/normal diye etiketlenmiş
  zaman aralığında hesaplanır. Olaylaştırılmış yanlış alarm/alıcı-saati raporlanır.
  Saldırı dışı fakat temizliği bilinmeyen zamanlar paydada kullanılmaz.
- **Alan aktarımı:** PolaRx5 sonucu TEXBAT, CMU veya geliştirme verileriyle
  birleştirilmez; ayrı bir dış alıcı/veri kaynağı sonucu olarak sunulur. Dosya ve
  olay kümeleri bağımsızlık varsayımı korunarak raporlanır.

Bu yaklaşım alıcı ölçüm modelini kalibre etme ve hedef yanlış alarm oranını
önceden tanımlama gereğini izler; koşullar sağlanmadığı sürece FAR garantisi
iddia edilmez [1]. Veri kümeleri arasındaki dağılım kayması ayrıca raporlanır [2].

## Metadata manifestini yenileme

```powershell
python scripts/fetch_fgi_catalogue_manifest.py
```

Bu komut yalnızca Fairdata Metax dosya metadata'sını alır; senaryo verilerini
indirmez ve yerel payload hash doğrulaması yapmaz.

## Kaynaklar

1. F. Rothmaier et al., “GNSS Spoofing Detection through Metric Combinations:
   Calibration and Application of a General Framework,” ION GNSS+ 2021.
   [Yayın ve özet](https://www.ion.org/publications/abstract.cfm?articleID=18126).
2. N. Khan et al., “GNSS-Spoofing Detection via Machine Learning With In-Domain
   and Cross-Domain Testing and Open-Access I/Q Data,” IEEE Access, 2026.
   [Yayın ve özet](https://ieeexplore.ieee.org/abstract/document/11517370).
