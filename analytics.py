import streamlit as st
import datetime
import pandas as pd
import hashlib
import os

def render_top_metrics(state, final_speed, final_cn0, firewall_active):
    """Ana ekran üst metrik kartları."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🕒 Yerel Saat", datetime.datetime.now().strftime("%H:%M:%S"))
    with c2:
        if state.get("ins_active", False):
            st.metric("📡 Sinyal (C/N0)", "0.0 dB-Hz", delta="İNERSİYEL MOD", delta_color="inverse")
        else:
            diff = final_cn0 - 45.0
            st.metric("📡 Sinyal (C/N0)", f"{final_cn0:.1f} dB-Hz", delta=f"{diff:+.1f} dB-Hz", delta_color="normal" if diff > -10 else "inverse")
    with c3:
        # İvme veya INS durumu
        if state.get("ins_active", False):
            remaining = state.get("ins_remaining", 0)
            st.metric("🏎️ Hız (INS)", f"{final_speed:.1f} km/sa", delta=f"Kalan: {remaining:.1f}sn", delta_color="off")
        else:
            st.metric("🏎️ Hız (GPS)", f"{final_speed:.1f} km/sa")
    with c4:
        st.metric("🛡️ Güvenlik Duvarı", "AKTİF" if firewall_active else "PASİF", delta="Koruma" if firewall_active else "Tehlike")

def render_academic_metrics(p_d, p_fa, precision, f1, ttd_avg, rmse=0.0):
    """Akademik performans göstergeleri (Pd, Pfa, F1, RMSE)."""
    st.markdown("<style>.metric-card { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 12px; margin-bottom: 10px; transition: all 0.3s ease; } .metric-card:hover { transform: translateY(-3px); border-color: #00d2ff; } .metric-val { font-size: 1.8rem; font-weight: 800; }</style>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-card">🎯 F1-Skoru<br><span class="metric-val">%{f1:.1f}</span></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card">🔍 Kesinlik<br><span class="metric-val">%{precision:.1f}</span></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card">📈 Tespit (Pd)<br><span class="metric-val">%{p_d:.1f}</span></div>', unsafe_allow_html=True)
    
    c4, c5, c6 = st.columns(3)
    with c4: st.markdown(f'<div class="metric-card">📉 Yanlış Alarm (Pfa)<br><span class="metric-val">%{p_fa:.1f}</span></div>', unsafe_allow_html=True)
    with c5: st.markdown(f'<div class="metric-card">⏱️ TTD (Hız)<br><span class="metric-val">{ttd_avg:.1f}ms</span></div>', unsafe_allow_html=True)
    with c6: st.markdown(f'<div class="metric-card">📏 RMSE (Hata)<br><span class="metric-val">{rmse:.1f}m</span></div>', unsafe_allow_html=True)

def render_expanders(state):
    """Analiz grafiklerini ve adli bilişim loglarını gösterir."""
    with st.expander("📈 Canlı Analiz Grafikleri (C/N0 & INS Error)", expanded=True):
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Sinyal Gücü (C/N0 dB-Hz)**")
            st.line_chart(state.snr_history, height=150)
        with g2:
            st.markdown("**INS Artık Hata (Metre)**")
            st.line_chart(state.residuals_history, height=150)

    with st.expander("📋 Adli Bilişim Kayıtları", expanded=True):
        tab1, tab2 = st.tabs(["🎮 Simülasyon", "🛰️ Dataset/Canlı"])
        with tab1:
            for l in state.sim_logs[:15]:
                st.write(l)
            
            # Log indirme butonu
            if os.path.exists("system_events.log"):
                with open("system_events.log", "rb") as f:
                    st.download_button(
                        label="📥 Adli Kayıtları İndir (.log)",
                        data=f,
                        file_name=f"GNSS_ADLI_KONTROL_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.log",
                        mime="text/plain",
                        use_container_width=True
                    )
        with tab2:
            for l in state.dataset_logs_iha[:5]:
                st.write(f"🛩️ {l}")
            for l in state.live_logs[:5]:
                st.write(f"📡 {l}")
