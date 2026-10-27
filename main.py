"""
Ana Yürütme Modülü (v10)
Tüm alt sistemleri (Sensörler, ML, UI, Devlet) koordine eder.
"""

import streamlit as st
import time
import random
import logging
import logging.handlers
import os
from datetime import datetime
import config

from forensic_config import load_forensic_key, FORENSIC_LEDGER_PATH

def init_forensic_chain(state):
    from forensic_ledger import Ledger
    try:
        head, _ = Ledger(FORENSIC_LEDGER_PATH, load_forensic_key()).verify()
        state.last_log_hash = head
        state.forensic_chain_valid = True
    except (ValueError, OSError, TimeoutError) as error:
        state.forensic_chain_valid = False
        logging.error("Adli zincir doğrulanamadı: %s", error)


def log_chained_event(state, level, message):
    from forensic_ledger import Ledger
    if not state.get("forensic_chain_valid", False):
        return
    try:
        entry = Ledger(FORENSIC_LEDGER_PATH, load_forensic_key()).append(level, message)
    except (ValueError, OSError, TimeoutError) as error:
        state.forensic_chain_valid = False
        logging.error("Adli kayıt yazılamadı: %s", error)
        return
    state.last_log_hash = entry["chain_hmac"]
    if "sim_logs" not in state:
        state.sim_logs = []
    state.sim_logs.insert(0, f"{entry['timestamp']} - {level} - {message} | HMAC: {entry['chain_hmac'][:16]}...")
    del state.sim_logs[15:]

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

