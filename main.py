"""
Ana Yürütme Modülü (v10)
Tüm alt sistemleri (Sensörler, ML, UI, Devlet) koordine eder.
"""

import streamlit as st
import time
import random
import math
import logging
import hashlib
import os
import json
from datetime import datetime

# Merkezi Log Yapılandırması (Kriptografik Zincirleme Desteği)
FORENSIC_SECRET_KEY = os.getenv("FORENSIC_SECRET_KEY", "b'SECRET_TUBITAK_2209_KEY'").encode('utf-8')

def init_forensic_chain(state):
    """Sistem yeniden başlatıldığında hash zincirini diskten okur ve doğruluk kontrolü (Tampering Detection) yapar."""
    if "last_log_hash" not in state:
        state.last_log_hash = "0"*64
        jsonl_path = "forensic_ledger.jsonl"
        if os.path.exists(jsonl_path):
            try:
                import hmac
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    
                if not lines:
                    return
                
                # Zincir doğrulama işlemi (Tampering check)
                current_hash = "0"*64
                is_valid = True
                for i, line in enumerate(lines):
                    try:
                        log_obj = json.loads(line.strip())
                        log_content = f"{log_obj['timestamp']} - {log_obj['level']} - {log_obj['message']}"
                        salt = log_obj['salt']
                        chain_input = f"{current_hash}{log_content}{salt}".encode('utf-8')
                        calc_hash = hmac.new(FORENSIC_SECRET_KEY, chain_input, hashlib.sha256).hexdigest()
                        
                        if calc_hash != log_obj['chain_hmac']:
                            logging.critical(f"DİJİTAL DELİL BOZULMASI (TAMPERING TESPİT EDİLDİ): Satır {i+1} değiştirilmiş!")
                            is_valid = False
                            break
                        current_hash = calc_hash
                    except Exception as parse_err:
                        logging.critical(f"DİJİTAL DELİL BOZULMASI: Satır {i+1} okunamadı ({parse_err})")
                        is_valid = False
                        break
                        
                if is_valid:
                    state.last_log_hash = current_hash
                    logging.info("Dijital Delil Zinciri (Forensic Ledger) doğrulandı.")
                else:
                    # Bozulma durumunda zinciri kırılmış kabul edip devam etmesi veya güvenli moda alması
                    state.last_log_hash = current_hash # Kaldığı en son geçerli hash
            except Exception as e:
                logging.error(f"Adli bilişim zinciri yüklenemedi: {e}")

def log_chained_event(state, level, message):
    """
    Her log girişini bir önceki girişe bağlayan (Blockchain benzeri) adli kayıt sistemi.
    Format: [ZAMAN] [SEVİYE] [MESAJ | HMAC]
    """
    import hmac
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"{timestamp} - {level} - {message}"
    
    # Zincirleme: Yeni Hash = HMAC-SHA256(SecretKey, Eski Hash + Mevcut Log + Salt)
    salt = os.urandom(8).hex()
    chain_input = f"{state.last_log_hash}{log_content}{salt}".encode('utf-8')
    new_hash = hmac.new(FORENSIC_SECRET_KEY, chain_input, hashlib.sha256).hexdigest()
    state.last_log_hash = new_hash
    
    final_entry = f"{log_content} | SALT: {salt} | HMAC: {new_hash[:16]}..."
    
    # UI için state listesine ekle
    if "sim_logs" not in state: state.sim_logs = []
    state.sim_logs.insert(0, final_entry)
    if len(state.sim_logs) > 15: state.sim_logs.pop()
    
    # Kriptografik Adli Sicil (JSONL Loglama)
    log_obj = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "salt": salt,
        "chain_hmac": new_hash
    }
    
    # Kriptografik Adli Sicil (JSONL Loglama) - Rotasyon Destekli (Atomic)
    jsonl_path = "forensic_ledger.jsonl"
    if os.path.exists(jsonl_path) and os.path.getsize(jsonl_path) > 10 * 1024 * 1024:
        archive_name = f"forensic_ledger_{int(time.time())}.jsonl"
        try:
            os.replace(jsonl_path, archive_name) # Atomic operation on Windows/Linux
        except OSError:
            pass # Eğer o anda dosya kilitliyse bir sonraki tur dener
            
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_obj) + "\n")
    
    if level == "ERROR":
        logging.error(message)
    else:
        logging.warning(message)

import logging.handlers
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('system_events.log', maxBytes=10*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)

# Paket Importları
import config
from state import SimulationState
from sensors import simulate_sensors, update_ins_model, calculate_distance_km
from detection import run_firewall_rules, calculate_metrics
from satellites import load_all_satellites_logic_v2, get_live_sat_data, SAT_SYSTEMS
from ml_detection import get_hybrid_decision, log_training_data

