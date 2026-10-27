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
from pathlib import Path
from dataset_adapters import mat_dataframe, zip_dataframe
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
            digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
            if state.get("last_uploaded_digest") != digest:
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

                if filename.endswith('.mat') and df.attrs.get('source', {}).get('adapter') == 'texbat-grid-v1':
                    from real_data_catalog import declared_grid_profile
                    df.attrs['source']['receiver_profile'] = declared_grid_profile(digest)
                result = _process_dataset_dataframe(df, uploaded_file.name, state)
                if result:
                    state.last_uploaded_digest = digest
                return result
                
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
        if not filename.endswith(('.csv', '.mat', '.zip')):
            raise ValueError('Desteklenen biçimler CSV, tanınan MAT ve ZIP paketleridir. '
                             'Ham IQ/BIN önce GNSS alıcısıyla işlenmelidir; alanlar tahmin edilmez.')
        from real_data_catalog import verify_source_file
        source_digest = verify_source_file(clean_path)
        
        if filename.endswith(".csv"):
            df = pd.read_csv(clean_path)
            
        elif filename.endswith(".mat"):
            if sio is None:
                state.dataset_error = "MATLAB dosyalarını okumak için 'scipy' kütüphanesi yüklü olmalıdır."
                return False
            mat_contents = sio.loadmat(clean_path)
            channel_path = Path(clean_path).with_name('channel.mat')
            channel = sio.loadmat(channel_path) if channel_path.is_file() else None
            df = mat_dataframe(mat_contents, channel)
            
        elif filename.endswith(".zip"):
            with zipfile.ZipFile(clean_path) as z:
                df = _extract_zip_dataframe(z)
                
        if df is None:
            state.dataset_error = f"'{filename}' formatı desteklenmiyor veya içeriği okunamadı. Lütfen .zip, .mat veya .csv dosyası seçtiğinizden emin olun."
            return False
            
        if filename.endswith('.mat') and df.attrs.get('source', {}).get('adapter') == 'texbat-grid-v1':
            from real_data_catalog import declared_grid_profile
            df.attrs['source']['receiver_profile'] = declared_grid_profile(source_digest)
        result = _process_dataset_dataframe(df, str(Path(clean_path).resolve()), state)
        if result:
            state.last_uploaded_digest = source_digest
        return result
        
    except Exception as e:
        state.dataset_error = f"Yerel dosya okuma hatası: {str(e)}"
        return False

def _extract_mat_dataframe(mat_contents):
    """Decode known schemas only; matrix size does not identify field meaning."""
    return mat_dataframe(mat_contents)

def _extract_zip_dataframe(z_obj):
    """Dispatch a source bundle or require an unambiguous canonical CSV."""
    return zip_dataframe(z_obj)

def parse_attack_label(value):
    label = str(value).strip().lower()
    mapping = {"0":"normal", "0.0":"normal", "normal":"normal", "benign":"normal",
               "1":"spoofing", "1.0":"spoofing", "spoofing":"spoofing", "spoof":"spoofing",
               "2":"jamming", "2.0":"jamming", "jamming":"jamming", "jamming_warning":"jamming"}
    if label not in mapping:
        raise ValueError(f"Bilinmeyen saldırı etiketi: {value}")
    return mapping[label]