def run_app():
    """Streamlit arayüzünü ve 2 Hz uygulama döngüsünü başlatır."""
    import torch

    torch.set_num_threads(max(1, int(os.getenv("GNSS_INFERENCE_THREADS", "1"))))
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.handlers.RotatingFileHandler('system_events.log', maxBytes=10*1024*1024, backupCount=3),
            logging.StreamHandler()
        ]
    )

    from state import SimulationState
    from sensors import simulate_sensors
    from satellites import load_all_satellites_logic_v2, get_live_sat_data, SAT_SYSTEMS
    from ui import render_app_shell
    from analytics import render_top_metrics, render_evaluation_metrics, render_expanders
    from map_layers import render_map
    from ai_assistant import show_ai_chat
    from dataset_loader import get_next_dataset_row
    from simulation import process_observation

    st.set_page_config(page_title="GNSS Savunma Sistemi", layout="wide")
    SimulationState.initialize()
    state = SimulationState.get()

    if "attack_counts" not in state:
        state.attack_counts = {"Jamming": 0, "Spoofing": 0}

    # Hash zincirini diskten başlat
    init_forensic_chain(state)
    if not state.get("forensic_chain_valid", False):
        st.warning("Adli kayıt zinciri veya bağlı arşivi doğrulanamadı. Anahtarı ve kayıt bütünlüğünü kontrol edin; zincire yeni kayıt eklenmiyor.")

    # Arayüz ve döngü, run_app çağrısı dışında oluşturulmaz.
    fw_active, conf_cn0, conf_accel, conf_heading = render_app_shell(state)

    all_sats_db = load_all_satellites_logic_v2()
    sat_data = []
    if not state.academic_mode and all_sats_db:
        sat_data = get_live_sat_data(list(SAT_SYSTEMS.keys()), _all_sats_db=all_sats_db)

    @st.fragment(run_every=0.5)
    def main_simulation_loop(sat_data_ref):
        """0.5 saniye aralıklarla çalışan çekirdek simülasyon döngüsü (2 Hz)."""
        try:
            # A. Mantıksal İşlemler
            if not state.get("use_live_gps", False) and not state.get("use_dataset_mode", False):
                handle_attack_logic(state)

            # B. Sensör Okuma
            sample_dt = .5
            if state.get("use_dataset_mode", False):
                observation = get_next_dataset_row(state)
                if observation is None:
                    st.info("Veri kaydı tamamlandı veya henüz veri yüklenmedi.")
                    return
                raw_lat, raw_lon, raw_speed, raw_cn0, label = observation
                sample_dt = state.get("sample_dt", .5)
                if state.get("dataset_dt_assumed", False):
                    st.caption("Kayıtta zaman bilgisi yok; örnek aralığı 0.5 saniye varsayılıyor.")
                if label != state.attack_mode or state.get("dataset_clock_reset", False):
                    state.attack_start_time = time.time()
                    state.attack_start_sample_time = state.get("sample_time_s")
                    state.is_attack_detected = False
                state.attack_mode = label
                state.acceleration = 0.
            else:
                observation = simulate_sensors(
                    state, use_live_gps=state.get("use_live_gps", False),
                    gps_mode=state.get("gps_mode", "Seri"),
                    port=state.get("gps_port", "COM3"), tcp_port=state.get("tcp_port", 9000), dt=sample_dt)
                if observation is None:
                    st.warning("GNSS verisi bekleniyor; simülasyon verisi kullanılmıyor.")
                    return
                raw_lat, raw_lon, raw_speed, raw_cn0 = observation
                state.kinematic_features = None
                if state.get("use_live_gps", False):
                    sample_dt = state.get("sample_dt", .5)
            source = (("dataset", state.get("last_uploaded_filename"), state.get("last_uploaded_digest"))
                      if state.get("use_dataset_mode", False) else
                      ("live", state.get("gps_mode"), state.get("gps_port"), state.get("tcp_port"))
                      if state.get("use_live_gps", False) else ("simulation",))
            if state.get("active_navigation_source") != source:
                if source[0] != 'dataset':
                    for key in ('speed_accuracy_m_s', 'previous_speed_accuracy_m_s',
                                'horizontal_accuracy_m', 'receiver_profile_name',
                                'receiver_profile_monitor', 'receiver_profile_result',
                                'code_carrier_monitor', 'code_carrier_version'):
                        state.pop(key, None)
                    state.receiver_observables = {}
                if source[0] != "live":
                    serial_manager = state.pop("gps_serial_manager", None)
                    if serial_manager is not None and serial_manager.ser is not None:
                        serial_manager.ser.close()
                    socket_manager = state.pop("gps_socket_manager", None)
                    if socket_manager is not None:
                        socket_manager.close()
                    state.nmea_parsers = {}
                    state.pop("last_live_sample_time", None)
                for key in ("ekf_filter", "inertial_monitor", "previous_observed_cn0", "gnss_quarantine_until", "inertial_reference_seeded", "inertial_hold_until"):
                    state.pop(key, None)
                state.vae_buffer, state.vae_anomaly_streak, state.spoof_persistence = [], 0, 0
                state.rf_anomaly_streak = 0
                state.ins_active, state.is_attack_detected = False, False
                state.prev_lat, state.last_good_lat = raw_lat, raw_lat
                state.prev_lon, state.last_good_lon = raw_lon, raw_lon
                state.prev_speed = raw_speed
                state.simulation_time = 0.
                state.reference_position = state.get("reference_position") if state.get("use_dataset_mode", False) else None
                for counter in ("stats_tp", "stats_fp", "stats_tn", "stats_fn"):
                    state[counter] = 0
                state.stats_response_times, state.rmse_buffer = [], []
                state.active_navigation_source = source
            if state.get("use_dataset_mode", False):
                state.navigation_time = state.sample_time_s
            elif state.get("use_live_gps", False):
                state.navigation_time = time.monotonic()
            else:
                state.simulation_time = state.get("simulation_time", 0.) + sample_dt
                state.navigation_time = state.simulation_time
            if not state.get("cn0_available", True):
                st.info("C/N0 ölçümü yok: sinyal tabanlı RF/VAE kapalı; mevcutsa ayrı kinematik model kullanılıyor.")

            # C. Tek örneğin algılama, navigasyon ve metrik hesabı
            result = process_observation(
                state, (raw_lat, raw_lon, raw_speed, raw_cn0), sample_dt,
                (conf_cn0, conf_accel, conf_heading, fw_active))
            final_type = result.decision
            reason = result.reason
            conf, ml_label, anomaly = result.confidence, result.model_label, result.anomaly_score
            f_lat, f_lon, f_speed = result.latitude, result.longitude, result.speed
            pd, pfa, prec, f1, ttd, rmse = result.metrics

            if state.get('ml_source') in ('TEXBAT_RECEIVER_PROFILE', 'RECEIVER_PROFILE'):
                receiver_result = state.get('receiver_profile_result', {})
                st.caption('Alıcı profili: ' + receiver_result.get('profile_id', str(state.get('receiver_profile_name')))
                           + ' | ' + receiver_result.get('status', 'unavailable'))
                if receiver_result.get('available') and not receiver_result.get('fully_assessed', False):
                    remaining = receiver_result.get('warmup_remaining_s', 0.)
                    names = dict(position_rate_m_s='konum değişimi', clock_rate_m_s='saat kayması değişimi',
                                 cn0_change_db='sinyal gücü değişimi', reported_clock_drift_m_s='anlık saat sürüklenmesi')
                    checked = ', '.join(names.get(name, name) for name in receiver_result.get('assessed_features', [])) or 'henüz yok'
                    st.info(f'Alıcı edinimi: {remaining:.1f} s kaldı. Değerlendirilen özellikler: {checked}. '
                            'Pencere kontrolleri tamamlanmadı; fiziksel kurallar çalışmaya devam ediyor.')
                if not receiver_result.get('available', False):
                    st.warning('Alıcı profili kullanılamıyor: ' + receiver_result.get('reason', 'Bilinmeyen hata'))
            elif state.get("cn0_available", True) and not state.get("rf_available", False):
                st.warning("RF modeli kullanılamıyor; mevcut diğer karar katmanları çalışıyor.")
            if (state.get('ml_source') not in ('TEXBAT_RECEIVER_PROFILE', 'RECEIVER_PROFILE')
                    and state.get("cn0_available", True) and not state.get("vae_available", False)):
                st.warning("VAE modeli kullanılamıyor; anomali katmanı devre dışı.")
            if (state.get("use_live_gps", False) or state.get("use_dataset_mode", False)) and not state.get("imu_navigation_available", False):
                st.info("Bağımsız IMU navigasyon ivmesi yok: GPS kesintisindeki çıktı doğrulanmış ataletsel navigasyon sayılmaz.")
            if state.get("ins_degraded", False):
                st.warning("GNSS uzun süredir reddediliyor; ataletsel tahmin belirsizliği artıyor. Bağımsız konum doğrulaması gerekli.")
            # INS Rota Geçmişi (Haritada Sarı Çizgi için)
            if state.get("ins_active", False):
                if "ins_history" not in state: state.ins_history = []
                state.ins_history.append([f_lon, f_lat])
                if len(state.ins_history) > 60: state.ins_history.pop(0)
            else:
                # INS bitti, geçmişi temizle
                if state.get("ins_history"):
                    state.ins_history = []


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
                    render_map(state, state.true_lat, state.true_lon, raw_lat, raw_lon, f_lat, f_lon, not state.academic_mode, sat_data_ref, final_type)

                with c_info:
                    st.subheader("🛡️ Hibrit Karar Motoru")
                    if final_type == "NORMAL":
                        st.success("✅ İzleme: Etkin ölçütlerde alarm yok")
                    elif final_type == "GNSS_FIX_LOSS":
                        st.warning("⚠️ GNSS Çözüm Kaybı: Olası girişim; saldırı nedeni doğrulanmadı")
                        st.info(reason)
                    else:
                        if final_type in ("JAMMING", "SPOOFING"):
                            st.error(f"🚨 {final_type} ile uyumlu ölçüm uyarısı; saldırı nedeni doğrulanmış değildir")
                        else:
                            st.error(f"🚨 Algılayıcı uyarısı: {final_type}")
                        source_info = reason if final_type != "NORMAL" else f"YZ Modeli: {ml_label} (Anomali: {anomaly:.4f})"
                        score_text = ("Kalibre edilmiş olasılık üretilmedi" if conf is None else
                                      f"Karar skoru: {conf:.1f} (kalibre olasılık değildir)")
                        st.info(f"💡 Neden / Model: {source_info} | {score_text}")

                        # Saldırı değiştiyse veya yeni başladıysa logla (Dosya şişmesini önle)
                        if state.get("last_detection_type", "NORMAL") != final_type:
                            log_chained_event(state, "WARNING", f"Durum Değişimi: {final_type} Tespiti | Model: {ml_label}")

                    st.markdown("---")
                    render_evaluation_metrics(pd, pfa, prec, f1, ttd, rmse)

                    # Genel amaçlı yerel sohbeti geniş pencerede aç.
                    if st.button(
                        "🐺 Bozkurt AI Asistanı",
                        icon=":material/chat:",
                        width="stretch",
                        key="open_bozkurt_chat",
                    ):
                        show_ai_chat(state)

                render_expanders(state, pd, pfa)

            # F. Durum Güncellemesi ve Saldırı Takibi
            state.last_detection_type = final_type
            state.prev_attack_mode = state.attack_mode
            state.prev_lat = raw_lat
            state.prev_lon = raw_lon
            state.prev_speed = raw_speed
            state.prev_heading = state.get("observed_heading", state.prev_heading)

        except Exception as e:
            st.error(f"⚠️ Simülasyon Döngü Hatası: {str(e)}")
            # Hata loguna da düşür (forensic analiz için)
            log_chained_event(state, "ERROR", f"Fragment Hatası: {str(e)}")

    # Döngüyü Başlat
    main_simulation_loop(sat_data)


if __name__ == "__main__":
    run_app()
