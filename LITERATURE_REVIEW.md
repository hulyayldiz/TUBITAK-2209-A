# Literatür eşlemesi ve yöntem kapsamı

**Son gözden geçirme:** 27 Ekim 2026
**Amaç:** Projedeki yöntem iddialarını temel ve birincil literatürle ilişkilendirmek, desteklenmeyen yorumları ayırmak. Bu belge kapsamlı sistematik derleme değildir; seçilmiş hakemli yayınlar ve resmi benchmark kaynakları için izlenebilirlik notudur.

## Problem kapsamı

GNSS spoofing ve jamming farklı tehditlerdir. Jamming sinyal kullanılabilirliğini düşürür; spoofing alıcıyı sahte ama makul görünebilen sinyalleri izlemeye yöneltebilir. Savunmaların gördüğü kanıt, alıcının erişilebilir çıktısına bağlıdır: RF/IQ ve korelatör özellikleri, kod/taşıyıcı ölçümleri, PVT artık ve tutarlılıkları, ya da bağımsız IMU/INS veya başka sensörler. Bu proje işlenmiş kayıt/adaptör girdilerini inceleyen bir yazılım prototipidir; ham IQ korelatör dedektörü, anten dizisi, bağımsız uçuş referansı ya da otonom uçuş emniyet sistemi değildir [1, 2].

## Literatür ile yöntem eşlemesi

| Literatür yöntemi | Yayındaki kanıt ve değerlendirme | Bu projeyle ilişki |
|---|---|---|
| Alıcı içi güç ve sinyal şekli ölçütleri | C/N0, korelatör şekli ve diğer takip döngüsü metrikleri; erişilebilir alıcı çıktısı ve saldırı tipine bağlı [1, 2, 3] | Mevcut TEXBAT replay'i ham IQ/korelatörleri yeniden işlemiyor; bu yöntemlerle doğrudan eşdeğerlik veya kıyas iddiası yok. |
| Alıcıya özel çoklu ölçüt/GLRT | Nominal ölçüm modeli gerçek uçuş verisinde kalibre edilir; eşik, hedef yanlış alarm olasılığına göre kurulur ve TEXBAT senaryolarında sınanır [4] | Projenin kuralları ve birleştirilmiş skorları aynı kalibrasyon ve FAR garantisini sağlamıyor. “Düşük yanlış alarm” ya da olasılıksal garanti sonucu çıkarılamaz. |
| Slope tabanlı izleme-korelatör metrikleri | Ek korelatörlerden ölçüt türetir, temiz sinyal varyansından eşik seçer, TEXBAT üzerinde sınar [5] | Projedeki CMC eğimi pseudorange/taşıyıcı faz ölçümlerinden gelir; [5]'teki korelatör yöntemiyle aynı değildir. |
| Code-minus-carrier ve multipath analizi | CMC, pseudorange ile dalga boyuyla ölçeklenmiş taşıyıcı fazının birleşimidir; multipath, iyonosfer, belirsizlik ve gürültü de etkiler [6] | CMC eğimi burada yardımcı tutarsızlık sinyalidir; tek başına spoofing kimliği veya nedensellik kanıtı değildir. |
| Çoklu sensör ve INS tutarlılığı | GNSS dışı ölçümle bağımsız çapraz kontrol; sensör zaman eşlemesi/kalibrasyonu ve referanslı saha ölçümü gerekir [7] | Projede kod bulunması, bağımsız IMU ile test veya güvenli INS yedekleme performansını kanıtlamaz. |
| Öğrenilmiş RF/LSTM-VAE bileşenleri | RF ve LSTM/VAE, sırasıyla topluluk sınıflandırması, sıralı bellek ve olasılıksal latent model aileleridir [12–14]. Mimari kaynakları GNSS tespit başarısı kanıtı değildir. | Projede kullanımları özgün algoritma katkısı veya tek başına güvenilir saldırı tespiti anlamına gelmez; veri sızıntısı ve eşik kalibrasyonu kayıt bazında değerlendirilmelidir. |
| Makine öğrenmesi ve alanlar arası genelleme | Aynı veri alanındaki rastgele/karma bölme sonuçları farklı kayıt/veri kümesine geçiş başarısını temsil etmez; çapraz veri kümesi performansı ciddi düşebilir [8] | Geliştirme kaydı üzerinde eşik/parametre ayarı sonrası aynı ailede alınan sonuç keşifseldir; kilitli farklı alıcı/uçuş holdout'u gerekir. |

## CMC ölçütünün yorumu

