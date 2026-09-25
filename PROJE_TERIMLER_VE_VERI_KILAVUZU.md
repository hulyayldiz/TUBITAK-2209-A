# 📖 SIFIRDAN BAŞLAYANLAR İÇİN: PROJE TERİMLERİ VE VERİ BİLGİ KILAVUZU

Bu kılavuz, projeyi incelerken veya sunarken karşılaşılabilecek tüm karmaşık siber güvenlik ve teknik terimleri "Gündelik dilde, hiç bilmeyen birine anlatır gibi" açıklamak için hazırlanmıştır.

---

## 1. TEMEL HAVACILIK VE NAVİGASYON TERİMLERİ

* **GNSS (Global Navigation Satellite System):** Sadece Amerikan sistemi olan "GPS" değil; Avrupa (Galileo), Rusya (GLONASS) ve Çin (BeiDou) gibi uzaydaki tüm konum uydularının genel ve evrensel adıdır. Biz projemizde sadece GPS değil, hepsini (GNSS) kapsayan bir güvenlik yapıyoruz.
* **Otonom Araç / İHA (UAV):** İçinde insan pilot/şoför olmayan, kendi kendine uçan (İnsansız Hava Aracı) veya kendi kendi giden araçlardır. Bu araçların gözleri tamamen dışarıdan gelen uydulara (GNSS) bağlıdır, uydu kandırılırsa araç da kandırılmış olur.

---

## 2. SİBER SALDIRI (KÖTÜ ADAM) TERİMLERİ

* **Spoofing (Işınlanma / Sahtekarlık):** Bir hackerın elinde güçlü bir vericiyle sizin drone'unuza "Sahte Uydu Sinyalleri" göndermesidir. Drone bir anda uzaydaki değil, yeryüzündeki hackerın yalan sinyaline inanır ve kendini İstanbul'dayken aniden Ankara'da sanıp oraya uçmaya başlar. Biz buna "Işınlama Saldırısı" diyoruz. CSV loglarında satır satır koordinatlar kayabilir.
* **Jamming (Sinyal Boğma / Kör Etme):** Hackerın "Ben sana yanlış bilgi vereyim" demek yerine, "Sana o kadar yüksek sesle (beyaz gürültüyle) bağıracağım ki kendi uydularını hiç duyamayacaksın" demesidir. Drone tamamen sağır/kör olur. Sinyal gücü aniden düşer.
* **Elektronik Harp (EW - Electronic Warfare):** Orduların radyo dalgalarıyla uyduları, dinlemeleri ve seyir sistemlerini hackleme ve bozma savaşlarının genel adıdır. 

---

## 3. BİZİM SAVUNMA (KAHRAMAN) TERİMLERİMİZ

* **C/N0 (Carrier-to-Noise density ratio / Sinyal Kalitesi):** Literatürde "SNR" yerine kullanılan en hassas terimdir. Bir sinyalin gürültü içindeki net gücünü (dB-Hz biriminde) gösterir. Normalde 40-50 dB-Hz civarındadır. Jamming (Sinyal Boğma) durumunda bu değer 20'nin altına düşer. Sistemimiz bu düşüşü bir DoS (Denial of Service) saldırısı olarak anında yakalar.
* **G-Kuvveti (İvme İhlali):** Bir nesnenin hızındaki ani değişimin yerçekimi (g) cinsinden ifadesidir. İHA'lar veya araçlar fiziksel olarak belirli bir ivmenin (örn. 2g) üzerine aniden çıkamazlar. Eğer GPS verisi bir saniyede 15g ivme gösteriyorsa, bu sinyalin sahte (Spoofing) olduğunun matematiksel kanıtıdır.
* **Drift (Sapma Hatası):** Kör uçuş (INS) sonsuza kadar süremez. Rüzgar, titreşim derken cihaz zamanla yolundan sapmaya başlar. Buna sapma hatası denir, o yüzden sistemimiz 10-15 saniyede bir anteni açıp dışarıyı kontrol eder.

---

## 4. YAPAY ZEKA TERİMLERİ (AKILLI KARAR MOTORU)

* **LSTM-VAE (Anomali Tespiti Zekası):** Sadece geçmişten ona öğretilen ezberlenmiş saldırıları değil, "Ben hayatımda böyle bir şey görmedim, burada bir gariplik var" diyebilen çok zeki bir derin öğrenme modelidir.
* **Random Forest (RF):** Geçmiş verileri ağaç dalları gibi sınıflara ayırıp tecrübeye dayalı karar veren diğer yardımcımızdır.
* **Epoch (Eğitim Döngüsü):** Yapay zekanın "Eğit" butonuna basıldığında tüm kitabı baştan sona kaç defa tekrar okuduğunu belirtir. Eğitim (Training) o yüzden yavaş sürer.
* **Inference (Çıkarım):** Eğitimini tamamlamış (mezun olmuş) yapay zekanın, o an gördüğü soruya "Bu bir Spoofing'dir!" diye saniyeden bile kısa sürede (milisaniyede) anında cevap vermesidir. Uygulamamız havadayken eğitim yapmaz, çıkarım (Inference) yapar.

---

## 5. VERİ KAYNAKLARIMIZ NEREDEN GELİYOR VE NEDEN DEĞİŞTİRDİK?

* **Orijinal Veri (AV-GPS-Dataset):** Amerika'da araştırmacıların otonom (kendi giden) bir araca gerçek cihazlar takıp, sonra ona radyoyla sahte konum (Spoofing) basarak kaydettiği %100 GERÇEK ve uluslararası bilim camiasında kabul görmüş veridir.
* **Neden Değiştirdik? (Data Augmentation):**
  1. Otonom bir araba yavaş gider (20km/h), bizim sistemimiz ise bir İHA (Dron). Bu yüzden sistemimizi gerçek havacılık hızlarında test etmek için matematiksel bir işlem yaparak gerçek verinin hızını İHA düzeylerine katladık.
  2. Orijinal veride sadece "Spoofing" vardı. Askeri laboratuvarlarda yapılan **Tehdit Enjeksiyonu** mantığını kullanarak, sahte ışınlanma başlamadan hemen öncesine 20 saniyelik bir Jamming (Sinyal çöküşü) ekledik.
* **Sonuç (Kombine Saldırı Senaryosu):** Temeli %100 gerçek fizik kurallarına dayanan, ancak havacılık ve ağır bir askeri savaş senaryosuna göre "Zenginleştirilmiş (Augmented)" kusursuz bir simülasyon ortamı yarattık. Jüriye bu işlemin adının **Data Augmentation** olduğunu söylemelisiniz.