# Modern Modüler UI Bileşenleri
from ui import render_ui_skeleton
from analytics import render_top_metrics, render_academic_metrics, render_expanders
from map_layers import render_map

# --- 1. Uygulama Başlatma ---
st.set_page_config(page_title="GNSS Savunma Sistemi", layout="wide")
SimulationState.initialize()
state = SimulationState.get()

if "attack_counts" not in state:
    state.attack_counts = {"Jamming": 0, "Spoofing": 0}

# Hash zincirini diskten başlat
init_forensic_chain(state)

# --- 2. Yardımcı Fonksiyonlar (Logic Separation) ---
def handle_attack_logic(state):
    """Saldırı zaman aşımı ve otomatik saldırı motorunu yönetir."""
    if state.attack_mode != "normal":
        elapsed = time.time() - state.attack_start_time
        if elapsed > config.GLOBAL_ATTACK_DURATION:
            state.attack_mode = "normal"
            state.is_attack_detected = False
            state.ins_active = False

    if state.get("auto_sim", False) and state.attack_mode == "normal":
        if random.random() < 0.03: # Tahmini saldırı frekansı
            state.attack_mode = random.choices(["jamming", "spoofing"], weights=[0.7, 0.3])[0]
            state.attack_start_time = time.time()

def process_navigation(state, raw_lat, raw_lon, raw_speed, raw_cn0, fw_active, conf_cn0_percent, conf_accel, dt=0.5):
    """Güvenlik duvarı ve navigasyon filtreleme mantığı."""
    attack_type, reason = run_firewall_rules(
        state, raw_lat, raw_lon, raw_cn0, raw_speed, config.NOMINAL_CN0, conf_cn0_percent, conf_accel, config.DEFAULT_HEADING_THRESHOLD, dt=dt)
    
    final_lat, final_lon, final_speed = raw_lat, raw_lon, raw_speed
    
    if attack_type != "NORMAL":
        if "JAMMING" in attack_type:
            if fw_active:
                # Jamming durumunda sinyal kaybolduğu için INS/Otopilot'a geç (Ataletsel Navigasyon)
                if not state.ins_active:
                    state.ins_active = True
                    state.ins_start_time = time.time()
                    state.ins_duration = 10.0 # Jamming için varsayılan 10sn koruma
                    state.ins_lat, state.ins_lon = state.last_good_lat, state.last_good_lon
                    state.ins_speed = getattr(state, "prev_speed", 40.0)
                    state.ins_heading = getattr(state, "prev_heading", 45.0)
                
                ins_elapsed = time.time() - state.ins_start_time
                if ins_elapsed < state.ins_duration:
                    state.ins_lat, state.ins_lon, final_speed = update_ins_model(state, dt=dt)
                    final_lat, final_lon = state.ins_lat, state.ins_lon
                    state.ins_remaining = state.ins_duration - ins_elapsed
                else:
                    state.ins_active = False # INS süresi dolunca dur (failsafe)
        
        elif attack_type == "SPOOFING":
            if fw_active:
                if not state.ins_active:
                    state.ins_active = True
                    state.ins_start_time = time.time()
                    state.ins_duration = random.uniform(config.INS_DURATION_MIN, config.INS_DURATION_MAX)
                    state.ins_lat, state.ins_lon = state.last_good_lat, state.last_good_lon
                    state.ins_speed = getattr(state, "prev_speed", 40.0)
                    state.ins_heading = getattr(state, "prev_heading", 45.0)
                
                ins_elapsed = time.time() - state.ins_start_time
                if ins_elapsed < state.ins_duration:
                    state.ins_lat, state.ins_lon, final_speed = update_ins_model(state, dt=dt)
                    final_lat, final_lon = state.ins_lat, state.ins_lon
                    state.ins_remaining = state.ins_duration - ins_elapsed
                else:
                    state.ins_active = False
    else:
        state.last_good_lat, state.last_good_lon = raw_lat, raw_lon
        state.ins_active = False

    return final_lat, final_lon, final_speed, attack_type, reason

# --- 3. Ana Arayüz ve Döngü ---
fw_active, conf_cn0, conf_accel, conf_heading = render_ui_skeleton(state)

# Uydu Verisi Yükleme
all_sats_db = load_all_satellites_logic_v2()
sat_data = []
if not state.academic_mode and all_sats_db:
    sat_data = get_live_sat_data(list(SAT_SYSTEMS.keys()), all_sats_db)

