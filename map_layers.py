import streamlit as st
import pydeck as pdk

# ─────────────────────────────────────────────
# GNSS Savunma Sistemi — Harita Katmanları
# TÜBİTAK 2209-A | map_layers.py
# ─────────────────────────────────────────────

def render_map(state, true_lat, true_lon, raw_lat, raw_lon, final_lat, final_lon,
               show_sats, sat_data, attack_type):
    """
    Pydeck tabanlı gelişmiş harita render fonksiyonu.

    Parametreler
    ------------
    state       : Uygulama durum nesnesi (StateProxy)
    true_lat/lon: Gerçek GPS konumu
    raw_lat/lon : Ham (spoofed) GPS ölçümü
    final_lat/lon: Sistem karar konumu (INS/EKF çıktısı)
    show_sats   : Uydu noktalarını göster/gizle
    sat_data    : Uydu konum listesi [{lat, lon, r, g, b, a, name}, ...]
    attack_type : "NORMAL" | "SPOOFING" | "JAMMING"
    """

    has_reference = (state.get("reference_position") is not None
                     or not (state.get("use_live_gps", False) or state.get("use_dataset_mode", False)))
    if state.get("reference_position") is not None:
        true_lat, true_lon = state.reference_position
    layers = []

    # ── 1. ROTA GEÇMİŞİ GÜNCELLEME ─────────────────────────────────────────
    # Her render döngüsünde final konumu rota hafızasına ekle (max 100 nokta)
    if "route_history" not in state or state.route_history is None:
        state.route_history = []

    state.route_history.append([final_lon, final_lat])

    # Bellek yönetimi: en eski noktaları sil
    if len(state.route_history) > 100:
        state.route_history = state.route_history[-100:]

    # ── 2. ROTA ÇİZGİSİ (Cyan — sistem karar rotası) ────────────────────────
    route = state.route_history
    if len(route) > 1:
        route_data = [{
            "path": route,
            "color": [0, 255, 255, 200]
        }]
        layers.append(pdk.Layer(
            "PathLayer",
            data=route_data,
            get_path="path",
            get_color="color",
            width_min_pixels=3,
            width_scale=1,
        ))

    # ── 3. INS TAKIP ROTASI (Sarı — INS aktifse) ────────────────────────────
    ins_history = state.get("ins_history", [])
    if state.get("ins_active", False) and len(ins_history) > 1:
        ins_route_data = [{
            "path": ins_history,
            "color": [255, 220, 0, 220]   # Sarı
        }]
        layers.append(pdk.Layer(
            "PathLayer",
            data=ins_route_data,
            get_path="path",
            get_color="color",
            width_min_pixels=2,
            width_scale=1,
            dash_array=[4, 2],            # Kesikli çizgi — INS tahmini
        ))

    # ── 4. UYDU KATMANLARI ───────────────────────────────────────────────────
    if show_sats and sat_data:
        # Uydu adı yoksa varsayılan ekle
        for s in sat_data:
            if "name" not in s:
                s["name"] = "Uydu"
            if "info" not in s:
                sys_tag = s.get("sys", "GNSS")
                s_lat = s.get("lat", 0.0)
                s_lon = s.get("lon", 0.0)
                lat_dir = "K" if s_lat >= 0 else "G"
                lon_dir = "D" if s_lon >= 0 else "B"
                s["info"] = f"Konstelasyon: {sys_tag} | Yörünge: {abs(s_lat):.1f}°{lat_dir}, {abs(s_lon):.1f}°{lon_dir}"

        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=sat_data,
            get_position="[lon, lat]",
            get_fill_color="[r, g, b, a]",
            get_radius=50000,
            radius_min_pixels=6,
            pickable=True,
        ))

    # ── 5. GERÇEK KONUM (Yeşil ●) ───────────────────────────────────────────
    if has_reference:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            id="actual_layer",
            data=[{
                "lat": true_lat,
                "lon": true_lon,
                "name": "📍 REFERANS KONUM",
                "info": f"Lat: {true_lat:.6f} | Lon: {true_lon:.6f}"
            }],
            get_position="[lon, lat]",
            get_fill_color=[0, 220, 80, 255],     # Canlı yeşil
            get_line_color=[0, 255, 100, 255],
            get_radius=25,
            radius_min_pixels=10,
            stroked=True,
            line_width_min_pixels=2,
            pickable=True,
        ))

    # ── 6. SPOOFING KATMANLARI ───────────────────────────────────────────────
    if attack_type == "SPOOFING":
        # Gerçek → Sahte arası bağlantı çizgisi
        layers.append(pdk.Layer(
            "LineLayer",
            data=[{
                "start": [true_lon, true_lat] if has_reference else [final_lon, final_lat],
                "end": [raw_lon, raw_lat],
                "name": "Referans sapması" if has_reference else "Ham GNSS–tahmin farkı",
                "info": ""
            }],
            get_source_position="start",
            get_target_position="end",
            get_color=[255, 128, 0, 180],
            get_width=3,
            pickable=False,
        ))

        # Sahte sinyal noktası (Kırmızı ●)
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=[{
                "lat": raw_lat,
                "lon": raw_lon,
                "name": "🔴 SAHTE SİNYAL (Spoofing)",
                "info": f"Lat: {raw_lat:.6f} | Lon: {raw_lon:.6f}"
            }],
            get_position="[lon, lat]",
            get_fill_color=[255, 30, 30, 220],    # Kırmızı
            get_line_color=[255, 200, 0, 255],
            get_radius=30,
            radius_min_pixels=12,
            stroked=True,
            line_width_min_pixels=2,
            pickable=True,
        ))

    # ── 7. SİSTEM KARAR NOKTASI (Beyaz ○ — saldırı algılandığında) ──────────
    if attack_type != "NORMAL":
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=[{
                "lat": final_lat,
                "lon": final_lon,
                "name": "⚪ SİSTEM KARARI (INS/EKF)",
                "info": f"Lat: {final_lat:.6f} | Lon: {final_lon:.6f}"
            }],
            get_position="[lon, lat]",
            get_fill_color=[240, 240, 255, 140],  # Yarı şeffaf beyaz
            get_line_color=[255, 255, 255, 255],
            get_radius=20,
            radius_min_pixels=15,
            stroked=True,
            line_width_min_pixels=2,
            pickable=True,
        ))

    # ── 8. EKF FÜZYON NOKTASI (Cyan ◆) ─────────────────────────────────────
    # EKF/Kalman filtresi çıktısı mevcutsa ayrı bir nokta olarak göster
    fused_lat = state.get("fused_lat", None)
    fused_lon = state.get("fused_lon", None)
    if fused_lat is not None and fused_lon is not None:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=[{
                "lat": fused_lat,
                "lon": fused_lon,
                "name": "🔵 EKF FÜZYON ÇIKTISI",
                "info": f"Lat: {fused_lat:.6f} | Lon: {fused_lon:.6f}"
            }],
            get_position="[lon, lat]",
            get_fill_color=[0, 220, 255, 200],    # Cyan
            get_line_color=[0, 180, 255, 255],
            get_radius=18,
            radius_min_pixels=8,
            stroked=True,
            line_width_min_pixels=2,
            pickable=True,
        ))

    # ── 9. KAMERA KONTROLÜ & VIEW STATE ─────────────────────────────────────
    cam_lock = state.get("cam_lock", True)

    if cam_lock:
        state.map_center = (final_lat, final_lon)

    # Zoom: Normal modda daha yakın, saldırıda biraz uzak
    if attack_type == "NORMAL":
        zoom_level = 14
    elif cam_lock:
        zoom_level = 11
    else:
        zoom_level = 13

    # Pitch: Kamera kilidi aktifse 3D eğim (akademik sunum etkisi)
    pitch_angle = 45 if cam_lock else 0

    view_state = pdk.ViewState(
        latitude=state.map_center[0],
        longitude=state.map_center[1],
        zoom=zoom_level,
        pitch=pitch_angle,
        bearing=0,
    )

    # ── 10. HARİTA RENDER ───────────────────────────────────────────────────
    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider="carto",
        map_style="dark",
        tooltip={
            "html": "<b>{name}</b><br/><span style='color:#aaa'>{info}</span>",
            "style": {
                "backgroundColor": "rgba(20,20,40,0.9)",
                "color": "white",
                "fontSize": "13px",
                "borderRadius": "6px",
                "padding": "8px 12px",
            }
        },
    ))

    # ── 11. HARİTA EFSANESİ (LEGEND) ────────────────────────────────────────
    st.markdown(
        """
        <div style="
            display:flex; gap:18px; flex-wrap:wrap;
            background:rgba(0,0,0,0.45); border-radius:8px;
            padding:6px 14px; margin-top:4px;
            font-size:12px; color:#ddd;
        ">
            <span>🟢 Gerçek Konum</span>
            <span>🔴 Sahte Sinyal (Spoofing)</span>
            <span>⚪ INS/EKF Karar Noktası</span>
            <span>🔵 EKF Füzyon Çıktısı</span>
            <span>🟡 INS Tahmini Rotası</span>
            <span>🔷 Sistem Rotası</span>
        </div>
        """.replace("🟢 Gerçek Konum", "🟢 Referans konum" if has_reference else "Referans konum yok"),
        unsafe_allow_html=True,
    )