Projede hesaplanan `CMC_i(t) = P_i(t) - λφ_i(t)` için `P_i` kod pseudorange, `φ_i` taşıyıcı fazı çevrim, `λ` taşıyıcı dalga boyudur. Geçerli bir uydu yayı üzerinde CMC eğimi regresyonla hesaplanır. Uydudan bağımsız ortak geometrik/saat bileşenleri ideal koşullarda büyük ölçüde giderilebilir; ölçüm gürültüsü, multipath, iyonosfer, alıcı işleme ve yay kesilmeleri kalır. Dolayısıyla CMC, çok yollu etki ve alıcı sapmalarından bağımsız bir spoofing ölçütü değildir [6]. Kodda kullanılan pencere uzunlukları, kanal çoğunluğu, kalibrasyon aralığı ve alarm onayı ampirik proje parametreleridir; yayında evrensel eşik olarak önerilmemiştir.

TEXBAT literatürü bazı alıcı/kayıt koşullarında ortak code-carrier drift kaynaklarına dikkat çeker. Bu, ölçülen eğimin mutlaka saldırıdan doğduğu varsayımını sakıncalı kılar. DS7'de gözlenen sonuç yalnızca kullanılan işlenmiş kayıt ve mevcut parametrelerle ilgili ampirik bulgudur [9].

## Benchmark ve deney tasarımı

TEXBAT, kontrollü GPS L1 C/A spoofing senaryoları içeren bir araştırma benchmark'ıdır; tüm alıcıları, saldırıları ve saha koşullarını temsil etmez [9]. Projenin TEXBAT replay'i yayımlanmış GRID NAV/kanal ölçümlerine dayanır; ham RF IQ bağımsız alıcıda yeniden işlenmemiştir. Aynı `cleanStatic` kaydından profil kalibre edilmesi ve DS7 gözlemleri sonrasında parametre ayarlanması nedeniyle TEXBAT sonucu geliştirme/keşif sonucudur. Ayrıca farklı alıcıdaki CMU AirLab 209 nominal uçuşu dondurulmuş eski sürümle bağımsız değerlendirildi; nominal varsayım altında örnek alarm oranı %48,98 bulundu. Sonraki düzeltmeler bu kayıtlar üzerinde geliştirildiğinden yeni sürüm için bağımsız holdout kalmamıştır. CMU kayıtlarında saldırı etiketi veya bağımsız RF saldırısızlık sertifikası olmadığı için bu oran etiketli sınıflandırmadan türetilmiş kesin FAR değildir.

Literatüre uygun doğrulama için deney öncesi eşik ve karar parametreleri dondurulmalı; kayıt, uçuş veya alıcı bazında ayrılmış temiz ve saldırı testleri kullanılmalı; alarm düzeyi ground truth saldırı zamanlarıyla eşleştirilmeli; olay düzeyinde tespit, kaçırma, ilk tespit gecikmesi ve temiz kayıt başına yanlış alarm raporlanmalıdır. Metrik tanımı, örnekleme aralığı, kapsama aralığı, veri kökeni, yazılım sürümü ve güven aralıkları açıklanmalıdır. Tekrarlanan zaman örneklerini bağımsız istatistiksel örnek gibi saymamak gerekir [4, 8].

Yeni alıcıda test için FGI Jammertest 2025 kaydı aday seçildi: Etsin kaydı Septentrio PolaRx5 ölçümleri, SBF/RINEX, olay yer gerçeği ve CC BY 4.0 erişim bilgisi bildiriyor [15]. Veri kümesi kümülatif olduğundan sınama, sabitlenmiş dosya listesi ve dosya hash'leriyle tanımlanmalıdır. 27 Ekim 2026'da katalog dosya listesi görünürken indirme kullanılabilirlik uç noktası kapalıydı. Kullanıcı aynı tarihte veri erişimi ve olay etiketleri için araştırmacıya e-posta gönderdiğini bildirdi; yanıt bekleniyor. Bu nedenle kayıt henüz bağımsız test sonucu sağlamıyor. Erişim ve protokol durumu [holdout planında](INDEPENDENT_HOLDOUT_PROTOCOL.md) tutuluyor.

## Sonuç ve iddia sınırı

Mevcut kanıt şu dar iddiayı destekler: ortak gözlem şemasına alınmış kayıtlarda kural, CMC ve öğrenilmiş bileşenleri çalıştıran, bazı TEXBAT işlenmiş ölçüm senaryolarında anomali alarmı üreten araştırma prototipi. Literatür uyumlu raporlama; yöntemin kanıt alanını, parametre kalibrasyonunu ve veri ayrımını açıklamayı, tespit kapsamını FAR/precision/recall ile karıştırmamayı; önceki dondurulmuş sürümdeki bağımsız CMU denemesinin başarısız alarm oranını ve güncel sürümün holdout eksikliğini ayrı belirtmeyi gerektirir.

