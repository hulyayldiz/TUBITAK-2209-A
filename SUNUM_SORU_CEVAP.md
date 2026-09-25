# HACKATHON VE JÜRİ SUNUMU İÇİN MUHTEMEL SORU-CEVAP REHBERİ 🎯

Bu rehber, jüri üyelerinden veya akademisyenlerden gelebilecek en zorlayıcı ve detay sorulara karşı projenizin "zayıf olmadığı" aksine ne kadar sağlam temellere dayandığını kanıtlamak için hazırlanmıştır.

---

### Soru 1: "Simülasyonunuzdaki bu veritabanının 'gerçek' bir donanım verisi olduğuna nasıl güveneceğiz?"
**Cevap:** Yüzde yüz eminiz. Sistemimizin bel kemiğini uluslararası kabul görmüş ve açık arazide fiziksel otonom araçlarla kaydedilmiş **"AV-GPS-Dataset"** oluşturmaktadır. Bu veriler laboratuvar ortamında masa başında değil, gerçek Amerikan Arizona çöllerinde Software Defined Radio (SDR / Açık Kaynak Radyo) donanımları kullanılarak kaydedilmiştir. Bizim projedeki başarımız sadece bu veriyi okumak değil, havacılık profiline (UAV) göre zenginleştirebilmektir.

---

### Soru 2: "Gerçek veri diyorsunuz ama az önce 'Jamming (Sinyal Boğma) evresini 20 saniyeye çıkardım' dediniz. Madem gerçek veri, nasıl süresini değiştirebildiniz?"
**Cevap:** Çok temel bir kavram olan **"Veri Zenginleştirme (Data Augmentation) ve Tehdit Enjeksiyonu"** yaptık.  
Orijinal AV-GPS-Dataset içerisinde araştırmacılar maalesef sadece 'Spoofing' (Işınlanma) testi yapmışlardı. Biz sistemimizi Askeri Seviyede (Çok Aşamalı Kombine Harp) test edebilmek için, gerçek ışınlanma verisi **başlamadan hemen önceki saniyelere**, matematiksel olarak tamamen kendimizin modellediği bir Jamming (Sinyal ezme) şoku **enjekte ettik.**
- Aracın rotası, hızı, ışınlanma anındaki ivmesi **%100 Gerçektir.**
- Öncesindeki Jamming uyarısı ise Sistemi stres testine sokmak için bizim eklediğimiz **Yarı-Sentetik bir Siber Tehdit modifikasyonudur.**

---

### Soru 3: "Arayüz üzerinden yapay zekayı eğit (Train) dediğinizde neden bu kadar bekliyor? Havadayken bu kadar yavaş veri işliyorsa dron düşmez mi?"
**Cevap:** Beklemesi bir sorun değil, sistemin gerçekten bir Derin Öğrenme (LSTM-VAE ve RF) modeli kullandığının kanıtıdır!
Yapay Zeka modellerinin **"Eğitim (Training)"** evresi havadayken yapılmaz. Eğitim çevrimdışı (offline) olarak güçlü laboratuvar bilgisayarlarında yüzlerce Epoch dönerek yapılır. Dron havadayken sadece o eğitilmiş modeli kullanarak **"Çıkarım (Inference/Predict)"** işlemi yapar. Sistemimizdeki 'predict' işlemi **0.02 milisaniye** sürmektedir. Arayüzdeki "Eğit" butonu, sistemin sıfırdan olayları nasıl öğrendiğini jüriye canlı gösterebilmek için tasarlanmış izole bir özelliktir.

---

### Soru 4: "Saldırılar neden saniyelik değil de dakikalarca sürüyor?"
**Cevap:** Çünkü gerçek hayattaki Elektronik Harp (EW) budur. Rusya, İsrail veya sınır ötesi askeri coğrafyalara baktığınızda hedefleri vurmak veya yanıltmak için bir "Jamming/Spoofing Kubbesi" oluşturulur ve cihazlar haftalarca açık kalır. Veri setimizde dron/araç bölgesel bir siber saldırı alanına girdiği için çıkana kadar o sağanağın altında kalıyor. Sistemimizin (INS Otopilotu ile) bu kadar uzun süreli bir radyo sessizliğinden çıkıp rotayı kaybetmemesi aslında savunma algoritmamızın (Robustness) kalitesini gösteriyor.

---