def _process_dataset_dataframe(df, filename_label, state):
    """Validate first, then replace the current stream atomically in session state."""
    import math
    if df.empty:
        raise ValueError("Veri dosyası boş")
    from dataset_adapters import CMU_COLUMNS, cmu_flight_dataframe
    if CMU_COLUMNS.issubset(df.columns):
        df = cmu_flight_dataframe(df)
    normalized = {column: normalize_column_name(column) for column in df.columns}
    aliases = {"lat":["lat", "latitude", "gps latitude", "enlem"],
               "lon":["lon", "long", "longitude", "gps longitude", "boylam"],
               "speed":["speed", "speed_kmh", "speed_m_s", "speed_mps", "velocity", "velocity m s", "hiz"],
               "snr":["cn0", "cno", "snr", "sinyal gucu snr"],
               "attack":["label", "target_label", "attack", "attack_label", "data type", "attack_mode"]}
    def match(names):
        for name in names:
            for original, norm in normalized.items():
                if norm == name:
                    return original
        return None
    cmap = {key: match(names) for key, names in aliases.items()}
    if not all(cmap[key] is not None for key in ("lat", "lon", "speed")):
        raise ValueError("Enlem, boylam ve hız sütunları gerekli; eksik ölçüm üretilmez")
    df = df.copy()
    for key in ("lat", "lon", "speed"):
        values = pd.to_numeric(df[cmap[key]], errors="coerce")
        if not values.map(math.isfinite).all():
            raise ValueError(f"Geçersiz/eksik sayısal sütun: {cmap[key]}")
        df[cmap[key]] = values
    if not df[cmap["lat"]].between(-89.999, 89.999).all() or not df[cmap["lon"]].between(-180,180).all():
        raise ValueError("Koordinatlar desteklenen aralığın dışında")
    if (df[cmap["speed"]] < 0).any():
        raise ValueError("GNSS yer hızı negatif olamaz")
    if cmap["attack"] is not None:
        for value in df[cmap["attack"]]:
            parse_attack_label(value)
    sample_times = None
    if "Run Time" in df.columns:
        clock = pd.to_timedelta(df["Run Time"], errors="coerce").dt.total_seconds()
    elif "timestamp_s" in df.columns:
        clock = pd.to_numeric(df["timestamp_s"], errors="coerce")
    elif "timestamp" in df.columns:
        stamps = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        clock = (stamps-stamps.iloc[0]).dt.total_seconds()
    else:
        clock = None
    if clock is not None:
        if not clock.map(math.isfinite).all():
            raise ValueError("Geçersiz zaman damgası")
        groups = clock.ne(clock.shift()).cumsum()
        retained = df.groupby(groups, sort=False).tail(1).index
        sample_times = clock.loc[retained].tolist()
        df = df.loc[retained].reset_index(drop=True)
    from domain_model import av_features
    from receiver_registry import source_contract
    source = source_contract(df, df.attrs.get('source', {}))
    df.attrs['source'] = source
    metadata = dict(dataset_df=df, dataset_index=0, col_map=cmap,
        receiver_profile_name=source.get('receiver_profile'),
        receiver_identity=dict(receiver_id=source.get('receiver_id'), motion=source.get('receiver_motion')),
        dataset_kinematic_features=av_features(df), dataset_sample_times=sample_times,
        dataset_previous_time=None, dataset_dt_assumed=sample_times is None,
        sample_dt=.5, vae_buffer=[], vae_anomaly_streak=0, rf_anomaly_streak=0, spoof_persistence=0,
        previous_observed_cn0=None, ins_active=False, kinematic_features=None,
        stats_tp=0, stats_fp=0, stats_tn=0, stats_fn=0, stats_response_times=[],
        is_attack_detected=False, rmse_buffer=[], last_uploaded_filename=filename_label,
        dataset_summary=dict(rows=len(df), cols=len(df.columns), filename=filename_label,
            adapter=source.get('adapter', 'csv-column-mapping'), source=source,
            capabilities=dict(cn0=cmap['snr'] is not None, attack_labels=cmap['attack'] is not None,
                              independent_imu=source.get('independent_imu', False)),
            time_unit='seconds', speed_unit='km/h at playback'))
    for key, value in metadata.items():
        state[key] = value
    state.pop("ekf_filter", None)
    state.pop("inertial_monitor", None)
    state.pop("gnss_quarantine_until", None)
    state.pop("inertial_reference_seeded", None)
    state.pop("inertial_hold_until", None)
    state.pop('last_dataset_hash', None)
    state.pop('active_navigation_source', None)
    state.pop('receiver_profile_monitor', None)
    state.pop('receiver_profile_result', None)
    state.pop('receiver_profile_version', None)
    state.pop('code_carrier_monitor', None)
    state.pop('code_carrier_version', None)
    state.pop('speed_accuracy_m_s', None)
    state.pop('previous_speed_accuracy_m_s', None)
    state.pop('horizontal_accuracy_m', None)
    _initialize_dataset_position(state, df.iloc[0])
    return True


def _speed_factor(column):
    name = str(column).lower()
    return 3.6 if "m/s" in name or name in ("speed_m_s", "speed_mps") else 1.


def _initialize_dataset_position(state, row):
    cmap = state.col_map
    state.prev_lat = state.true_lat = state.last_good_lat = float(row[cmap["lat"]])
    state.prev_lon = state.true_lon = state.last_good_lon = float(row[cmap["lon"]])
    state.prev_speed = float(row[cmap["speed"]])*_speed_factor(cmap["speed"])
    heading = row.get("GPS Course", row.get("heading_deg", 0.))
    state.prev_heading = float(heading) if pd.notna(heading) else 0.


