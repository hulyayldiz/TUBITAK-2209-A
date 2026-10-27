import unittest
import sys
import os
import pandas as pd
from unittest.mock import patch

# Proje dizinini path'e ekle
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ml_detection

class TestMLDetection(unittest.TestCase):
    def setUp(self):
        class MockState(dict):
            def __getattr__(self, name): return self.get(name)
            def __setattr__(self, name, value): self[name] = value
            
        self.state = MockState({
            "save_training_data": False,
            "vae_buffer": []
        })

    def test_model_loading(self):
        """Modellerin yüklenip yüklenmediğini kontrol et."""
        # Not: Dosyalar yoksa None döner, hata vermemeli.
        rf, _ = ml_detection.load_rf_bundle()
        vae = ml_detection.load_vae_model()
        self.assertTrue(rf is not None or not os.path.exists("gnss_rf_model.pkl"))
        self.assertTrue(vae is None or hasattr(vae, "feature_mean"))

    def test_hybrid_decision_structure(self):
        """Hibrit karar fonksiyonunun dönüş yapısını kontrol et."""
        features = [45.0, 0.1, 0.0, 0.5] # snr, accel, heading, residual
        final_type, confidence, ml_label, anomaly = ml_detection.get_hybrid_decision(
            "NORMAL", features, self.state, None
        )
        
        self.assertIsInstance(final_type, str)
        self.assertIsNone(confidence)
        self.assertIsInstance(ml_label, str)
        self.assertIsInstance(anomaly, float)

    def test_vae_buffer_processing(self):
        """VAE tamponu ile işleme yapıldığında hata oluşmamalı."""
        features = [40.0, 0.5, 2.0, 1.2]
        buffer = [features] * 5
        
        final_type, _, _, _ = ml_detection.get_hybrid_decision(
            "NORMAL", features, self.state, buffer
        )
        self.assertIn(final_type, ["NORMAL", "ANOMALİ (Potansiyel Meaconing)", "JAMMING", "SPOOFING", "BİLİNMİYOR"])

    def test_receiver_anomaly_does_not_emit_fabricated_confidence(self):
        self.state.update(use_dataset_mode=True, receiver_profile_name="receiver:test",
                          receiver_identity={"receiver_id": "test", "motion": "moving"},
                          dataset_df=pd.DataFrame([{"lat": 1., "lon": 2.}]),
                          dataset_index=1, col_map={"lat": "lat", "lon": "lon"})
        with patch("receiver_profile.receiver_decision", return_value={
                "available": True, "detected": True, "status": "alarm"}):
            decision, confidence, _, _ = ml_detection.get_hybrid_decision(
                "NORMAL", [45., 0., 0., 0.], self.state)
        self.assertEqual(decision, "ANOMALİ (Alıcı tutarsızlığı)")
        self.assertIsNone(confidence)

if __name__ == '__main__':
    unittest.main()