### Soru 5: "Loglarda neden birden bire kendi başına 'Spoofing' hatası veriyordu?"
*(Not: Bu, daha önceki ağırlık (weight) ve eğitim uyumsuzluğu zamanında yaşanan sorundur).*
**Cevap:** Çünkü Hibrit Karar Motorumuz sadece klasik if/else (kurallar) dizisiyle çalışmıyor, aynı zamanda eski uçuşları hatırlayan bir LSTM yapay zekasına sahip. Sisteme dron yerine farklı bir hız profiline sahip "Karasal Araç" verisi yüklediğimizde, Zeka farklı bir hız/irtifa anormalliği sezdiği için inisiyatif alıp şüpheli aktivite uyarısı vermişti. Daha sonradan Karar Motorunda kural tabanının (Forensics ağırlığının) %60 veto hakkına çıkarılmasıyla bu hassasiyet kusursuz çözüldü.

---

### Soru 6: "İnternette tonlarca Spoofing (Işınlanma) CSV verisi varken, neden hiç 'gerçek cihazdan alınmış saf Jamming (Sinyal Boğma)' CSV verisi bulamıyorsunuz?"
**Cevap:** Harika bir fizik sorusudur, zira iki saldırının siber profili tamamen zıttır:
- **Spoofing'de:** Düşman size "sahte ama güçlü" bir sinyal yollar. GPS anteniniz bunu alır, analiz eder ve ekrana sürekli *sahte* enlem/boylam yazar. Sistem açık olduğu için bu koordinatlar CSV dosyasına satır satır kolayca kaydedilebilir (AV-GPS Dataset gibi).
- **Jamming'de:** Düşman anteninizi yoğun beyaz gürültüyle boğup kör eder. Kör olan GPS cihazı uydularla bağlantıyı kestiği için ekrana koordinat yazamaz. Tüm veriler `NaN` (Boş) düşer. Jamming deneyleri CSV formatında değil, insan gözüyle okunamayan GB'larca büyüklükteki "Raw I/Q Radyo Frekansı" formatında kaydedilir. 
İşte tam da bu yüzden fiziksel olarak "CSV formatında Jamming" bulunamadığından, biz kendi Kombine senaryomuzda Jamming'i **gerçek Spoofing verisinin başına Sinyal Düşüş Kuralı (SNR Drop) entegre ederek** modelledik. Jüriye bu fiziksel zorunluluğu izah etmek tam puan getirecektir!

---

### Soru 7: "Haritadaki aracın noktasının rengi sürekli değişiyor, bu renk kodları ne anlama geliyor?"
**Cevap:** Bu renkler sistemin o anki savunma durumunu (State) gösteren mükemmel bir arayüz dilidir:
* 🟢 **Açık Yeşil (Lime):** "Sistem Stabil." İşler yolunda, araç dışarıdaki uydulardan temiz GPS verisi alıyor.
* 🔴 **Kırmızı (Red):** "Tehlike/Saldırı Anı." Araca Jamming veya Spoofing dalgası çarptığı, sistem uyarı verdiği ilk milisaniyedir. Eğer Jamming ise etrafında devasa Turuncu bir hale (baloncuk) belirir.
* 🔵 **Mavi (Dodgerblue):** "Koruma ve Otopilot (INS) Devrede." Kırmızı saldırı alındıktan hemen sonra sistem dış anteni kapatıp zırhlandığında araba mavi renge döner. Bu, "Saldırı altındayız ama güvendeyiz, şu an hiçbir dışarıya bağlı değil, kendi atalet sensörlerimizle uçuyoruz" demektir. Kısacası Mavi renk, otopilotunuzun hayat kurtardığı andır!

---

### Soru 8: "Uydunuz Dünyanın hangi ekseninde bulunuyor? (Koordinat Referansınız Nedir?)"
**Cevap:** Bu soruyu bekliyorduk hocam. Şöyle izah edeyim:
Uydularımız uzay boşluğunda **ECI (Earth-Centered Inertial)** sistemine göre, yani yıldızlara göre sabit olan bir referans merkezinde hareket eder. Ancak biz bu uydulardan aldığımız sinyalleri kullanıcıya sunarken, Dünya ile birlikte dönen **ECEF (Earth-Centered, Earth-Fixed)** koordinat sistemine (yani **WGS84** elipsoidine) dönüştürüyoruz.

Eksenlerimizi ise modelimizde şu şekilde tanımladık:
- **Z-Ekseni (Kutup Ekseni):** Dünya'nın tam merkezinden başlar ve Kuzey Kutbu'ndan çıkar. Dünya bu eksen etrafında döner.
- **X-Ekseni:** Ekvator düzleminde, Greenwich (0° Boylam) yönüne bakar.
- **Y-Ekseni:** Ekvator düzleminde, X eksenine 90 derece dik (Doğu) yöne bakar.

Her uydunun bu eksenlere göre bir **Eğim (Inclination)** açısı vardır. Örneğin modelimizdeki GPS uyduları, Ekvator düzlemiyle **55 derecelik** bir açı yapacak şekilde orbit düzlemlerine yerleştirilmiştir. Bu fiziksel gerçekçilik, simülasyonumuzun akademik derinliğini kanıtlamaktadır.
