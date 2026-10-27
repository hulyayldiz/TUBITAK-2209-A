# TÜBİTAK 2209-A Sunum Rehberi: GNSS Ölçüm Tutarlılığı Prototipi

> Güncelleme: 23 Ekim 2026. Önceki sürümdeki sentetik F1, ablation, çalışma zamanı, GPS/INS ve saha performansı ifadeleri doğrulanmadığı için kaldırıldı. Sunumda güncel ölçümler için [PROJE_RAPORU.md](PROJE_RAPORU.md), TEXBAT ayrıntıları için [TEXBAT_CURRENT_VALIDATION.md](TEXBAT_CURRENT_VALIDATION.md), veri kökeni için [DATA_PROVENANCE.md](DATA_PROVENANCE.md) kullanılmalıdır.

## Önerilen sunum akışı

1. **Problem ve kapsam:** GNSS spoofing alıcının yanlış PVT üretmesine yol açabilir; jamming hizmet kullanılabilirliğini düşürür. Bunlar ayrı tehditlerdir. Bu proje kayıt/ölçüm akışlarında tutarsızlıkları araştıran bir yazılım prototipidir.
2. **Literatür:** Kod-taşıyıcı ve navigasyon artıklarının, C/N0/korelatör SQM ölçütlerinin, anten/yön yöntemlerinin farklı kanıtları kullandığını açıklayın. Tek bir metriğin bütün saldırılarda yeterli olmadığını; alıcıya uygun kalibrasyon, yanlış alarm ölçümü ve ayrı test verisi gerektiğini vurgulayın [1–3, 6].
3. **Mimari:** Kaynağa özel adaptör → ortak gözlem şeması/kalite kontrolü → kural, alıcı profili, CMC ve mevcut ML bileşenleri → alarm ve günlükleme. Ham RF demodülasyonu ve otonom uçuş kontrolü kapsam dışıdır.
4. **Veri kökeni:** TEXBAT GRID NAV/kanal ölçümleri işlenmiş gerçek kayıtlardır, ham IQ değildir. AV-GPS kayıtları gerçek kara aracı deneyleridir; türetilmiş IHA isimli CSV fiziksel İHA uçuşu değildir. Sentetik örnekleri gerçek saha verisinden ayrı gösterin.
5. **Bağımsız nominal uçuş bulgusu:** CMU AirLab farklı GNSS/INS platformundaki 209 nominal enerji uçuşu önceki dondurulmuş sürümde test edildi; nominal varsayımla örnek alarm oranı %48,98 idi. Veriler saldırı etiketli olmadığı için bu kesin FAR değildir. Sonraki navigasyon düzeltmesi bu uçuşlarda geliştirildi; güncel sürüm için bunlar bağımsız test sayılmaz. Kaynak ve dönem farkı [INDEPENDENT_REAL_VALIDATION.md](INDEPENDENT_REAL_VALIDATION.md) içinde.
6. **Ölçülmüş TEXBAT bulgusu:** cleanStatic kalibrasyon aralığında 2.115 örnekte alarm yok; bağımsız yanlış alarm oranı sayılmaz. DS2 kapsamı %99,77 ve ilk yeni alarm +0,90 s. DS7 kapsamı %98,49, ilk yeni alarm +5,60 s ve 1.789 saldırı örneğinin 27'si ilk alarmdan önce. DS3'te alarm başlangıçta zaten etkin olduğundan yeni alarm gecikmesi ölçülemiyor. Tanım ve zaman çizelgesi alternatifleri raporda.
7. **Sınırlamalar ve sonraki deney:** Eşikler aynı TEXBAT ailesi incelenirken ayarlandığı için bu skorlar keşif/değerlendirme kanıtıdır; bağımsız genelleme değildir. Farklı alıcı/oturumda test, eşiklerin önceden dondurulması, bağımsız temiz kayıtlar, doğrulanmış etiketler ve mümkünse ham IQ ile alıcı çapraz kontrolü gerekir.

## Kullanılabilecek sonuç cümlesi

“Mevcut TEXBAT replay seçilmiş işlenmiş ölçümlerde kayıt-özel alarm kapsamı ve gecikmesi gösteriyor. Önceki dondurulmuş sürüm farklı alıcının CMU nominal uçuşlarında %48,98 örnek alarm oranı verdi; veriler saldırı etiketi taşımadığından kesin yanlış alarm olasılığı değildir. Sonraki düzeltmeler bu kayıtlarla geliştirildiği için güncel sürümün bağımsız testi henüz yok.”

## Sunumda kullanmayın

- Eski `%98,5` / `%99,5` F1, `%0,45 m` RMSE, `%30` EKF iyileşmesi ve `<10 ms` / `<300 ms` gecikme iddiaları: güncel tekrarlanabilir benchmark veya hedef donanım ölçümüyle doğrulanmış değiller.
- “TEXBAT ham IQ test edildi” ifadesi: güncel replay işlenmiş GRID NAV/kanal ürünlerini kullandı.
- “Zero-day koruması”, “saldırıyı ispatlar”, “yanlış alarm yok”, “saha/İHA doğrulaması” veya “INS'e güvenli otomatik geçiş” ifadeleri: mevcut kanıt bunları desteklemiyor.
- Sentetik saldırı türevlerini gerçek RF jamming/spoofing deneyi gibi sunmayın.

## Kaynaklar

[1] M. L. Psiaki and T. E. Humphreys, “GNSS Spoofing and Detection,” *Proceedings of the IEEE*, 104(6), 1258–1270, 2016. [DOI](https://doi.org/10.1109/JPROC.2016.2526658).

[2] F. Rothmaier et al., “GNSS Spoofing Detection through Metric Combinations: Calibration and Application of a General Framework,” *ION GNSS+ 2021*, 4249–4263. [DOI](https://doi.org/10.33012/2021.18126).

[3] Q. Li et al., “Intrinsic Identification and Mitigation of Multipath for Enhanced GNSS Positioning,” *Sensors*, 21(1), 188, 2021. [DOI](https://doi.org/10.3390/s21010188). CMC bileşenleri ve multipath sınırlaması.

[4] UT Austin Radionavigation Laboratory, [TEXBAT veri ve senaryo açıklaması](https://radionavlab.ae.utexas.edu/texbat/).

[5] TEXBAT metrikleri, veri kökeni ve sınırlamalar: [güncel proje raporu](PROJE_RAPORU.md).

[6] A. M. Khan et al., “Detection of Intermediate Spoofing Attack on Global Navigation Satellite System Receiver Through Slope Based Metrics,” *The Journal of Navigation*, 73(5), 1052–1068, 2020. [DOI](https://doi.org/10.1017/S0373463320000168).
[7] T. A. Rodrigues et al., CMU AirLab drone flight dataset, *Scientific Data*, 8, 155, 2021. [DOI](https://doi.org/10.1038/s41597-021-00930-x); [data](https://doi.org/10.1184/R1/12683453).
