"""Streamlit application shell and top-level status messages."""

import streamlit as st

from controls import render_sidebar

def render_app_shell(state):
    """Render the sidebar and accurately describe the research prototype."""
    fw_active, conf_cn0, conf_accel, conf_heading = render_sidebar(state)
    st.title("GNSS Ölçüm Tutarlılığı Araştırma Prototipi")
    st.caption(
        "Fiziksel kurallar ve uygun olduğunda veri türüne özel algılama katmanları. "
        "Saha doğrulaması tamamlanmamıştır; örtülü spoofing değerlendirmesi bağımsız IMU/yönelim gerektirir."
    )

    if state.get("save_training_data", False):
        st.toast("Eğitim verisi kaydı etkin; bu kayıtlar saha doğrulaması yerine geçmez.", icon="📊")

    if state.get("ins_active", False):
        st.warning(
            "GNSS ölçümleri reddediliyor; mevcut sensör girdileriyle ataletsel konum tahmini kullanılıyor. "
            "Bu çıktı doğrulanmış saha INS'i veya otopilot kontrolü değildir."
        )

    return fw_active, conf_cn0, conf_accel, conf_heading
