import unittest
import sys
import os

# Proje dizinini path'e ekle
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import detection
import config

class TestDetectionLogic(unittest.TestCase):
    def setUp(self):
        # Her test için temiz bir state simülasyonu
        class MockState:
            def __init__(self):
                self.prev_lat = 38.6744
                self.prev_lon = 39.1942
                self.prev_speed = 40.0
                self.prev_heading = 45.0
                self.last_good_lat = 38.6744
                self.last_good_lon = 39.1942
                self.ins_active = False
                self.stats_tp = 0
                self.stats_fp = 0
                self.stats_tn = 0
                self.stats_fn = 0
                self.stats_response_times = []
                self.last_resp = 0.0
                self.spoof_persistence = 0
            
            def __contains__(self, key):
                return hasattr(self, key)
            
            def get(self, key, default=None):
                return getattr(self, key, default)

        self.state = MockState()

    def test_normal_operation(self):
        """Normal seyir durumunda saldırı tespit edilmemeli."""
        attack_type, reason = detection.run_firewall_rules(
            self.state, 
            38.67441, 39.19421, # Hafif değişim
            45.0, # Normal SNR
            40.0, # Normal Hız
            config.NOMINAL_CN0,
            0.8, 0.8, 45.0
        )
        self.assertEqual(attack_type, "NORMAL")

    def test_jamming_detection(self):
        """Düşük SNR durumunda Jamming tespiti yapılmalı."""
        attack_type, reason = detection.run_firewall_rules(
            self.state, 
            38.6744, 39.1942,
            10.0, # Kritik SNR
            40.0,
            config.NOMINAL_CN0,
            0.8, 0.8, 45.0
        )
        self.assertIn("JAMMING", attack_type)

    def test_spoofing_teleport_detection(self):
        """Ani konum sıçramasında Spoofing (Teleport/Işınlanma) tespiti yapılmalı."""
        attack_type, reason = detection.run_firewall_rules(
            self.state, 
            39.6744, 40.1942, # Büyük sıçrama
            45.0, 
            40.0,
            config.NOMINAL_CN0,
            0.8, 0.8, 45.0
        )
        self.assertEqual(attack_type, "SPOOFING")
        self.assertIn("Konum Sıçraması", reason)

    def test_acceleration_violation(self):
        """Anormal ivme değişiminde Spoofing tespiti yapılmalı."""
        attack_type, reason = detection.run_firewall_rules(
            self.state, 
            38.6745, 39.1943, 
            45.0, 
            250.0, # Fiziksel olmayan hız/ivme
            config.NOMINAL_CN0,
            0.8, 0.8, 45.0
        )
        self.assertEqual(attack_type, "SPOOFING")
        self.assertIn("İvme", reason)

    def test_imu_priority_detection(self):
        """Tespit motorunun GPS türevi yerine IMU verisine öncelik verdiğini doğrula."""
        self.state.imu_data = {"accel": {"x": 100.0, "y": 0.0}} # IMU'dan gelen devasa ivme (Saldırı)
        attack_type, reason = detection.run_firewall_rules(
            self.state, 
            38.6744, 39.1942, 
            45.0, 
            40.0, # Sabit hız (GPS türevi 0 ivme derdi)
            config.NOMINAL_CN0,
            0.8, 0.8, 45.0
        )
        self.assertEqual(attack_type, "SPOOFING")
        self.assertIn("İvme tutarsızlığı göstergesi", reason)

    def test_ekf_fusion_logic(self):
        """EKF'nin konum verilerini füzyonladığını ve state'e yazdığını doğrula."""
        from fusion import get_fused_position
        f_lat, f_lon = get_fused_position(self.state, 38.0, 39.0, 0.5, 0.1, dt=0.5, gps_trustworthy=True)
        self.assertAlmostEqual(f_lat, 38.0, places=4)
        self.assertAlmostEqual(f_lon, 39.0, places=4)

if __name__ == '__main__':
    unittest.main()
