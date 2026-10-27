# GNSS ölçüm tutarlılığı prototipi — sunum soru-cevap notları

> Güncelleme: 23 Ekim 2026. Bu not yalnızca doğrulanmış kapsamı anlatır. Ölçüm ayrıntıları [PROJE_RAPORU.md](PROJE_RAPORU.md), veri kökeni [DATA_PROVENANCE.md](DATA_PROVENANCE.md), TEXBAT skorları ve sınırlamaları [TEXBAT_CURRENT_VALIDATION.md](TEXBAT_CURRENT_VALIDATION.md) içindedir.

### Veriler gerçek mi?
Projede gerçek yayımlanmış kayıtlar, değiştirilmiş türevler ve sentetik dosyalar birlikte vardır. AV-GPS kaynakları gerçek kara aracı deneyleridir; fiziksel İHA uçuşu değildir. TEXBAT değerlendirmesinde gerçek deneylerden türetilmiş işlenmiş GRID NAV/kanal ölçümleri kullanılır; ham IQ bu testte yeniden alıcıdan geçirilmemiştir. Her dosyanın kaynağı ve sınırı veri kökeni raporunda kayıtlıdır.

### Sistem spoofing'i veya jamming'i kanıtlıyor mu?
Hayır. Yazılım ölçüm tutarsızlıklarını ve bazı alıcı müdahale göstergelerini izler. CMC, C/N0, kinematik kurallar ya da ML alarmı tek başına saldırı türünün kanıtı değildir. Kapsama/fix kaybı jamming nedenini de tek başına belirlemez.

### TEXBAT'taki sonucu nasıl anlatmalıyız?
GRID ölçümlerindeki mevcut replay'de DS2 örnek kapsamı %99,77, ilk yeni alarm gecikmesi 0,90 s; DS7 kapsamı %98,49, ilk yeni alarm gecikmesi 5,60 s ve 1.789 örneğin 27'si ilk alarm öncesidir. DS3 başlangıcında alarm zaten açık olduğundan yeni alarm gecikmesi ölçülememiştir. Bu skorlar eşikler/parametreler aynı TEXBAT ailesindeki davranış incelenirken ayarlandığı için keşifseldir; bağımsız ve kör başarı tahmini değildir. DS7 zaman çizelgesinin kaynakları da uyuşmaz; iki sonuç raporda gösterilir.

### Yanlış alarm oranımız nedir?
CMU AirLab’ın farklı alıcıdan 209 nominal uçuşu önceki dondurulmuş sürümde sınandı; nominal varsayım altında örnek alarm oranı %48,98 çıktı. Kayıtlar saldırı etiketli olmadığı için bu kesin FAR değildir. Sonraki düzeltmeler bu kayıtlar kullanılarak geliştirildiğinden güncel sürüm için bağımsız holdout bulunmuyor. Kalibrasyonda kullanılan cleanStatic penceresindeki 0/2.115 de bağımsız yanlış alarm oranı değildir.

### Sistem gerçek zamanlı mı veya uçuş kontrolüne bağlı mı?
Hedef donanımda uçtan uca gecikme ölçümü ve uçuş kontrol entegrasyonu doğrulanmamıştır. Yazılım otopilota/motora komut göndermez. Arayüzdeki INS/inertial prediction davranışı, saha veya emniyet sertifikasyonu değildir.

### Literatürle ilişkisi ve yenilik iddiası nedir?
Prototip, alıcıya özel adaptörleri, kural kontrollerini, CMC izlemeyi ve mevcut öğrenilmiş bileşenleri bir araya getirir. Yöntem literatürdeki korelatör/SQM, anten yönü veya kalibre edilmiş olasılıksal çoklu-metrik testlerle eşdeğer değildir. Özgünlük ve üstün performans iddiası için daha kapsamlı kaynak taraması, açık yöntem tanımı ve aynı veride uygun karşılaştırmalı deney gerekir.

### Bundan sonraki bilimsel test nedir?
CMU ve TEXBAT kayıtları geliştirme için kullanıldığı için yeni kayıt/alıcıyı önceden kilitli holdout yapmak gerekir. Eşik ve karar parametrelerini geliştirme kaydında seçip dondurmak; başka uçuş/kayıt ve alıcıyı kör holdout yapmak; bağımsız temiz veride yanlış alarmı, saldırı etiketli veride olay düzeyinde tespit/kaçırma ve gecikmeyi ayrı ölçmek; mümkünse ham IQ'yu bağımsız yazılım alıcıdan geçirmek ve GNSS/IMU referansıyla kinematiği çapraz doğrulamak.
