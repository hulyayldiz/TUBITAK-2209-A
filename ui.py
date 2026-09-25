"""
Streamlit Merkezi UI Modülü
Diğer bileşenleri koordine eder ve ana arayüzün iskeletini oluşturur.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import config

# Bileşenleri Import Et
from controls import render_sidebar, inject_custom_css
from map_layers import render_map
from analytics import render_top_metrics, render_academic_metrics, render_expanders

def render_ui_skeleton(state):
    """Arayüzün temel yapısını ve yerleşimini koordine eder."""
    
    # 1. Stil ve Sidebar
    fw_active, conf_cn0, conf_accel, conf_heading = render_sidebar(state)
    
    # 2. Üst Banner
    st.title("🛰️ GNSS Sinyal Bütünlüğü İçin Hibrit Yapay Zeka Destekli Otonom Müdahale Sistemi")
    st.markdown("*Akademik Literatür Standartlarında Anomali Tespit ve Savunma Arayüzü*")
    
    # 3. Bilgilendirme Mesajları (UX Geliştirmesi)
    if state.get("save_training_data", False):
        st.toast("🔴 Veri Toplama Aktif: Farklı senaryolar uygulayarak modeli zenginleştirin.", icon="📊")
    
    if state.get("ins_active", False):
        st.warning(f"🚨 Sinyal Kaybı! Otopilot (INS) Devrede. Tahmini Kalan Süre: {state.get('ins_remaining', 0):.1f} sn", icon="🛡️")

    return fw_active, conf_cn0, conf_accel, conf_heading

# Geriye dönük uyumluluk için UI fonksiyonlarını buradan dışarı açıyoruz
__all__ = ['render_sidebar', 'render_top_metrics', 'render_map', 'render_academic_metrics', 'render_expanders', 'render_ui_skeleton']
