"""
Merkezi Durum Yönetimi (State Management)
Simülasyonun tüm değişkenlerini merkezi bir yapıda toplar.
"""

import time
import uuid
import streamlit as st
import config

class SimulationState:
    """Simülasyonun tüm dinamik verilerini yöneten sınıf."""
    @staticmethod
    def initialize():
        """Session state değişkenlerini varsayılan değerlerle başlatır."""
        if "initialized_v10" not in st.session_state:
            # Başlangıç Konumları
            lat, lon = config.DEFAULT_LAT, config.DEFAULT_LON
            st.session_state.map_center = (lat, lon)
            st.session_state.true_lat = lat
            st.session_state.true_lon = lon
            st.session_state.prev_lat = lat
            st.session_state.prev_lon = lon
            st.session_state.render_lat = lat
            st.session_state.render_lon = lon
            st.session_state.last_good_lat = lat
            st.session_state.last_good_lon = lon
            
            # Dinamik Parametreler
            st.session_state.prev_speed = 40.0
            st.session_state.current_speed = 40.0
            st.session_state.prev_heading = 45.0
            st.session_state.acceleration = 0.0
            
            # Otopilot (INS) Durumu
            st.session_state.ins_active = False
            st.session_state.ins_lat = lat
            st.session_state.ins_lon = lon
            st.session_state.ins_speed = 40.0
            st.session_state.ins_start_time = 0.0
            st.session_state.ins_duration = 0.0
            st.session_state.ins_remaining = 0.0
            
            # Saldırı Yönetimi
            st.session_state.attack_mode = "normal"
            st.session_state.prev_attack_mode = "normal"
            st.session_state.is_attack_detected = False
            st.session_state.attack_start_time = time.time()
            st.session_state.auto_sim = False
            st.session_state.fw_state = True
            
            # Spoofing & Jamming Detayları
            st.session_state.spoof_offset_lat = 0.0
            st.session_state.spoof_offset_lon = 0.0
            st.session_state.spoof_drag_lat = lat
            st.session_state.spoof_drag_lon = lon
            
            # Veri Seti (Dataset)
            st.session_state.use_dataset_mode = False
            st.session_state.dataset_df = None
            st.session_state.dataset_index = 0
            st.session_state.col_map = {"lat": None, "lon": None, "speed": None, "snr": None, "attack": None}
            
            # Geçmiş Kayıtları (History)
            st.session_state.snr_history = [40.0] * 30
            st.session_state.residuals_history = [0.0] * 30
            st.session_state.route_history = []
            st.session_state.sim_logs = []
            st.session_state.live_logs = []
            st.session_state.dataset_logs_iha = []
            st.session_state.dataset_logs_arac = []
            
            # İstatistikler
            st.session_state.stats_tp = 0
            st.session_state.stats_fp = 0
            st.session_state.stats_tn = 0
            st.session_state.stats_fn = 0
            st.session_state.stats_response_times = []
            st.session_state.last_resp = 0.0
            
            # Teknik Ayarlar
            st.session_state.academic_mode = False
            st.session_state.cam_lock = False
            st.session_state.save_training_data = False
            st.session_state.training_session_id = uuid.uuid4().hex
            st.session_state.tcp_status = "Bekleniyor..."
            st.session_state.startup_time = time.time()
            st.session_state.vae_buffer = []
            st.session_state.force_reset = False
            st.session_state.attack_counts = {"Jamming": 0, "Spoofing": 0}
            st.session_state.last_log_hash = "0" * 64 # Başlangıç (Genesis) hash
            st.session_state.roc_history = []  # [(p_fa, p_d)] ROC eğrisi için birikimli veri
            st.session_state.inference_latency = 0.0  # ms cinsinden son inference süresi
            st.session_state.ins_history = []   # [[lon, lat]] INS rota çizgisi için
            st.session_state.render_counter = 0
            st.session_state.fused_lat = lat
            st.session_state.fused_lon = lon
            
            st.session_state.initialized_v10 = True

    @staticmethod
    def get():
        """Mevcut duruma erişim sağlar."""
        return st.session_state
