# HK-UrbanSpoof referans izleri

Projeye HK-UrbanSpoof deposunun S2 ve S3 post-processed GNSS/INS referans tabloları eklendi. Kaynak depodaki S2/S3 senaryo açıklamaları controlled urban spoofing verisi ve NovAtel SPAN-CPT referansından söz eder ([proje README](https://github.com/Fangjingxiaotao/HK-UrbanSpoof)). Bu dosyalar bağımsız GNSS/INS referans izidir; burada receiver NAV çıktısı değildir.

İndirilen dosyalar `dataset_gercek/external/hk_urban_spoof/` altındadır. `hk_urban_spoof_manifest.json` sabit Git commit'ini, kaynak adresini, bayt sayısını, Git blob SHA-1 ve SHA-256 özetlerini kaydeder. Depoda lisans bildirimi bulunmadığı için dosyalar yerel doğrulama amacıyla tutulmuştur; dağıtım veya yeniden yayımlama için lisans netleştirilmelidir.

`load_reference_track("S2")` / `load_reference_track("S3")` tabloyu doğrular, UTC epoch'larını parse eder ve koordinat, irtifa, hız bileşenleri ve tutumu kanonik sütunlara dönüştürür. `merge_hk_reference(receiver, reference, tolerance_s=0.1)` en yakın zaman damgasını seçer; tolerans dışındaki ölçümlere referans uydurmaz. Dönen `reference_lat` ve `reference_lon` mevcut dataset loader tarafından bağımsız referans olarak okunabilir. Referansın kendisi algılama girdisi sayılmamalı; yalnızca değerlendirme / konum hatası ölçümü için ayrılmalıdır.

**Algılama değerlendirmesi henüz yapılamıyor:** Her iki küçük dosya referans konumunu sağlar, fakat karşılık gelen saldırı altındaki receiver NAV çözümü bu projede yok. Depodaki ham IF kayıtları dosya başına yaklaşık 10–13 GB olduğundan indirilip işlenmedi. Bu nedenle adapter testlerinin geçmesi, küçük saldırıların tespit edildiğini veya kaçırma oranının düzeldiğini göstermez.

Yeniden üretim: `python download_hk_urbanspoof.py` eksik referans dosyalarını indirir ve pinned içerik özetleriyle doğrular. `python -m pytest tests/test_hk_urban_spoof.py -q` iki kaydı parse eder ve zaman eşleştirme toleransını denetler.
