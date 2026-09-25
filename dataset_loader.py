"""
Veri Seti Oynatıcı Modülü (Dataset Playback Engine)
Dışarıdan yüklenen gerçek dünya uçuş ve saldırı loglarını (TEXBAT, NMEA, GPS Kaggle CSV'leri vb.)
okuyarak, Streamlit döngüsü boyunca sisteme canlı olarak (saniye saniye) besler.
"""
import pandas as pd
import io
import re
import unicodedata
import zipfile
import hashlib
try:
    import scipy.io as sio
except ImportError:
    sio = None


def normalize_column_name(name):
    if name is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(name))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9_]+", " ", normalized.lower()).strip()


def load_dataset_from_uploaded_file(uploaded_file, state):
    """Kullanıcının yüklediği dosyayı Pandas ile okuyup Session State'e kaydeder"""
    if uploaded_file is not None:
        try:
            # Sadece dosya değiştiyse yeniden oku
            if state.get("last_uploaded_filename") != uploaded_file.name:
                filename = uploaded_file.name.lower()
                df = None
                
                if filename.endswith(".csv"):
                    content = uploaded_file.getvalue().decode("utf-8")
                    df = pd.read_csv(io.StringIO(content))
                
                elif filename.endswith(".mat"):
                    if sio is None:
                        state.dataset_error = "MATLAB dosyalarını okumak için 'scipy' kütüphanesi yüklü olmalıdır."
                        return False
                    
                    mat_contents = sio.loadmat(io.BytesIO(uploaded_file.getvalue()))
                    df = _extract_mat_dataframe(mat_contents)
                    if df is None:
                        state.dataset_error = "MATLAB dosyası içinde veri tablosu bulunamadı."
                        return False

                elif filename.endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue())) as z:
                        df = _extract_zip_dataframe(z)
                        if df is None:
                            state.dataset_error = "ZIP içinde uygun bir veri dosyası (.csv veya .mat) bulunamadı."
                            return False
                
                if df is None:
                    state.dataset_error = "Desteklenmeyen dosya formatı veya boş veri."
                    return False

                return _process_dataset_dataframe(df, uploaded_file.name, state)
                
        except Exception as e:
            state.dataset_error = f"Veri okuma hatası: {e}"
            return False
    return True

def load_dataset_from_local_path(file_path, state):
    """Büyük dosyalar için yerel disk üzerinden doğrudan okuma yapar"""
    import os
    
    # Boş giriş kontrolü
    if not file_path or not file_path.strip():
        state.dataset_error = "Lütfen bir dosya yolu girin."
        return False

    clean_path = file_path.strip().strip('"') # Tırnakları temizle
    
    # Dosya varlık kontrolü
    if not os.path.exists(clean_path):
        # Uzantı unutulmuş olabilir, yaygın uzantıları dene
        for ext in ['.zip', '.mat', '.csv']:
            if os.path.exists(clean_path + ext):
                clean_path += ext
                break
        else:
            state.dataset_error = f"Hata: Dosya bulunamadı. Lütfen tam yolu ve uzantıyı (.zip vb.) kontrol edin.\nGirilen: {clean_path}"
            return False
        
    try:
        filename = os.path.basename(clean_path).lower()
        df = None
        
        if filename.endswith(".csv"):
            df = pd.read_csv(clean_path)
            
        elif filename.endswith(".mat"):
            if sio is None:
                state.dataset_error = "MATLAB dosyalarını okumak için 'scipy' kütüphanesi yüklü olmalıdır."
                return False
            mat_contents = sio.loadmat(clean_path)
            df = _extract_mat_dataframe(mat_contents)
            
        elif filename.endswith(".zip"):
            with zipfile.ZipFile(clean_path) as z:
                df = _extract_zip_dataframe(z)
                
        if df is None:
            state.dataset_error = f"'{filename}' formatı desteklenmiyor veya içeriği okunamadı. Lütfen .zip, .mat veya .csv dosyası seçtiğinizden emin olun."
            return False
            
        return _process_dataset_dataframe(df, os.path.basename(clean_path), state)
        
    except Exception as e:
        state.dataset_error = f"Yerel dosya okuma hatası: {str(e)}"
        return False

def _extract_mat_dataframe(mat_contents):
    """MAT içeriğinden en büyük diziyi DataFrame olarak seçer"""
    data_key = None
    max_size = -1
    for k, v in mat_contents.items():
        if not k.startswith("__"):
            if hasattr(v, 'size') and v.size > max_size:
                max_size = v.size
                data_key = k
    
    if data_key:
        data = mat_contents[data_key]
        if len(data.shape) == 2:
            df = pd.DataFrame(data)
            df.columns = [str(c) for c in df.columns]
            return df
    return None

def _extract_zip_dataframe(z_obj):
    """ZIP objesi içindeki ilk CSV veya MAT dosyasını bulur ve DF döner"""
    file_list = z_obj.namelist()
    for f_name in file_list:
        if f_name.lower().endswith(".csv"):
            with z_obj.open(f_name) as f:
                return pd.read_csv(f)
        elif f_name.lower().endswith(".mat"):
            if sio:
                with z_obj.open(f_name) as f:
                    mat_in_zip = sio.loadmat(io.BytesIO(f.read()))
                    return _extract_mat_dataframe(mat_in_zip)
    return None