@st.fragment(run_every=0.5)
def main_simulation_loop(sat_data_ref):
    """Her saniye çalışan çekirdek simülasyon döngüsü (10 Hz)."""
    try:
        # A. Mantıksal İşlemler
        handle_attack_logic(state)
        
        # B. Sensör Okuma
        raw_lat, raw_lon, raw_speed, raw_cn0 = simulate_sensors(
            state, 
            use_live_gps=state.get("use_live_gps", False),
            port=state.get("gps_port", "COM3"),
            tcp_port=state.get("tcp_port", 9000),
            dt=0.5 # 2 Hz döngü süresine uyarlandı (run_every=0.5)
        )
        
        # C. Navigasyon ve Filtreleme
        f_lat, f_lon, f_speed, a_type, reason = process_navigation(state, raw_lat, raw_lon, raw_speed, raw_cn0, fw_active, conf_cn0, conf_accel, dt=0.5)
        
        # Rota geçmişini kaydet (Haritadaki iz için)
        if "route_history" not in state: state.route_history = []
        state.route_history.append((f_lat, f_lon))
        if len(state.route_history) > 200: state.route_history.pop(0)
        
        # D. Kararlılık Kayıtları (Grafikler için)
        res_err = math.sqrt((raw_lat - state.last_good_lat)**2 + (raw_lon - state.last_good_lon)**2) * 111000
        state.residuals_history.append(res_err)
        if len(state.residuals_history) > 30: state.residuals_history.pop(0)
        
        state.snr_history.append(raw_cn0)
        if len(state.snr_history) > 30: state.snr_history.pop(0)
        
        ml_features = [raw_cn0, getattr(state, 'acceleration', 0.0), abs(state.get('prev_heading', 45.0) - 45.0), res_err]
        state.vae_buffer.append(ml_features)
        if len(state.vae_buffer) > 10: state.vae_buffer.pop(0)

        final_type, conf, ml_label, anomaly = get_hybrid_decision(a_type, ml_features, state, state.vae_buffer)
        pd, pfa, prec, f1, ttd, rmse = calculate_metrics(state, a_type, raw_lat, raw_lon, f_lat, f_lon)
        
        # Fragment zaten saniyede 2 kez (0.5s) çalıştığı için her tick'te render edebiliriz.
        state.render_counter = getattr(state, "render_counter", 0) + 1
        ui_update_tick = True
        
        if ui_update_tick:
            # E. UI Güncelleme
            render_top_metrics(state, f_speed, raw_cn0, fw_active)
            
            # Canlı veya Dataset Loglarını Popüle Et
            log_text = f"📍 {datetime.now().strftime('%H:%M:%S')} - Lat: {raw_lat:.5f}, Lon: {raw_lon:.5f}, C/N0: {raw_cn0:.1f}"
            if state.get("use_live_gps", False):
                state.live_logs.insert(0, log_text)
                if len(state.live_logs) > 10: state.live_logs.pop()
            elif state.get("use_dataset_mode", False):
                state.dataset_logs_iha.insert(0, log_text)
                if len(state.dataset_logs_iha) > 10: state.dataset_logs_iha.pop()
            
            c_map, c_info = st.columns([2, 1])
            with c_map:
                render_map(state, state.true_lat, state.true_lon, raw_lat, raw_lon, f_lat, f_lon, not state.academic_mode, sat_data_ref, a_type)
            
            with c_info:
                st.subheader("🛡️ Hibrit Karar Motoru")
                if a_type == "NORMAL":
                    st.success("✅ Sistem Stabil: Tehdit Yok")
                else:
                    st.error(f"🚨 {a_type} TESPİT EDİLDİ!")
                    st.info(f"💡 Neden: {reason}")
                    
                    # Saldırı değiştiyse veya yeni başladıysa logla (Dosya şişmesini önle)
                    if getattr(state, "prev_attack_mode", "NORMAL") != a_type:
                        log_chained_event(state, "WARNING", f"Durum Değişimi: {a_type} Tespiti | Model: {ml_label}")
                
                st.markdown("---")
                render_academic_metrics(pd, pfa, prec, f1, ttd, rmse)
    
            render_expanders(state)
        
        # F. Durum Güncellemesi ve Saldırı Takibi
        state.prev_attack_mode = a_type 
        state.prev_lat = raw_lat
        state.prev_lon = raw_lon
        state.prev_speed = raw_speed
        if "current_heading" in state:
            state.prev_heading = state.current_heading

    except Exception as e:
        st.error(f"⚠️ Simülasyon Döngü Hatası: {str(e)}")
        # Hata loguna da düşür (forensic analiz için)
        log_chained_event(state, "ERROR", f"Fragment Hatası: {str(e)}")

# Döngüyü Başlat
main_simulation_loop(sat_data)
