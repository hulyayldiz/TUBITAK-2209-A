"""
Kontrol Paneli ve CSS Enjeksiyon Modülü (controls.py)
Sol kenar çubuğundaki tüm kullanıcı kontrolleri ve özel stil tanımları burada yönetilir.
Modülerlik ilkesi: UI mantığı main.py ve ui.py'den tamamen ayrıştırılmıştır.
"""

import streamlit as st
import time
import config
from dataset_loader import load_dataset_from_uploaded_file, load_dataset_from_local_path


def inject_custom_css():
    """Akademik ve modern görünüm için özel CSS stilleri enjekte eder."""
    st.markdown("""
    <style>
        /* --- GENEL ARKA PLAN --- */
        .stApp {
            background: linear-gradient(135deg, #0a0e1a 0%, #0d1b2a 50%, #0a0e1a 100%);
        }

        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0d1b2a 0%, #112240 100%);
            border-right: 1px solid rgba(0, 210, 255, 0.15);
        }

        /* --- METRIK KARTLAR --- */
        div[data-testid="metric-container"] {
            background: rgba(0, 210, 255, 0.05);
            border: 1px solid rgba(0, 210, 255, 0.2);
            border-radius: 12px;
            padding: 12px;
            transition: all 0.3s ease;
        }
        div[data-testid="metric-container"]:hover {
            border-color: rgba(0, 210, 255, 0.5);
            transform: translateY(-2px);
        }

        /* --- BUTONLAR --- */
        .stButton > button {
            background: linear-gradient(135deg, #1a4a6b, #0d3a5c);
            color: #00d2ff;
            border: 1px solid rgba(0, 210, 255, 0.3);
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #00d2ff, #0099cc);
            color: #0a0e1a;
            border-color: #00d2ff;
        }

        /* --- BAŞLIK --- */
        h1 { color: #00d2ff !important; font-size: 1.4rem !important; }
        h2, h3 { color: #a8d8ea !important; }

        /* --- UYARI KUTULARI --- */
        .stAlert { border-radius: 10px; }

        /* --- GİZLE: Streamlit Watermark --- */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }

        /* --- EXPANDER --- */
        .streamlit-expanderHeader {
            background: rgba(0, 210, 255, 0.05) !important;
            border-radius: 8px !important;
        }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar(state):
    """
    Sol kenar çubuğunun tüm kontrol elemanlarını oluşturur.
    Döndürür: (fw_active, conf_cn0_percent, conf_accel, conf_heading)
    """
    inject_custom_css()

    with st.sidebar:
        st.markdown("## 🛰️ GNSS Savunma Sistemi")
        st.markdown("*v10.0 — TÜBİTAK 2209-A*")
        st.divider()

        # ── 1. VERİ KAYNAĞI ──────────────────────────────────────────
        st.markdown("### 📡 Veri Kaynağı")

        veri_modu = st.radio(
            "Kaynak Seç",
            ["🎮 Simülasyon", "📂 Veri Seti Yükle", "🔌 Canlı GPS"],
            index=0,
            key="veri_modu_radio"
        )

        if veri_modu == "📂 Veri Seti Yükle":
            state.use_dataset_mode = True
            state.use_live_gps = False

            st.markdown("**Dosya Yükle** (.csv / .zip / .mat)")
            uploaded = st.file_uploader(
                "Veri seti seç", type=["csv", "zip", "mat"],
                label_visibility="collapsed"
            )
            if uploaded:
                with st.spinner("Veri okunuyor..."):
                    ok = load_dataset_from_uploaded_file(uploaded, state)
                if ok:
                    summary = state.get("dataset_summary", {})
                    st.success(f"✅ {summary.get('filename','?')} — {summary.get('rows','?')} satır")
                else:
                    st.error(state.get("dataset_error", "Bilinmeyen hata"))

            st.markdown("**veya Yerel Yol Girin**")
            local_path = st.text_input("Tam dosya yolu", placeholder="C:/veri/dataset.csv",
                                       label_visibility="collapsed")
            if st.button("📂 Yükle", use_container_width=True) and local_path:
                with st.spinner("Dosya okunuyor..."):
                    ok = load_dataset_from_local_path(local_path, state)
                if ok:
                    st.success("✅ Yüklendi")
                else:
                    st.error(state.get("dataset_error", "Hata"))

        elif veri_modu == "🔌 Canlı GPS":
            state.use_live_gps = True
            state.use_dataset_mode = False
            gps_mode = st.selectbox("Bağlantı Tipi", ["Seri (COM/ttyUSB)", "TCP/UDP"])
            if "Seri" in gps_mode:
                state.gps_port = st.text_input("Port", value="COM3")
            else:
                state.tcp_port = st.number_input("TCP Port", value=9000, step=1)
        else:
            state.use_live_gps = False
            state.use_dataset_mode = False

        st.divider()

        # ── 2. SALDIRI SİMÜLASYONU ───────────────────────────────────
        st.markdown("### ⚔️ Saldırı Simülasyonu")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📡 Jamming", use_container_width=True):
                state.attack_mode = "jamming"
                state.attack_start_time = time.time()
                state.is_attack_detected = False
        with col2:
            if st.button("📍 Spoofing", use_container_width=True):
                state.attack_mode = "spoofing"
                state.attack_start_time = time.time()
                state.is_attack_detected = False

        if st.button("✅ Normal Moda Dön", use_container_width=True):
            state.attack_mode = "normal"
            state.ins_active = False
            state.spoof_offset_lat = 0.0
            state.spoof_offset_lon = 0.0

        state.auto_sim = st.toggle(
            "🤖 Otomatik Saldırı Simülasyonu",
            value=state.get("auto_sim", False)
        )

        st.divider()

        # ── 3. GÜVENLİK DUVARI AYARLARI ──────────────────────────────
        st.markdown("### 🛡️ Güvenlik Duvarı")

        fw_active = st.toggle(
            "Güvenlik Duvarını Etkinleştir",
            value=state.get("fw_state", True),
            key="fw_toggle"
        )
        state.fw_state = fw_active

        conf_cn0_percent = st.slider(
            "C/N0 Jamming Eşiği (%)",
            min_value=0.1, max_value=1.0, value=0.5, step=0.05,
            help="Nominal C/N0'ın yüzdesi. Altına düşerse Jamming sayılır. (Örn: 0.5 → 22.5 dB-Hz)"
        )

        conf_accel = st.slider(
            "İvme Toleransı (km/sa per frame)",
            min_value=5, max_value=80, value=40, step=5,
            help="Anlık hız değişimi bu değeri aşarsa Spoofing tespiti tetiklenir."
        )

        conf_heading = st.slider(
            "Yön Sapma Eşiği (°)",
            min_value=10, max_value=90, value=45, step=5,
            help="Tek framede bu dereceden fazla yön değişimi Spoofing işareti sayılır."
        )

        st.divider()

        # ── 4. EKF PROFİLİ ───────────────────────────────────────────
        st.markdown("### 🔧 EKF Füzyon Profili")

        ekf_options = list(config.EKF_PROFILES.keys())
        selected_profile = st.selectbox(
            "Platform Tipi", ekf_options,
            index=0,
            help="Platforma göre Kalman filtresi gürültü parametreleri (Q, R) otomatik ayarlanır."
        )
        state.ekf_profile = selected_profile
        profile_desc = config.EKF_PROFILES[selected_profile]["desc"]
        st.caption(f"ℹ️ {profile_desc}")

        st.divider()

        # ── 5. YAPAY ZEKA EĞİTİMİ ────────────────────────────────────
        st.markdown("### 🧠 Yapay Zeka Motoru")

        state.save_training_data = st.toggle(
            "📊 Eğitim Verisi Topla",
            value=state.get("save_training_data", False),
            help="Aktifken her simülasyon döngüsü gnss_training_dataset.csv'ye kaydedilir."
        )

        state.academic_mode = st.toggle(
            "🎓 Akademik Mod (Uydu Görünümü Kapalı)",
            value=state.get("academic_mode", False),
            help="Performans için uydu katmanını devre dışı bırakır."
        )

        if st.button("🚀 Yapay Zeka Modellerini Eğit", use_container_width=True):
            with st.spinner("Modeller eğitiliyor... (~20 saniye)"):
                try:
                    from train_model import run_model_training
                    success, msg, report = run_model_training()
                    if success:
                        st.success(f"✅ {msg}")
                        if report:
                            with st.expander("📊 Eğitim Raporu"):
                                st.text(report)
                    else:
                        st.warning(f"⚠️ {msg}")
                except Exception as e:
                    st.error(f"Eğitim hatası: {e}")

        st.divider()

        # ── 6. HARİTA ve KONUM ────────────────────────────────────────
        st.markdown("### 🗺️ Harita Ayarları")

        state.cam_lock = st.toggle(
            "📷 Kamera Kilidi (Araca Takip)",
            value=state.get("cam_lock", False)
        )

        city_options = list(config.CITY_LIST.keys())
        selected_city = st.selectbox("Başlangıç Konumu", city_options)
        if st.button("📍 Konumu Uygula", use_container_width=True):
            new_lat, new_lon = config.CITY_LIST[selected_city]
            state.true_lat = new_lat
            state.true_lon = new_lon
            state.last_good_lat = new_lat
            state.last_good_lon = new_lon
            state.map_center = (new_lat, new_lon)
            st.success(f"✅ {selected_city} konumuna geçildi.")

        st.divider()

        # ── 7. SİSTEM BİLGİSİ ────────────────────────────────────────
        st.markdown("### ℹ️ Sistem Bilgisi")
        uptime = time.time() - state.get("startup_time", time.time())
        st.caption(f"⏱️ Çalışma Süresi: {uptime/60:.1f} dakika")
        st.caption(f"🔁 Döngü Sayısı: {state.get('render_counter', 0)}")
        st.caption(f"🔐 Son Hash: `{state.get('last_log_hash','—')[:12]}...`")

        attack_counts = state.get("attack_counts", {"Jamming": 0, "Spoofing": 0})
        st.caption(f"📊 Tespit: Jamming×{attack_counts['Jamming']} | Spoofing×{attack_counts['Spoofing']}")

        if st.button("🔄 Sistemi Sıfırla", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    return fw_active, conf_cn0_percent, conf_accel, conf_heading