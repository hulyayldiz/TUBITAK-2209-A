import socket
import select
import time
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

    def close(self):
        for connection in (self.tcp_client_conn, self.tcp_sock, self.udp_sock):
            if connection is not None:
                connection.close()
        self.tcp_client_conn = self.tcp_sock = self.udp_sock = None

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
            self.close()

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

def get_serial_manager(port, baud=9600):
    return SerialManager(port, baud)

def _decode(state, source, payload):
    from nmea_stream import NMEAStream
    parsers = state.get("nmea_parsers", {})
    if source not in parsers and len(parsers) >= 8:
        parsers.pop(next(iter(parsers)))
    parser = parsers.setdefault(source, NMEAStream())
    state.nmea_parsers = parsers
    result = parser.feed(payload)
    if result is not None:
        state.gps_cn0 = parser.cn0()
        state.gps_source = source
        state.gps_sample_time = time.monotonic()
    return result


def get_gps_from_tcp(state, host="0.0.0.0", port=9000):
    manager = state.get("gps_socket_manager")
    if manager is None or (manager.host, manager.port) != (host, int(port)):
        if manager is not None:
            manager.close()
        manager = get_socket_manager(host, int(port))
        state.gps_socket_manager = manager
    if (manager.tcp_sock is None or manager.udp_sock is None) and time.monotonic() >= getattr(manager, "retry_after", 0.):
        manager._setup_sockets()
        manager.retry_after = time.monotonic()+2.
    if manager.tcp_sock is None or manager.udp_sock is None:
        state.tcp_status = "Soket Hatası (Port Meşgul Olabilir)"
        return (None,)*4
    inputs = [manager.tcp_sock, manager.udp_sock]
    if manager.tcp_client_conn is not None:
        inputs.append(manager.tcp_client_conn)
    latest = None
    try:
        readable, _, _ = select.select(inputs, [], [], 0.)
        for connection in readable:
            if connection is manager.tcp_sock:
                client, address = connection.accept()
                client.setblocking(False)
                if manager.tcp_client_conn is not None:
                    manager.tcp_client_conn.close()
                manager.tcp_client_conn = client
                manager.client_id = str(time.monotonic_ns())
                state.tcp_status = f"TCP: {address[0]}"
            elif connection is manager.udp_sock:
                data, address = connection.recvfrom(65536)
                latest = _decode(state, f"udp:{address}", data) or latest
            else:
                data = connection.recv(65536)
                if not data:
                    connection.close()
                    manager.tcp_client_conn = None
                else:
                    latest = _decode(state, f"tcp:{manager.client_id}", data) or latest
    except (OSError, ValueError) as error:
        state.tcp_status = f"TCP/UDP Okuma Hatası: {error}"
    return latest if latest is not None else (None,)*4


def get_gps_from_serial(state, port="COM3", baud=9600):
    if serial is None:
        state.tcp_status = "Bağımlılık Eksik: pyserial"
        return (None,)*4
    manager = state.get("gps_serial_manager")
    if manager is None or (manager.port, manager.baud) != (port, baud):
        if manager is not None and manager.ser is not None:
            manager.ser.close()
        manager = get_serial_manager(port, baud)
        state.gps_serial_manager = manager
    if manager.ser is None and time.monotonic() >= getattr(manager, "retry_after", 0.):
        manager._setup_serial()
        manager.retry_after = time.monotonic()+2.
        state.get("nmea_parsers", {}).pop(f"serial:{port}:{baud}", None)
    if manager.ser is None:
        state.tcp_status = f"Port Erişim Hatası: {port}"
        return (None,)*4
    try:
        count = manager.ser.in_waiting
        if count:
            result = _decode(state, f"serial:{port}:{baud}", manager.ser.read(min(count, 65536)))
            state.tcp_status = "Seri veri akıyor"
            if result is not None:
                return result
    except (OSError, ValueError) as error:
        state.tcp_status = f"Seri Okuma Hatası: {error}"
        manager.ser.close()
        manager.ser = None
    return (None,)*4