def get_next_dataset_row(state):
    import math
    from imu_processing import navigation_imu
    df = state.get("dataset_df")
    if df is None or df.empty or state.dataset_index >= len(df):
        return None
    index = state.dataset_index
    row = df.iloc[index]
    state.dataset_index += 1
    clocks = state.get("dataset_sample_times")
    now = clocks[index] if clocks is not None else index*.5
    previous = state.get("dataset_previous_time")
    state.sample_dt = now-previous if previous is not None and now > previous else .5
    state.dataset_clock_reset = previous is not None and now < previous
    state.dataset_previous_time, state.sample_time_s = now, now
    state.receiver_observables = {column: float(row[column]) for column in
        ('receiver_clock_bias_m', 'receiver_clock_drift_m_s') if column in row.index}
    # u-blox MON-RF is an explicit receiver-side RF measurement. Preserve
    # missing values as unavailable; zero is meaningful only for a valid field.
    rf_columns = ('receiver_jamming_state', 'receiver_jam_indicator',
                  'receiver_noise_per_ms', 'receiver_agc_count', 'receiver_fix_valid')
    state.receiver_rf_observables = {}
    for column in rf_columns:
        value = row.get(column)
        if value is not None and pd.notna(value) and math.isfinite(float(value)):
            state.receiver_rf_observables[column.removeprefix('receiver_')] = float(value)
    if state.dataset_clock_reset:
        state.pop('receiver_profile_monitor', None)
        state.pop('code_carrier_monitor', None)
        state.pop('speed_accuracy_m_s', None)
        state.pop('previous_speed_accuracy_m_s', None)
        for key in ("ekf_filter", "inertial_monitor", "gnss_quarantine_until", "inertial_reference_seeded", "inertial_hold_until"):
            state.pop(key, None)
        state.vae_buffer, state.vae_anomaly_streak, state.spoof_persistence = [], 0, 0
        state.rf_anomaly_streak = 0
        state.ins_active, state.is_attack_detected = False, False
        _initialize_dataset_position(state, row)
    kinematic = state.get("dataset_kinematic_features")
    state.kinematic_features = kinematic.iloc[index].to_numpy(dtype=float).tolist() if kinematic is not None else None
    cmap = state.col_map
    state.ground_truth_available = cmap.get("attack") is not None
    lat, lon = float(row[cmap["lat"]]), float(row[cmap["lon"]])
    speed = float(row[cmap["speed"]])*_speed_factor(cmap["speed"])
    try:
        cn0 = float(row[cmap["snr"]]) if cmap.get("snr") is not None else float("nan")
    except (ValueError, TypeError):
        cn0 = float("nan")
    state.cn0_available = math.isfinite(cn0) and 0 <= cn0 <= 99
    if not state.cn0_available:
        cn0 = float("nan")
    state.previous_speed_accuracy_m_s = state.get('speed_accuracy_m_s')
    for column in ('speed_accuracy_m_s', 'horizontal_accuracy_m'):
        value = row.get(column)
        state[column] = (float(value) if value is not None and pd.notna(value)
                         and math.isfinite(float(value)) and float(value) > 0 else None)
    state.imu_data = {}
    imu_present = str(row.get('imu_available', True)).lower() in ('true', '1')
    if imu_present and all(column in row.index for column in ("imu_ax_m_s2", "imu_ay_m_s2")):
        accel = {"x":float(row["imu_ax_m_s2"]), "y":float(row["imu_ay_m_s2"]),
                 "z":float(row.get("imu_az_m_s2", 9.80665))}
        if not all(math.isfinite(value) for value in accel.values()):
            raise ValueError("Geçersiz IMU ölçümü")
        # Navigation-frame input is an explicit file contract, never inferred.
        state.imu_data = dict(accel=accel, real=True, frame=str(row.get("imu_frame", "body")))
        if str(row.get("heading_independent", "false")).lower() in ("true", "1") and "imu_heading_deg" in row.index:
            state.imu_data.update(heading_deg=float(row["imu_heading_deg"]), heading_independent=True)
        if all(column in row.index for column in ("roll_deg", "pitch_deg", "yaw_deg")):
            state.imu_data["attitude"] = dict(roll_deg=float(row["roll_deg"]), pitch_deg=float(row["pitch_deg"]),
                yaw_deg=float(row["yaw_deg"]), convention=str(row.get("attitude_convention", "")), valid=True,
                heading_independent=str(row.get("heading_independent", "false")).lower() in ("true", "1"))
        state.imu_data = navigation_imu(state.imu_data)
    state.reference_position = None
    if all(column in row.index for column in ("reference_lat", "reference_lon")):
        reference = float(row["reference_lat"]), float(row["reference_lon"])
        if (not all(math.isfinite(value) for value in reference)
                or not -89.999 <= reference[0] <= 89.999 or not -180 <= reference[1] <= 180):
            raise ValueError("Geçersiz referans konum")
        state.reference_position = reference
    row_str = ",".join(map(str, row))
    state.current_row_hash = hashlib.sha256(f"{state.get('last_dataset_hash', '0'*64)}{row_str}".encode()).hexdigest()
    state.last_dataset_hash = state.current_row_hash
    label = parse_attack_label(row[cmap["attack"]]) if state.ground_truth_available else "normal"
    return lat, lon, speed, cn0, label
