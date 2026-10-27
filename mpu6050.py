"""
MPU6050 IMU Modülü (v2.0)
Gerçek donanım (I2C) desteği ve sanal fallback mekanizması içerir.
"""
import random
import logging

try:
    import smbus2 as smbus
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

class MPU6050:
    def __init__(self, address=0x68, bus_num=1):
        self.address = address
        self.bus_num = bus_num
        self.bus = None
        self.is_real_hardware = False
        
        if HAS_HARDWARE:
            try:
                self.bus = smbus.SMBus(self.bus_num)
                # Uyku modundan çıkar (PWR_MGMT_1)
                self.bus.write_byte_data(self.address, 0x6B, 0x00)
                self.is_real_hardware = True
                logging.info(f"✅ Gerçek MPU6050 Tespit Edildi (Adres: {hex(address)})")
            except Exception as e:
                logging.warning(f"⚠️ MPU6050 Donanım Hatası: {e}. Sanal moda geçiliyor.")
                self.is_real_hardware = False
        else:
            logging.info("ℹ️ smbus2 bulunamadı, Sanal IMU modu aktif.")

    def _read_raw_data(self, addr):
        # 16-bit veriyi oku (Yüksek ve Düşük baytları birleştir)
        high = self.bus.read_byte_data(self.address, addr)
        low = self.bus.read_byte_data(self.address, addr + 1)
        value = (high << 8) | low
        if value >= 32768:
            value = value - 65536
        return value

    def get_imu_data(self, speed_kmh=0, heading_deg=0, dt=0.5):
        if self.is_real_hardware:
            try:
                # Hassasiyet çarpanları (Varsayılan: +/- 2g ve +/- 250 deg/s)
                accel_scale = 16384.0
                gyro_scale = 131.0
                
                ax = self._read_raw_data(0x3B) / accel_scale * 9.80665
                ay = self._read_raw_data(0x3D) / accel_scale * 9.80665
                az = self._read_raw_data(0x3F) / accel_scale * 9.80665
                
                gx = self._read_raw_data(0x43) / gyro_scale
                gy = self._read_raw_data(0x45) / gyro_scale
                gz = self._read_raw_data(0x47) / gyro_scale
                
                return {
                    "accel": {"x": ax, "y": ay, "z": az},
                    "gyro": {"x": gx, "y": gy, "z": gz},
                    "frame": "body",
                    "real": True
                }
            except Exception as e:
                logging.error(f"IMU Okuma Hatası: {e}")
                self.is_real_hardware = False # Hata durumunda sanal moda düş
        
        # Sanal Fallback (Literatüre uygun gürültü modeli)
        return {
            "accel": {
                "x": (random.random() - 0.5) * 0.2, 
                "y": (random.random() - 0.5) * 0.2, 
                "z": 9.80665 + (random.random() - 0.5) * 0.1
            },
            "gyro": {
                "x": 0.0, "y": 0.0, "z": random.uniform(-0.1, 0.1)
            },
            "real": False
        }

# Singleton instance
_imu_sensor = MPU6050()

def get_live_imu(speed=0, heading=0):
    return _imu_sensor.get_imu_data(speed, heading)
