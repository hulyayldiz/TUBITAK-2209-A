import os
import urllib.request
import zipfile
import sys

TEXBAT_INFO_URL = "https://radionavlab.ae.utexas.edu/texbat/"
TARGET_DIR = "dataset_gercek/TEXBAT"

def download_texbat():
    print("=" * 60)
    print("🛰️ TEXBAT (Texas Spoofing Test Battery) Veri İndirici")
    print("=" * 60)
    
    print("\n[BİLGİ] TEXBAT veri setleri yüksek boyutlu IQ kayıtları ve işlenmiş CSV'lerden oluşur.")
    print("Resmi dağıtım UT Austin Radionavigation Laboratory tarafından yapılmaktadır.")
    print(f"Lütfen şu adresi ziyaret edip veri setini talep ediniz/indiriniz:\n{TEXBAT_INFO_URL}\n")
    
    # Yerel dizini oluştur
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    print(f"İndirdiğiniz 'texbat_data.zip' dosyasını lütfen '{TARGET_DIR}' klasörüne kopyalayınız.")
    
    zip_path = os.path.join(TARGET_DIR, "texbat_data.zip")
    if os.path.exists(zip_path):
        print(f"\n[İŞLEM] '{zip_path}' bulundu! Çıkartılıyor...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(TARGET_DIR)
            print("✅ Başarılı: Veri seti çıkartıldı. Artık simülasyon arayüzünden yükleyebilirsiniz.")
        except Exception as e:
            print(f"❌ Hata: ZIP dosyası çıkartılamadı: {e}")
    else:
        print("\n⏳ Bekleniyor: ZIP dosyası henüz bulunamadı. İndirip ilgili dizine attıktan sonra bu betiği tekrar çalıştırın.")

if __name__ == "__main__":
    download_texbat()
