# Demo kullanım kılavuzu

Bu kılavuz, mevcut araştırma prototipinin doğrulanabilir işlevlerini dürüst ve tekrarlanabilir biçimde göstermeyi amaçlar. Arayüz, bir GNSS alıcısının kendisi, uçuş kontrolcüsü veya güvenlik sertifikalı ürün değildir. Demo sırasında ekrandaki alarmı dedektör çıktısı olarak anlatın; saldırının bağımsız doğrulanmış etiketi gibi sunmayın.

## Hazırlık

1. Proje ortamında `streamlit run main.py` komutuyla arayüzü açın.
2. Arayüzün sunduğu kayıtlı veri kümelerinden birini seçin. Dosya adını ve kaynak/kayıt bilgisini not edin; burada adı geçmeyen bir dosyanın projede bulunduğunu varsaymayın.
3. Model eğitimi veya profil kalibrasyonu başlatmadan önce seçili akışın ne olduğunu, eğitimde hangi kayıtların kullanılacağını ve bunların test kaydıyla çakışıp çakışmadığını kontrol edin. Aynı kayda bakarak eşik ayarlayıp sonra aynı kayıtta başarı raporlamak bağımsız test değildir.
4. Deney yapılandırmasını, uygulama sürümünü, adaptörü ve alarm parametrelerini kaydedin. Böylece replay tekrarlanabilir.

## Önerilen kayıtlı replay

Önce `cleanStatic` kaydını gösterin. Bu kaydın 50–120 saniye aralığı güncel CMC alıcı profilini kalibre etmek için kullanılmıştır; dolayısıyla aynı kayıttaki sessiz sonuç, bağımsız yanlış-alarm doğrulaması değildir.

Sonra TEXBAT DS2 veya DS7 replay'ini açın. DS2'de mevcut yapılandırma için ilk yeni alarm yaklaşık 0,90 saniyede, DS7'de 5,60 saniyede oluşmuştur. DS7'deki saldırı başlangıcından ilk alarma kadar 1.789 örneğin 27'si alarm dışında kalmıştır. Bu değerler işlenmiş GRID NAV/kanal ölçümleriyle yapılan, DS7 incelendikten sonra bazı parametreleri ayarlanmış keşifsel replay sonuçlarıdır; kör bağımsız test, gerçek zamanlı gecikme veya genel tespit olasılığı değildir.

Açıklama örneği: “Bu prototip, seçilen TEXBAT kaydının alıcı ölçümlerindeki tutarsızlıkları izliyor. Bu demo ham RF sinyalini yeniden çözmüyor ve alarm tek başına saldırı tipini kanıtlamıyor. DS7 için mevcut geliştirme replay'inde alarm gecikmesi 5,60 saniye; bunun bağımsız kayıtta doğrulanması gerekiyor.”

## Sentetik senaryolar

Sentetik senaryo gösteriliyorsa bunu açıkça sentetik olarak etiketleyin. Enjekte edilmiş özellikler ve senaryo etiketleri algoritma davranışını sınamak için kullanılabilir; bunlar gerçek İHA uçuşu, gerçek saldırı kaydı veya saha doğrulaması değildir. Harita ya da araç animasyonu görselleştirmedir; fiziksel araç kontrolü veya gerçek sensör telemetrisi anlamına gelmez.

## Sonuçların doğru anlatımı

Jamming, alıcıya ulaşan GNSS sinyallerini bozarak kullanılabilirliği düşürür; spoofing ise alıcının yanıltıcı uydu ölçümlerini takip etmesine yol açabilir. Bu projedeki her alarm bu iki sınıftan birini kesinleştirmez. “INS'e geçti”, “sahte uyduyu reddetti”, “otopilotu güvenli moda aldı”, “milisaniyede çalışıyor” veya “%100 gerçek İHA dinamiği” ifadelerini ancak ayrı fiziksel donanım ve zaman referanslı testlerle kanıtlandıysa kullanın. Mevcut yazılım çıktıları bu iddiaları tek başına desteklemiyor.

Ölçüm sonuçlarını örnek kapsamı, olay düzeyinde tespit, kaçırılan olay/örnek, ilk alarm gecikmesi ve temiz bağımsız kayıttaki yanlış alarm olarak ayrı raporlayın. Ardışık örnek kapsamını olay tespit oranı ya da olasılıksal yanlış alarm garantisi diye sunmayın. Yöntem, veri kökeni ve kısıtlar için [teknik rapora](PROJE_RAPORU.md), [literatür eşlemesine](LITERATURE_REVIEW.md) ve [güncel TEXBAT değerlendirmesine](TEXBAT_CURRENT_VALIDATION.md) bakın.

## Günlük ve hash gösterimi

Günlük/hash ekranı gösteriliyorsa bunun yalnızca uygulamanın kaydettiği veride bütünlük kontrolü olduğunu söyleyin. Bu tek başına mahkemece kabul edilebilir adli delil, anahtar yönetimi, güvenilir zaman damgası veya askeri kriptolama kanıtı değildir. Veri kökeni ve dosya doğrulama durumu ayrıca [veri kökeni kaydında](DATA_PROVENANCE.md) belirtilmelidir.
