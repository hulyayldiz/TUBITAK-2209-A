import math
import streamlit as st
import datetime
import pandas as pd
import os
import plotly.graph_objects as go

def render_top_metrics(state, final_speed, final_cn0, firewall_active):
    """Ana ekran üst metrik kartları."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🕒 Yerel Saat", datetime.datetime.now().strftime("%H:%M:%S"))
    with c2:
        if not math.isfinite(final_cn0):
            st.metric("📡 Sinyal (C/N0)", "Ölçüm yok")
        elif state.get("ins_active", False):
            st.metric("📡 Sinyal (C/N0)", f"{final_cn0:.1f} dB-Hz", delta=("Düşük ağırlıklı GNSS" if state.get("gnss_measurement_used", False) else "GNSS reddediliyor"), delta_color="inverse")
        else:
            diff = final_cn0 - 45.0
            st.metric("📡 Sinyal (C/N0)", f"{final_cn0:.1f} dB-Hz", delta=f"{diff:+.1f} vs 45 dB-Hz referansı", delta_color="normal" if diff > -10 else "inverse")
    with c3:
        # İvme veya INS durumu
        if state.get("ins_active", False):
            remaining = state.get("ins_remaining", 0)
            st.metric("🏎️ Hız (INS)", f"{final_speed:.1f} km/sa", delta=f"Kalan: {remaining:.1f}sn", delta_color="off")
        else:
            st.metric("🏎️ Hız (GPS)", f"{final_speed:.1f} km/sa")
    with c4:
        st.metric("🛡️ Kural kontrolleri", "Çalışıyor" if firewall_active else "Kapalı",
                  delta="Ölçütleri izliyor" if firewall_active else "İzleme kapalı")

def render_evaluation_metrics(p_d, p_fa, precision, f1, ttd_avg, rmse=float("nan")):
    """Unknown reference metrics are absent, never displayed as zero or NaN."""
    values = [("F1 skoru", f1, "%"), ("Kesinlik", precision, "%"),
              ("Tespit (Pd)", p_d, "%"), ("Yanlış alarm (Pfa)", p_fa, "%"),
              ("TTD", ttd_avg, " ms"), ("RMSE", rmse, " m")]
    for start in (0, 3):
        columns = st.columns(3)
        for column, (label, value, unit) in zip(columns, values[start:start+3]):
            column.metric(label, f"{value:.1f}{unit}" if math.isfinite(value) else "Ölçüm yok")


def render_expanders(state, p_d=float("nan"), p_fa=float("nan")):
    """Analiz grafiklerini ve adli bilişim loglarını gösterir."""
    with st.expander("📈 Canlı Analiz Grafikleri (C/N0 & INS Error)", expanded=True):
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Sinyal Gücü (C/N0 dB-Hz)**")
            st.line_chart(state.snr_history, height=150)
        with g2:
            st.markdown("**Hareket modeli artık hatası (metre)**")
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
                        width="stretch"
                    )
        with tab2:
            for l in state.dataset_logs_iha[:5]:
                st.write(f"🛩️ {l}")
            for l in state.live_logs[:5]:
                st.write(f"📡 {l}")

    # ---------------------------------------------------------------
    # YENİ: ML Analitik & Confusion Matrix Expander
    # ---------------------------------------------------------------
    with st.expander("📊 Etiketli oynatma metrikleri ve karmaşıklık matrisi", expanded=False):

        if not math.isfinite(p_d) or not math.isfinite(p_fa):
            st.info("Metrikleri hesaplamak için yeterli etiketli gözlem yok.")
            return
        st.caption("Metrikler bu oynatmadaki örnek kararlarını özetler; bağımsız olay başarısı, saha genellemesi veya güven aralığı değildir.")
        # --- ROC Geçmişini Güncelle ---
        # Her çağrıda mevcut (p_fa, p_d) çiftini ROC geçmişine ekle (maks 50 nokta)
        if not hasattr(state, "roc_history") or state.roc_history is None:
            state.roc_history = []
        state.roc_history.append((p_fa, p_d))
        if len(state.roc_history) > 50:
            state.roc_history.pop(0)  # En eski noktayı çıkar (FIFO)

        # --- State'den TP/FP/TN/FN Değerlerini Oku ---
        tp = getattr(state, "stats_tp", 0)
        fp = getattr(state, "stats_fp", 0)
        tn = getattr(state, "stats_tn", 0)
        fn = getattr(state, "stats_fn", 0)

        # Sıfır bölme koruması için yardımcı değişkenler
        total_pozitif = tp + fn  # Gerçek pozitifler
        total_negatif = tn + fp  # Gerçek negatifler
        total = tp + fp + tn + fn

        # --- Performans Metrikleri Hesapla ---
        recall_val    = (tp / total_pozitif * 100) if total_pozitif > 0 else 0.0
        precision_val = (tp / (tp + fp) * 100)    if (tp + fp) > 0   else 0.0
        specificity   = (tn / total_negatif * 100) if total_negatif > 0 else 0.0
        f1_val        = (2 * precision_val * recall_val / (precision_val + recall_val)) \
                        if (precision_val + recall_val) > 0 else 0.0
        accuracy_val  = ((tp + tn) / total * 100) if total > 0 else 0.0

        # ====================================================
        # BÖLÜM 1: Confusion Matrix (Plotly Heatmap)
        # ====================================================
        st.markdown("#### 🔲 Confusion Matrix")

        # Matris değerleri: [[TN, FP], [FN, TP]] — satır: Gerçek, sütun: Tahmin
        cm_values   = [[tn, fp], [fn, tp]]
        eksen_etiketleri = ["NORMAL", "SALDIRI"]

        # Hücre içi metin: değer ve etiket birlikte
        metin_matris = [
            [f"<b>{tn}</b><br>TN", f"<b>{fp}</b><br>FP"],
            [f"<b>{fn}</b><br>FN", f"<b>{tp}</b><br>TP"],
        ]

        fig_cm = go.Figure(data=go.Heatmap(
            z=cm_values,
            x=eksen_etiketleri,      # Tahmin edilen sınıf (X ekseni)
            y=eksen_etiketleri,      # Gerçek sınıf (Y ekseni)
            text=metin_matris,
            texttemplate="%{text}",
            colorscale=[
                [0.0, "#0a1628"],    # Koyu lacivert — düşük değer
                [0.5, "#00d2ff"],    # Mavi      — orta değer
                [1.0, "#00ff88"],    # Yeşil     — yüksek değer
            ],
            showscale=True,
            colorbar=dict(title="Sayı", tickfont=dict(color="white")),
        ))

        fig_cm.update_layout(
            title=dict(text="Confusion Matrix — Gerçek vs Tahmin", font=dict(color="#00d2ff", size=14)),
            xaxis=dict(title="Tahmin Edilen", tickfont=dict(color="white"), title_font=dict(color="#00d2ff")),
            yaxis=dict(title="Gerçek Sınıf",  tickfont=dict(color="white"), title_font=dict(color="#00d2ff")),
            paper_bgcolor="#0a1628",
            plot_bgcolor="#0a1628",
            font=dict(color="white"),
            height=320,
            margin=dict(l=60, r=40, t=60, b=60),
        )

        st.plotly_chart(fig_cm, width="stretch")

        # ====================================================
        # BÖLÜM 2: Performans Özeti Tablosu
        # ====================================================
        st.markdown("#### 📋 Performans Özeti")

        df_perf = pd.DataFrame({
            "Metrik":  ["Hassasiyet (Precision)", "Duyarlılık (Recall/Pd)", "Özgüllük (Specificity)",
                        "F1-Skoru", "Doğruluk (Accuracy)", "Yanlış Alarm (Pfa)"],
            "Değer (%)": [
                f"{precision_val:.1f}",
                f"{recall_val:.1f}",
                f"{specificity:.1f}",
                f"{f1_val:.1f}",
                f"{accuracy_val:.1f}",
                f"{p_fa:.1f}",
            ],
            "TP/FP/TN/FN": [
                f"TP={tp}, FP={fp}",
                f"TP={tp}, FN={fn}",
                f"TN={tn}, FP={fp}",
                "—",
                f"Toplam={total}",
                f"FP={fp}, TN+FP={total_negatif}",
            ],
        })

        st.dataframe(
            df_perf,
            width="stretch",
            hide_index=True,
        )

        # ====================================================
        # BÖLÜM 3: ROC Benzeri Scatter (Pd vs Pfa)
        # ====================================================
        st.markdown("#### 📈 ROC Benzeri Dağılım (Pd vs Pfa)")

        if len(state.roc_history) >= 2:
            pfa_list = [nokta[0] for nokta in state.roc_history]
            pd_list  = [nokta[1] for nokta in state.roc_history]

            # Nokta indekslerini renk skalası için sıra numarası olarak kullan
            nokta_indeksleri = list(range(len(pfa_list)))

            fig_roc = go.Figure()

            # İdeal ROC referans çizgisi (çapraz — rastgele sınıflandırıcı)
            fig_roc.add_trace(go.Scatter(
                x=[0, 100], y=[0, 100],
                mode="lines",
                line=dict(color="gray", dash="dash", width=1),
                name="Rastgele Sınıflandırıcı",
                opacity=0.4,
            ))

            # Biriken ROC noktaları — zaman içinde renk değişir (eski→yeni)
            fig_roc.add_trace(go.Scatter(
                x=pfa_list,
                y=pd_list,
                mode="markers+lines",
                marker=dict(
                    size=8,
                    color=nokta_indeksleri,        # Zaman sırası renk ekseni
                    colorscale=[[0, "#00d2ff"], [1, "#00ff88"]],  # Mavi→Yeşil
                    showscale=True,
                    colorbar=dict(title="Zaman Sırası", tickfont=dict(color="white"), x=1.05),
                    line=dict(width=1, color="white"),
                ),
                line=dict(color="#00d2ff", width=1.5),
                name="Pd vs Pfa Geçmişi",
            ))

            # Mevcut (son) nokta — özel işaret
            fig_roc.add_trace(go.Scatter(
                x=[pfa_list[-1]],
                y=[pd_list[-1]],
                mode="markers",
                marker=dict(size=14, color="#00ff88", symbol="star", line=dict(color="white", width=2)),
                name="Mevcut Değer",
            ))

            fig_roc.update_layout(
                title=dict(text="ROC Benzeri Scatter — Tespit Oranı vs Yanlış Alarm Oranı",
                           font=dict(color="#00d2ff", size=13)),
                xaxis=dict(
                    title="Yanlış Alarm Oranı Pfa (%)",
                    range=[0, 100],
                    tickfont=dict(color="white"),
                    title_font=dict(color="#00d2ff"),
                    gridcolor="rgba(255,255,255,0.08)",
                ),
                yaxis=dict(
                    title="Tespit Oranı Pd (%)",
                    range=[0, 100],
                    tickfont=dict(color="white"),
                    title_font=dict(color="#00d2ff"),
                    gridcolor="rgba(255,255,255,0.08)",
                ),
                paper_bgcolor="#0a1628",
                plot_bgcolor="#0a1628",
                font=dict(color="white"),
                height=360,
                legend=dict(font=dict(color="white"), bgcolor="rgba(0,0,0,0.3)"),
                margin=dict(l=60, r=80, t=60, b=60),
            )

            st.plotly_chart(fig_roc, width="stretch")
        else:
            # Yeterli veri birikene kadar bilgi mesajı göster
            st.info("ℹ️ ROC dağılımı için simülasyon verisi biriktirilmektedir... (min. 2 nokta gerekli)")