def _process_dataset_dataframe(df, filename_label, state):
    """Okunan DataFrame'i temizler, sütun haritalamasını yapar ve state'e kaydeder"""
    # Sütun isimlerini tahmin etmeye/temizlemeye çalış (büyük/küçük harf duyarsız)
    original_columns = list(df.columns)
    normalized_columns = {c: normalize_column_name(c) for c in original_columns}

    state.dataset_df = df
    state.dataset_index = 0
    state.last_uploaded_filename = filename_label

    def match_column(patterns):
        for orig, norm in normalized_columns.items():
            if any(re.search(p, norm) for p in patterns):
                return orig
        return None

    # Sütunların varlığını kontrol et (esnek eşleştirme)
    state.col_map = {
        "lat": match_column([r"\blat\b", r"\benlem\b", r"\blatitude\b", r"gps latitude"]),
        "lon": match_column([r"\blon\b", r"\blong\b", r"\bboylam\b", r"\blongitude\b", r"gps longitude"]),
        "speed": match_column([r"\bspeed\b", r"\bvel\b", r"\bhiz\b", r"\bvelocity\b"]),
        "snr": match_column([r"\bsnr\b", r"\bsignal\b", r"\bcn0\b", r"\bcno\b"]),
        "attack": match_column([r"attack", r"spoof", r"jam", r"saldiri", r"label", r"status", r"data type", r"type"])
    }
    
    # Konum sıfırlamasını ilk satıra göre başlat
    if state.col_map["lat"] and state.col_map["lon"]:
        first_row = df.iloc[0]
        state.true_lat = float(first_row[state.col_map["lat"]])
        state.true_lon = float(first_row[state.col_map["lon"]])
        state.last_good_lat = state.true_lat
        state.last_good_lon = state.true_lon
        
        # Hız sıfırlaması (Ani ivme sıçramasını engeller)
        if state.col_map["speed"]:
            try:
                speed_val = float(first_row[state.col_map["speed"]])
                if "m/s" in state.col_map["speed"].lower():
                    speed_val *= 3.6
                state.prev_speed = speed_val
            except:
                pass
    
    # Veri Özeti (Summary) ekle
    state.dataset_summary = {
        "rows": len(df),
        "cols": len(df.columns),
        "filename": filename_label
    }
    
    return True

def get_next_dataset_row(state):
    """
    Kayıtlı DataFrame içerisinden sıradaki satırı döner.
    Başa sarma (Loop) özelliği ile sürekli akış sağlar.
    """
    df = state.get("dataset_df")
    if df is None:
        return None
        
    # Döngü Modu (Sürekli akış)
    if state.dataset_index >= len(df):
        state.dataset_index = 0

    row = df.iloc[state.dataset_index]
    state.dataset_index += 1
    
    cmap = state.get("col_map", {})
    
    def try_float(val, default):
        try: return float(val)
        except: return default

    # Güvenli okuma
    raw_lat = try_float(row[cmap["lat"]], getattr(state, "true_lat", 38.6744)) if cmap.get("lat") else getattr(state, "true_lat", 38.6744)
    raw_lon = try_float(row[cmap["lon"]], getattr(state, "true_lon", 39.1942)) if cmap.get("lon") else getattr(state, "true_lon", 39.1942)
    
    # Hız okuma ve birim çevirme (m/s -> km/sa)
    raw_speed = try_float(row[cmap["speed"]], getattr(state, "prev_speed", 84.0)) if cmap.get("speed") else getattr(state, "prev_speed", 84.0)
    if cmap.get("speed") and "m/s" in str(cmap["speed"]).lower():
        raw_speed *= 3.6
    raw_cn0 = try_float(row[cmap["snr"]], 40.0) if cmap.get("snr") else 40.0
    
    # Adli Bilişim İçin Hash Zincirleme (Hash Chaining)
    # Literatüre Uygunluk: Önceki hash + Mevcut Satır Verisi = Yeni Hash
    row_str = ",".join([str(x) for x in row])
    chain_input = f"{state.last_log_hash}{row_str}"
    state.current_row_hash = hashlib.sha256(chain_input.encode()).hexdigest()
    state.last_log_hash = state.current_row_hash # Zinciri bir sonraki adım için güncelle

    attack_raw = str(row[cmap["attack"]]).lower() if cmap.get("attack") else "normal"
    
    attack_mode = "normal"
    if any(x in attack_raw for x in ["spoof", "teleport", "drag", "meander", "1"]):
        attack_mode = "spoofing"
    elif any(x in attack_raw for x in ["jam", "2"]):
        attack_mode = "jamming"

    # ÖNEMLİ: Dataset verisi "Ground Truth" olarak kabul edilir eğer atak yoksa
    if attack_mode == "normal":
        state.true_lat = raw_lat
        state.true_lon = raw_lon

    return raw_lat, raw_lon, raw_speed, raw_cn0, attack_mode