Mevcut kanıt; evrensel literatür uyumu, genel geçer tespit başarısı, sertifikalı bütünlük, sıfır yanlış alarm, gerçek zamanlı uçuş performansı, farklı alıcıya aktarılabilirlik veya otonom güvenliğe geçiş iddialarını desteklemez. Bunlar yazım düzenlemesiyle çözülemez; önceden dondurulmuş yöntem ve bağımsız referanslı yeni deneyler gerekir.

## Kaynakça

1. M. L. Psiaki and T. E. Humphreys, “GNSS Spoofing and Detection,” *Proceedings of the IEEE*, 104(6), 1258–1270, 2016. [DOI: 10.1109/JPROC.2016.2526658](https://doi.org/10.1109/JPROC.2016.2526658).
2. M. Manfredini et al., “Effective GPS Spoofing Detection Utilizing Metrics from Commercial Receivers,” *Proceedings of ION GNSS+ 2018*, 672–689. [ION](https://www.ion.org/publications/abstract.cfm?articleID=15595).
3. B. Wesson et al., “GNSS Signal Authentication via Power and Distortion Monitoring,” *IEEE Transactions on Aerospace and Electronic Systems*, 54(2), 739–754, 2018. [DOI: 10.1109/TAES.2017.2765258](https://doi.org/10.1109/TAES.2017.2765258).
4. F. Rothmaier et al., “GNSS Spoofing Detection through Metric Combinations: Calibration and Application of a General Framework,” *Proceedings of ION GNSS+ 2021*, 4249–4263. [DOI: 10.33012/2021.18126](https://doi.org/10.33012/2021.18126).
5. A. M. Khan et al., “Detection of Intermediate Spoofing Attack on Global Navigation Satellite System Receiver Through Slope Based Metrics,” *The Journal of Navigation*, 73(5), 1052–1068, 2020. [DOI: 10.1017/S0373463320000168](https://doi.org/10.1017/S0373463320000168).
6. Q. Li et al., “Intrinsic Identification and Mitigation of Multipath for Enhanced GNSS Positioning,” *Sensors*, 21(1), 188, 2021. [DOI: 10.3390/s21010188](https://doi.org/10.3390/s21010188).
7. M. Stas et al., “Sensor- and Communication-Based GNSS Spoofing and Jamming Detection Framework for Connected and Automated Vehicle Applications,” *Proceedings of ION 2026 Pacific PNT Meeting*, 786–800. [ION](https://www.ion.org/publications/abstract.cfm?articleID=20611).
8. N. Khan et al., “GNSS-Spoofing Detection via Machine Learning With In-Domain and Cross-Domain Testing and Open-Access I/Q Data,” *IEEE Access*, 14, 73921–73934, 2026. [DOI: 10.1109/ACCESS.2026.3693081](https://doi.org/10.1109/ACCESS.2026.3693081).
9. T. E. Humphreys et al., “The Texas Spoofing Test Battery: Toward a Standard for Evaluating GPS Signal Authentication Techniques,” *Proceedings of ION GNSS 2012*, 3569–3583. Benchmark tanımı ve veri erişimi: [UT Austin Radionavigation Laboratory — TEXBAT](https://radionavlab.ae.utexas.edu/texbat/).
10. M. Lemmenes et al., “Detailed Analysis of the Texas Spoofing Test Battery Using a High Fidelity Software Receiver,” *Proceedings of ION GNSS+ 2016*. [UT Austin PDF](https://radionavlab.ae.utexas.edu/images/stories/files/papers/LemmenesGNSSpaper.pdf).
11. T. A. Rodrigues et al., “In-flight positional and energy use data set of a DJI Matrice 100 quadcopter for small package delivery,” *Scientific Data*, 8, 155, 2021. [DOI: 10.1038/s41597-021-00930-x](https://doi.org/10.1038/s41597-021-00930-x); [dataset DOI: 10.1184/R1/12683453](https://doi.org/10.1184/R1/12683453).

12. L. Breiman, “Random Forests,” *Machine Learning*, 45, 5–32, 2001. [DOI: 10.1023/A:1010933404324](https://doi.org/10.1023/A:1010933404324).
13. S. Hochreiter and J. Schmidhuber, “Long Short-Term Memory,” *Neural Computation*, 9(8), 1735–1780, 1997. [DOI: 10.1162/neco.1997.9.8.1735](https://doi.org/10.1162/neco.1997.9.8.1735).
14. D. P. Kingma and M. Welling, “Auto-Encoding Variational Bayes,” *International Conference on Learning Representations*, 2014. [Open-access paper record](https://mlanthology.org/iclr/2014/kingma2014iclr-auto/).
15. Finnish Geospatial Research Institute, “FGI Jammertest 2025 GNSS interference dataset,” Fairdata Etsin, released 30 September 2026. Alıcı, ölçüm ve lisans açıklaması: [dataset record](https://etsin.fairdata.fi/dataset/095782a8-4e31-456e-8719-7021b4c96362).
