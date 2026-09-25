import streamlit as st
import pydeck as pdk
import time

def render_map(state, true_lat, true_lon, raw_lat, raw_lon, final_lat, final_lon, show_sats, sat_data, attack_type):
    """PyDeck tabanlı 2D harita katmanlarını oluşturur."""
    layers = []
    
    # Rota Bazlı Yol Çizimi
    route = state.get("route_history", [])
    if len(route) > 1:
        route_data = [{"path": [[p[0], p[1]] for p in route], "color": [0, 255, 255, 200]}]
        layers.append(pdk.Layer("PathLayer", data=route_data, get_path="path", get_color="color", width_min_pixels=4))

    # Uydu Katmanları
    if show_sats and sat_data:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=sat_data,
            get_position="[lon, lat]",
            get_fill_color="[r, g, b, a]",
            get_radius=50000,
            radius_min_pixels=6,
            pickable=True
        ))

    # Gerçek Konum (Yeşil) - Ground Truth (Sinyal koptuğunda gizle)
    if attack_type != "JAMMING":
        layers.append(pdk.Layer(
            "ScatterplotLayer", id="actual_layer",
            data=[{"lat": true_lat, "lon": true_lon, "name": "📍 GERÇEK KONUM"}],
            get_position="[lon, lat]", get_fill_color=[0, 255, 0, 255],
            get_radius=25, radius_min_pixels=10, pickable=True
        ))

    # Saldırı Analizi (Spoofing/Jamming)
    if attack_type == "SPOOFING":
        layers.append(pdk.Layer(
            "LineLayer", data=[{"start": [true_lon, true_lat], "end": [raw_lon, raw_lat]}],
            get_source_position="start", get_target_position="end",
            get_color=[255, 128, 0, 150], get_width=2
        ))
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=[{"lat": raw_lat, "lon": raw_lon}],
            get_position="[lon, lat]", get_fill_color=[255, 0, 0, 200],
            get_radius=30, radius_min_pixels=12
        ))

    # Sistem Karar Noktası (Beyaz) - Forensic Estimate
    if attack_type != "NORMAL":
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=[{"lat": final_lat, "lon": final_lon}],
            get_position="[lon, lat]", get_fill_color=[255, 255, 255, 120], # Daha şeffaf
            get_radius=20, radius_min_pixels=15 # Yeşil'in içinde kalsın diye küçültüldü
        ))

    # Kamera Takibi
    if state.get("cam_lock", True):
        state.map_center = (final_lat, final_lon)
    
    view_state = pdk.ViewState(
        latitude=state.map_center[0],
        longitude=state.map_center[1],
        zoom=11 if state.get("cam_lock", False) else 13,
        pitch=0,
    )

    st.pydeck_chart(pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider="carto",
        map_style="dark",
        tooltip={"text": "📌 {name}"}
    ))
