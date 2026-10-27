"""
Uydu (GNSS) Takip ve Simülasyon Modülü
Skyfield ve Celestrak TLE verileri aracılığıyla çoklu uydu mekaniğini yönetir.
"""

import time
import math
import logging
from datetime import datetime, timedelta
import collections

# Merkezi Loglama
logging.basicConfig(filename='system_events.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from skyfield.api import load, wgs84
    SKYFIELD_AVAILABLE = True
except ImportError:
    SKYFIELD_AVAILABLE = False

# Çoklu GNSS Sistemi yapılandırması
SAT_SYSTEMS = {
    "GPS":     {"url": "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle",  "color": "#00aaff", "size": 150},
    "GLONASS": {"url": "https://celestrak.org/NORAD/elements/gp.php?GROUP=glonass&FORMAT=tle", "color": "#ff4444", "size": 150},
    "Galileo": {"url": "https://celestrak.org/NORAD/elements/gp.php?GROUP=galileo&FORMAT=tle", "color": "#ffcc00", "size": 150},
}

SAT_RGBA = {
    "GPS":     [0,   170, 255, 230],
    "GLONASS": [255, 60,  60,  230],
    "Galileo": [255, 200, 0,   230],
}

import streamlit as st

@st.cache_resource(ttl=3600)
def load_all_satellites_logic_v2():
    """
    Tüm uydu sistemleri için TLE verisini Celestrak'ten çeker.
    Bağlantı kopukluklarını yönetir ve hata durumunda log tutar.
    """
    if not SKYFIELD_AVAILABLE:
        logging.error("Skyfield kütüphanesi yüklü değil!")
        return None
        
    result = collections.defaultdict(list)
    any_success = False
    for name, cfg in SAT_SYSTEMS.items():
        try:
            result[name] = load.tle_file(cfg["url"])
            any_success = True
        except Exception as e:
            logging.error(f"TLE Yükleme Hatası ({name}): {e}")
            result[name] = []
            
    if not any_success:
        return None
        
    return dict(result)

@st.cache_resource
def get_skyfield_timescale():
    """
    Ekonomik Performans: Skyfield zaman ölçeğini önbelleğe alır.
    Her 2 saniyede bir yüklenmesini engeller.
    """
    if SKYFIELD_AVAILABLE:
        return load.timescale()
    return None

@st.cache_data(ttl=5)
def get_live_sat_data(active_systems, _all_sats_db, time_offset_hours=0):
    """
    Aktif uydu konstelasyonlarını istenilen zaman ofsetine göre hesaplayıp harita
    verisine dönüştürür. İnternet yoksa simüle yörünge çizer.
    """
    all_sats = _all_sats_db or {}
    sat_list = []
    
    ts = get_skyfield_timescale()
    if ts:
        t_now = datetime.now() + timedelta(hours=time_offset_hours)
        t = ts.utc(t_now.year, t_now.month, t_now.day, t_now.hour, t_now.minute, t_now.second)
    else:
        t = None
        
    for sys_name in active_systems:
        rgba = SAT_RGBA.get(sys_name, [200, 200, 200, 200])
        real_sats = all_sats.get(sys_name, [])

        if real_sats and ts:
            for sat in real_sats:
                try:
                    geocentric = sat.at(t)
                    subpoint = wgs84.subpoint(geocentric)
                    sat_list.append({
                        "lat": subpoint.latitude.degrees,
                        "lon": subpoint.longitude.degrees,
                        "name": sat.name, "sys": sys_name,
                        "r": rgba[0], "g": rgba[1], "b": rgba[2], "a": rgba[3]
                    })
                except Exception as e:
                    logging.error(f"Skyfield Hesaplama Hatası ({sat.name}): {e}")
        else:
            # Gerçek TLE yoksa, görsel demonstrasyon için matematiksel simülasyon (Hocalar için güvenli mod)
            idx = list(SAT_RGBA.keys()).index(sys_name) if sys_name in SAT_RGBA else 0
            t_now_local = time.time() + time_offset_hours * 3600
            for i in range(8):
                t_offset_val = t_now_local * 0.01 + (i * (math.pi / 4)) + idx * 2
                sat_list.append({
                    "lat": 55 * math.sin(t_offset_val),
                    "lon": ((t_now_local * 1.5 + i * 45 + idx * 60) % 360) - 180,
                    "name": f"SIM-{sys_name}-{i+1}", "sys": sys_name,
                    "r": rgba[0], "g": rgba[1], "b": rgba[2], "a": rgba[3]
                })
    return sat_list
