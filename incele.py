import os
import sys
import pandas as pd
import zipfile
import io

try:
    import scipy.io as sio
except ImportError:
    sio = None

def inspect_file(file_path):
    if not os.path.exists(file_path):
        print(f"[!] Hata: Dosya bulunamadi -> {file_path}")
        return

    ext = os.path.splitext(file_path)[1].lower()
    df = None

    print(f"\n[?] INCELENIYOR: {os.path.basename(file_path)}")
    print("-" * 50)

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext == ".mat":
            if sio is None:
                print("[!] Hata: 'scipy' kütüphanesi yüklü değil. 'pip install scipy' yazarak yükleyin.")
                return
            mat = sio.loadmat(file_path)
            # Anahtarları göster
            keys = [k for k in mat.keys() if not k.startswith("__")]
            print(f"[#] MATLAB Anahtarları: {keys}")
            # En büyük matrisi bul
            max_key = max(keys, key=lambda k: mat[k].size) if keys else None
            if max_key:
                print(f"[+] Secilen Veri Kümesi: '{max_key}'")
                df = pd.DataFrame(mat[max_key])
        elif ext == ".zip":
            with zipfile.ZipFile(file_path) as z:
                files = z.namelist()
                print(f"[#] ZIP Icerigi: {files}")
                target = next((f for f in files if f.lower().endswith((".csv", ".mat"))), None)
                if target:
                    print(f"[-] Okunan Dosya: {target}")
                    with z.open(target) as f:
                        if target.lower().endswith(".csv"):
                            df = pd.read_csv(f)
                        else:
                            if sio:
                                mat_in_zip = sio.loadmat(io.BytesIO(f.read()))
                                keys = [k for k in mat_in_zip.keys() if not k.startswith("__")]
                                max_key = max(keys, key=lambda k: mat_in_zip[k].size) if keys else None
                                df = pd.DataFrame(mat_in_zip[max_key])
        
        if df is not None:
            print(f"[OK] Basarili! {len(df)} satir ve {len(df.columns)} sutun bulundu.")
            print("\n[!] SUTUNLAR:")
            print(list(df.columns))
            print("\n[!] ILK 5 SATIR:")
            print(df.head())
        else:
            print("[!] Hata: Desteklenmeyen format veya bos dosya.")

    except Exception as e:
        print(f"[!] Hata olustu: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("💡 Kullanım: python incele.py \"DOSYA_YOLU\"")
    else:
        inspect_file(sys.argv[1])
