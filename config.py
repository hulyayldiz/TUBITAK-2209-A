"""
Protokol Sabitleri, Eşik Değerleri ve Genel Simülasyon Konfigürasyonu
Bu dosya sistemin merkezi ayarlarını barındırır. Hocaların bahsettiği
modülerlik ve bakım kolaylığı sağlamak için ayarlar buradan yönetilmelidir.
"""

# --- AKADEMİK GÜVENLİK DUVARI EŞİKLERİ ---
NOMINAL_CN0 = 45.0                 # Nominal C/N0 değeri (dB-Hz)
JAMMING_CN0_CRITICAL = 15.0        # Jamming tespiti için kritik C/N0 (Interference Threshold)
MAX_G_FORCE = 3.0                  # Maksimum fiziksel ivme (g unit) - İHA'lar için 3-5g, Kara Araçları için 1.5-2g
DEFAULT_HEADING_THRESHOLD = 45.0   # Yön sapması Derece (Aerodinamik Limit)
RF_IMMEDIATE_ATTACK_SCORE = .9     # Strong GNSS RF evidence remains immediate.
RF_CONFIRMATION_SAMPLES = 2        # Weak model-only evidence needs consecutive fixes.
JAMMING_ERROR_FACTOR = 5.0          # Jamming anında konum hatası çarpanı

GLOBAL_ATTACK_DURATION = 40.0      # Gözlem süresi (Observation Window)
GLOBAL_ATTACK_COOLDOWN = 10.0      # Stabilizasyon süresi (Cooldown)

# --- CİHAZ (INS) OTOPİLOT LİMİTLERİ ---
MAX_INS_SPEED = 120.0              # INS modundayken çıkılabilecek max hız (km/sa)
INS_DRIFT_RATE = 0.002             # INS otopilotundayken her saniye biriken hata payı (Drift)
INS_DURATION_MIN = 4.0             # INS minimum devrede kalma süresi (sn)
INS_DURATION_MAX = 7.0             # INS maksimum devrede kalma süresi (sn)

# --- KONUM VERİTABANI (IP ve Varsayılanlar) ---
DEFAULT_LAT = 38.6744              # Elazığ
DEFAULT_LON = 39.1942              # Elazığ
EARTH_RADIUS_KM = 6371.0           # Dünya yarıçapı

CITY_LIST = {
    "Otomatik (IP Tabanlı)": (DEFAULT_LAT, DEFAULT_LON),
    "İstanbul": (41.0082, 28.9784),
    "Ankara": (39.9334, 32.8597),
    "İzmir": (38.4237, 27.1428),
    "Elazığ": (38.6744, 39.1942),
    "Gaziantep": (37.0662, 37.3833),
    "Antalya": (36.8841, 30.7056),
    "Bursa": (40.1826, 29.0659),
    "Kocaeli": (40.8533, 29.8815)
}

# --- AKADEMİK ARAYÜZ ---
SHOW_WIDGETS_ON_START = False      # Başlangıçta loglar ve grafikler daraltılmış gelsin

# --- DİNAMİK EKF PROFİLLERİ ---
EKF_PROFILES = {
    "İHA (UAV) - Yüksek Dinamik": {
        "Q": 0.05,        # Süreç Gürültüsü (Daha esnek takip)
        "R": 0.0001,
        "position_variance_m2": 0.25,      # Ölçüm Gürültüsü (Daha temiz sinyal)
        "desc": "Hızlı manevralar için düşük gecikmeli takip."
    },
    "Kara Aracı (AV) - Yüksek Titreşim": {
        "Q": 0.01,        # Süreç Gürültüsü (Daha stabil/öngörülebilir)
        "R": 0.001,
        "position_variance_m2": 1.0,       # Ölçüm Gürültüsü (Mekanik titreşim filtresi)
        "desc": "Yol gürültüsü ve titreşimi engelleme odaklı."
    }
}

# Detector outputs are not combined into a probability: their scales are not
# calibrated on a common, independent validation set. Each layer applies its
# own decision rule; a future calibrated fusion model needs a frozen protocol.

# --- SENSOR / SLIDER NORMALİZASYON ---
# UI slider değeri [0-100] → G-kuvveti cinsine çevirme faktörü
# Örnek: Slider=40 → 40/20 = 2.0g (İHA manevra limiti)
ACCEL_SLIDER_TO_G_FACTOR = 20.0
