import socket
import pynmea2
import select
import time
import streamlit as st
import logging

import logging.handlers

# Merkezi Loglama (Rotasyon Destekli)
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler('system_events.log', maxBytes=10*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)

try:
    import serial
except ImportError:
    serial = None

class SocketManager:
    """Soket bağlantılarını Streamlit yenilemeleri arasında güvenli bir şekilde saklar."""
    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        self.tcp_sock = None
        self.udp_sock = None
        self.tcp_client_conn = None
        self._setup_sockets()

    def _setup_sockets(self):
        try:
            # TCP Sunucu Soketi
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_sock.bind((self.host, self.port))
            self.tcp_sock.listen(1)
            self.tcp_sock.setblocking(False)
            
            # UDP Soketi
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock.bind((self.host, self.port))
            self.udp_sock.setblocking(False)
        except socket.error as e:
            logging.error(f"Soket Başlatma Hatası: {e}")
            self.tcp_sock = None
            self.udp_sock = None

@st.cache_resource
def get_socket_manager(host, port):
    return SocketManager(host, port)

class SerialManager:
    """Seri port bağlantısını Streamlit yenilemeleri arasında güvenli saklar."""
    def __init__(self, port, baud=9600):
        self.port = port
        self.baud = baud
        self.ser = None
        self._setup_serial()

    def _setup_serial(self):
        if serial is None: return
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
        except Exception as e:
            logging.error(f"Seri Port Açma Hatası ({self.port}): {e}")
            self.ser = None

@st.cache_resource
def get_serial_manager(port, baud=9600):
    return SerialManager(port, baud)

def get_gps_from_tcp(state, host='0.0.0.0', port=9000):
    """
    Hibrit Veri Alıcısı: Hem TCP hem de UDP üzerinden gelen NMEA paketlerini dinler.
    """
    manager = get_socket_manager(host, port)
    
    if manager.tcp_sock is None or manager.udp_sock is None:
        state.tcp_status = "Soket Hatası (Port Meşgul Olabilir)"
        return None, None, None, None

    # Dinlenecek giriş listesi
    inputs = [manager.tcp_sock, manager.udp_sock]
    if manager.tcp_client_conn:
        inputs.append(manager.tcp_client_conn)
        
    try:
        readable, _, _ = select.select(inputs, [], [], 0.2)
    except socket.error:
        return None, None, None, None

    raw_data = ""
    
    for s in readable:
        # A. Yeni bir TCP bağlantı isteği
        if s is manager.tcp_sock:
            try:
                conn, addr = s.accept()
                conn.setblocking(False)
                manager.tcp_client_conn = conn
                state.tcp_status = f"Bağlı (TCP): {addr[0]}"
            except socket.error:
                pass
            
        # B. Mevcut TCP istemcisinden veri akışı
        elif s is manager.tcp_client_conn:
            try:
                data = s.recv(4096)
                if not data:
                    manager.tcp_client_conn.close()
                    manager.tcp_client_conn = None
                    state.tcp_status = "TCP Bağlantısı Kesildi (Yeniden Dinleniyor)"
                    logging.info("TCP İstemcisi koptu, yeni bağlantı bekleniyor...")
                else:
                    raw_data = data.decode(errors='replace')
                    state.tcp_status = "Veri Akıyor (TCP)"
            except socket.error as e:
                logging.warning(f"TCP Veri Alma Hatası (Bağlantı koptu): {e}")
                manager.tcp_client_conn = None
                state.tcp_status = "TCP Hata (Yeniden Dinleniyor)"

        # C. UDP paketi girişi
        elif s is manager.udp_sock:
            try:
                data, addr = manager.udp_sock.recvfrom(4096)
                raw_data = data.decode(errors='replace')
                state.tcp_status = f"Bağlı (UDP): {addr[0]}"
            except socket.error as e:
                logging.warning(f"UDP Veri Alma Hatası: {e}")

    # NMEA Çözümleme
    if not raw_data:
        return None, None, None, None

    try:
        for line in raw_data.split('\n'):
            line = line.strip()
            if line.startswith('$'):
                msg = pynmea2.parse(line)
                if isinstance(msg, pynmea2.types.talker.GGA):
                    return msg.latitude, msg.longitude, 0.0, getattr(state, "current_heading", 45.0)
                elif isinstance(msg, pynmea2.types.talker.RMC):
                    speed_kmh = float(msg.spd_over_grnd or 0) * 1.852
                    heading = float(msg.true_course) if msg.true_course else getattr(state, "current_heading", 45.0)
                    return msg.latitude, msg.longitude, speed_kmh, heading
    except pynmea2.ParseError:
        pass
    except Exception as e:
        logging.error(f"NMEA İşleme Hatası: {e}")
        
    return None, None, None, None

def get_gps_from_serial(state, port='COM3', baud=9600):
    """
    Donanım Entegrasyonu: Seri port üzerinden gerçek NMEA verisini okur.
    """
    if serial is None:
        state.tcp_status = "Bağımlılık Eksik: pyserial"
        return None, None, None, None

    manager = get_serial_manager(port, baud)
    
    if manager.ser is None:
        state.tcp_status = f"Port Erişim Hatası: {port}"
        return None, None, None, None

    try:
        if manager.ser.in_waiting > 0:
            line = manager.ser.readline().decode('ascii', errors='replace').strip()
            if line.startswith('$'):
                msg = pynmea2.parse(line)
                state.tcp_status = "Seri Veri Akıyor"
                if isinstance(msg, pynmea2.types.talker.GGA):
                    return float(msg.latitude), float(msg.longitude), 0.0, getattr(state, "current_heading", 45.0)
                elif isinstance(msg, pynmea2.types.talker.RMC):
                    speed_kmh = float(msg.spd_over_grnd or 0) * 1.852
                    heading = float(msg.true_course) if msg.true_course else getattr(state, "current_heading", 45.0)
                    return float(msg.latitude), float(msg.longitude), speed_kmh, heading
    except Exception as e:
        state.tcp_status = f"Seri Okuma Hatası: {str(e)}"
        logging.error(f"Seri Okuma Hatası: {e}")
        
    return None, None, None, None
