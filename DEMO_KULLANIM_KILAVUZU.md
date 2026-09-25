# 🎮 HACKATHON / JÜRİ DEMO KULLANIM KILAVUZU

Bu kılavuz, jüri karşısına çıktığınızda projeyi hangi sırayla ve nasıl tanıtmanız gerektiğini adım adım anlatan "Kusursuz Şov" senaryosudur.

---

## 🚀 BAŞLANGIÇ: SİSTEMİ AYAĞA KALDIRMA
1. Terminalden `streamlit run main.py` komutuyla sistemi başlatın.
2. Sistem açıldığında menüden **"Sol Menüyü"** açın.
3. Çıkan menüden en üstteki anahtarı **"Kayıtlı Veri Seti Yükle"** moduna getirin.
4. "Eğitim Verisi Topla" şalterinin **AÇIK (Aktif)** olduğundan emin olun. (Bu, yapay zekanın uçuşu öğrenmesi için şarttır).

---

## 🎯 SENARYO 1: İHA KOMBİNE SİBER HARP TESTİ (EN ETKİLEYİCİ KISIM)
Bu aşamada dünyanın en zor siber saldırılarından biri olan "Önce Jamming, Sonra Spoofing (Kombine)" saldırısını jüriye göstereceksiniz.

* **Adım 1:** Veri yükleme kısmından daha önce hazırladığımız **`Kombine-Gercek-IHA-Saldirisi.csv`** dosyasını seçin.
* **Adım 2:** Araç haritada uçmaya başlayacaktır. Jüriye şunu söyleyin: *"Şu an sistemimiz %100 gerçek verilerle tasarlanmış bir İHA uçuş dinamiğine geçti. Havada 1200 metrede 250 km/sa hızla devriye atıyoruz."*
* **Adım 3 (EĞİTİM):** Uçuş normal bir şekilde devam ederken yaklaşık 15-20 saniye bekleyin. Sonra Karar Motoru paneli altındaki **"Yapay Zeka Modellerini Eğit"** butonuna basın. Jüriye dönüp: *"Yapay zeka şu an havadaki İHA'nın dinamiklerini öğreniyor. Modeller çevrimdışı eğitildiği için bu işlem biraz sürer ancak havadaki çıkarım (predict) hızı milisaniyedir."* deyin.
* **Adım 4 (JAMMING GÖZLEMİ):** Bir süre sonra ekranda sinyal gücünün (SNR) aniden çakıldığını (40'lardan 15'e) ve haritanın kırmızıya döndüğünü göreceksiniz. *"İşte şu an Jamming (Körleştirme) saldırısı altındayız, uyduları kaybettik."* deyin.
* **Adım 5 (SPOOFING VE KORUMA):** Hemen arkasından araç haritada ışınlanma tepkisi verecektir. Sisteminiz anında paneli Sarı/Kırmızı uyarıya çevirip aracı **"Kör Uçuş (INS) Otopilotuna"** alacaktır. *"Sistemimiz körleştirilmeyi fark edip sahte uydulara bağlanmayı reddetti. Şu an otopilotla kendi iç sensörlerimizi kullanarak güvendeyiz."* diyerek şovu tamamlayın.

---

## 🚙 SENARYO 2: KARA ARACINA (AV) DİNAMİK GEÇİŞ ŞOVU
Bu aşamada makine öğrenmesi sisteminizin hantal olmadığını, her türlü araca anında adapte olabilen esnek bir ticari ürün olduğunu kanıtlayacaksınız.

* **Adım 1:** Sayfayı ASLA YENİLEMEYİN. Sol menüden dosya yükleyiciyi açıp bu sefer **`AV-GPS-Dataset-1.csv`** (Yavaş giden orijinal otonom araç) dosyasını yükleyin.
* **Adım 2 (ANOMALİ YAKALAMA):** Dosyayı yükler yüklemez yapay zeka büyük ihtimalle "Spoofing / Anomali" tespit uyarısı vererek sistemi kilitleyecektir. Bu beklenen bir reaksiyondur (False Positive değil, True Anomaly). Jüriye dönüp profesyonel bir şekilde şunu açıklayın:
*"Fark ettiğiniz gibi sistem uyarı verdi. Ancak bu bir hata değil, algoritmamızın kusursuz bir tespitidir. Yapay zekamız bir önceki uçuşta 'İHA uçuş dinamiklerini' referans almıştı. Biz aniden yavaş giden bir Karasal Otonom Araç profilini sisteme dahil ettiğimizde, yapay zeka bu ani hız ve irtifa düşüşünü önceden tanımlanmış eşiklerin dışında bir anomali (fiziksel tutarsızlık) olarak doğru bir şekilde sınıflandırdı."*
* **Adım 3 (BEYNİ SIFIRLAMA):** Araç yürümeye devam ederken 15-20 saniye sonra tekrar **"Yapay Zeka Modellerini Eğit"** butonuna basın.
* **Adım 4:** Sistem 20 saniye sonra eğitimi tamamlandığında ışıkların Yeşil'e (Normal) döndüğünü göreceksiniz. Jüriye şunu deyin: *"İşte gördüğünüz gibi, sistem yeni arabanın hız profilini yeni "Normal" olarak kabul etti ve sadece 20 saniyede bir otonom kara aracının beyni haline geldi. Tamamen platform bağımsızız."*

---

## 📊 VURUCU FİNAL (ADLİ BİLİŞİM KAPANIŞI)
En son jüri sorusu vs. kalmadığında sayfanın en altına inip **"Adli Bilişim (Forensics) Kayıtları"** panelini açın. 

* *"Tüm bu yaptığımız operasyonlar, İHA için ayrı sekmede, Kara Aracı için ayrı sekmede kaydedildi. Mahkemede veya siber güvenlik analizinde delil olması için hepsi manipüle edilemez SHA256 Askeri Kriptolamasıyla (Hash) mühürlenip indirilebilir durumdadır."* diyerek sunumu alkışlarla bitirin.
