# Adli kayıt zinciri düzeltmesi — 23 Ekim 2026

## Kanıtlanan neden

Eski `forensic_ledger.jsonl` dosyası 4.575 byte ve 19 kayıt içeriyordu.
Kayıtların tamamının HMAC değeri, Git indeksindeki eski uygulamanın sabit
varsayılan anahtarıyla eşleşiyor; yeni yerel özel anahtarla eşleşmiyor.
İlk 15 kayıt birbirine bağlı. 16, 17, 18 ve 19. satırlar önceki kaydın
hash'i yerine sıfır başlangıç değeriyle imzalanmış. Dolayısıyla yalnızca
eski anahtara dönmek zinciri düzeltmez.

Eski anahtar kaynak kodda bulunduğundan bu HMAC eşleşmeleri kayıtların
gerçekliğini kanıtlamaz. Tarihsel zincir sürekliliği doğrulanmış değildir.

## Uygulanan işlem

Eski dosyanın içeriği değiştirilmeden şu yerel arşive kopyalandı:

`forensic_ledger.jsonl.legacy-81ccd316c7d437536ba9a9710383e371f3d8219c996b3d45842dfa5467489772.jsonl`

Orijinal SHA-256:
`81ccd316c7d437536ba9a9710383e371f3d8219c996b3d45842dfa5467489772`

Aynı adın `.report.json` uzantılı dosyası, 19 eski kaydı ve dört zincir
yeniden başlangıcını raporlar. Hiçbir eski kayıt yeniden imzalanmadı.

Etkin dosyada yerel özel anahtarla bağımsız bir zincir başlatıldı.
İlk `RECOVERY` kaydı eski arşivin ve raporunun SHA-256 değerlerini imzalı
mesajında taşır. Her doğrulama ve yeni kayıt ekleme öncesinde bu dosyaların
varlığı ve hash'leri kontrol edilir; değiştirilmiş veya eksik kanıt varsa
yazma engellenir. Normal segment döndürme sonrasında da kontrol sürer.
Arşivler ve rapor yerel kalır, Git ve Docker bağlamına alınmaz.

Uygulama ile doğrulama betiği artık çalışma dizininden bağımsız olarak
proje klasöründeki aynı dosyayı kullanır. Eksik etkin dosya CLI'da başarı
olarak raporlanmaz. Uygulamanın ilk kurulumda kayıt oluşturması desteklenir.

## Kontroller

- `python -m pytest -q`: **105 geçti**.
- `python verify_hashes.py`: **çıkış kodu 0**, bir yeni zincir başlangıç kaydı;
  bağlı eski arşiv ve rapor hash'leri geçerli.
- Streamlit AppTest: **0 uygulama istisnası**, `forensic_chain_valid=True`.
- Kurtarma testleri: orijinal byte'ların korunması, kopukluk raporu,
  bilinmeyen anahtar/değiştirilmiş eski kayıt için işlemi reddetme,
  arşiv değişikliği veya kaybında engelleme, rapor değişikliği,
  yanlış yeni anahtar, segment döndürme ve çalışma dizini bağımsızlığı.
- `git diff --check`: içerik/boşluk hatası yok.

Bu sonuç yeni zincirin ve korunmuş arşivin bugünkü bütünlüğünü doğrular;
geçmişteki dört kopukluğu geriye dönük olarak ortadan kaldırmaz.
Anahtar yedeklenirken etkin dosya, tüm segmentler, eski arşiv ve rapor
birlikte korunmalıdır. Anahtar değişimi geçmiş zinciri otomatik yeniden
imzalamaz. Önceki veri denetimindeki başarısız hash sonucu o denetim anına
aittir; bu belge sonraki düzeltmeyi kaydeder. ML başarı ölçümleri yeniden
hesaplanmadı; bu değişiklik adli kayıt altyapısıyla sınırlıdır.
