import math
from sensors import calculate_distance_km
from detection import analyze_kinematics, run_firewall_rules

# 1. Mesafe Hesaplama Testleri
def test_calculate_distance():
    # Elazığ - Malatya arası yaklaşık mesafe (38.6, 39.1 -> 38.3, 38.3)
    d = calculate_distance_km(38.6, 39.1, 38.3, 38.3)
    assert 60.0 < d < 120.0 # Kabaca doğruluk kontrolü

# 2. Kinematik Analiz Testleri
def test_analyze_kinematics():
    class MockState(dict):
        prev_speed = 80.0
        prev_lat = 38.0
        prev_lon = 39.0
        prev_heading = 0.0
        acceleration = 0.0

    state = MockState()
    acc, h_diff, h = analyze_kinematics(state, 38.01, 39.01, 100.0, 45.0, dt=0.5)

    assert math.isclose(acc, (20.0 / 3.6) / 0.5) # 100 - 80
    assert h > 0 # Yön açısı oluşmalı

# 3. Güvenlik Duvarı (Firewall) Mantık Testleri
def test_firewall_spoofing_teleport():
    class MockState(dict):
        prev_speed = 80.0
        prev_lat = 38.0
        prev_lon = 39.0
        prev_heading = 0.0
        last_good_lat = 38.0
        last_good_lon = 39.0
        attack_mode = "normal"
        jamming_state = "none"

    state = MockState()
    # Işınlanma: Çok uzak koordinat (Ankara'dan İstanbul'a gibi)
    attack, reason = run_firewall_rules(state, 41.0, 29.0, 40.0, 80.0, 45.0, 0.75, 15.0, 180.0)

    assert attack == "SPOOFING"
    assert "Konum Sıçraması" in reason

def test_firewall_jamming_detection():
    class MockState(dict):
        prev_speed = 80.0
        prev_lat = 38.0
        prev_lon = 39.0
        prev_heading = 0.0
        last_good_lat = 38.0
        last_good_lon = 39.0
        attack_mode = "jamming"
        jamming_state = "azaliyor"
        jamming_baseline = 40.0

    state = MockState()
    # SNR çok düşük (40 dB-Hz baz alınmıştı, 10 dB-Hz veriyoruz)
    attack, reason = run_firewall_rules(state, 38.0001, 39.0001, 5.0, 80.0, 45.0, 0.75, 15.0, 45.0)

    assert "JAMMING" in attack
    assert "C/N0" in reason
