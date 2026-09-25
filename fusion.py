"""
Sensör Füzyon Modülü (v1.0) - Genişletilmiş Kalman Filtresi (EKF) Esaslı
Akademik Not: Bu sınıf yüksek lisans düzeyinde bir 'Loosely Coupled' entegrasyonu temsil eder. 
Sistem doğrusal (Linear) varsayıldığı için pratik uygulamalarda Lineer Kalman Filtresi (LKF) 
olarak çalışır, ancak durum genişletilmeye (Jacobian eklemeye) uygundur.
"""
import numpy as np
import math

class LooselyCoupledEKF:
    def __init__(self, start_lat, start_lon, profile_name="İHA (UAV) - Yüksek Dinamik"):
        # Durum Vektörü [lat, lon, v_lat, v_lon]
        self.x = np.array([start_lat, start_lon, 0.0, 0.0])
        self.P = np.eye(4) * 0.1
        self.LAT_TO_M = 111320.0
        self.update_parameters(profile_name)
        
    def update_parameters(self, profile_name):
        """Profil bazlı gürültü matrislerini (Q and R) günceller."""
        import config
        profile = config.EKF_PROFILES.get(profile_name, config.EKF_PROFILES["İHA (UAV) - Yüksek Dinamik"])
        
        # Süreç Gürültüsü (Q)
        q_val = profile["Q"]
        self.Q = np.eye(4) * q_val
        
        # Ölçüm Gürültüsü (R)
        r_val = profile["R"]
        self.R = np.eye(2) * r_val
        
        # Kovaryansı sıfırla (Yeni profile uyum için hızlandırma)
        self.P = np.eye(4) * 0.1

    def _f(self, x_state, ax_m_s2, ay_m_s2, dt):
        lat, lon, v_lat, v_lon = x_state
        cos_lat = math.cos(math.radians(lat))
        a_lat = ax_m_s2 / self.LAT_TO_M
        a_lon = ay_m_s2 / (self.LAT_TO_M * cos_lat) if cos_lat != 0 else 0
        
        new_lat = lat + v_lat * dt + 0.5 * a_lat * (dt**2)
        new_lon = lon + v_lon * dt + 0.5 * a_lon * (dt**2)
        new_v_lat = v_lat + a_lat * dt
        new_v_lon = v_lon + a_lon * dt
        return np.array([new_lat, new_lon, new_v_lat, new_v_lon])

    def predict(self, ax_m_s2, ay_m_s2, dt=0.5):
        """EKF Prediction: IMU verisi ile bir sonraki durumu tahmin et."""
        # 1. State Transition (Durum Geçiş)
        new_state = self._f(self.x, ax_m_s2, ay_m_s2, dt)
        
        # 2. Analytical Jacobian Matrisi (F) - df/dx
        # Durum vektörü: [lat, lon, v_lat, v_lon]
        # x_k = F_k-1 * x_k-1 + B * u
        # F_k-1:
        # [1, 0, dt, 0 ]
        # [0, 1, 0,  dt]
        # [0, 0, 1,  0 ]
        # [0, 0, 0,  1 ]
        F = np.array([
            [1.0, 0.0, dt,  0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ])
            
        self.x = new_state
        
        # 3. Kovaryans Tahmini (P = FPF' + Q)
        self.P = F @ self.P @ F.T + self.Q
        
        return self.x[0], self.x[1]

    def update(self, gps_lat, gps_lon):
        """EKF Correction: GPS verisi ile durumu düzelt."""
        # Gözlem Matrisi (H) - Jacobian of h(x). h(x) = [lat, lon] lineer olduğu için H sabit.
        H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        z = np.array([gps_lat, gps_lon])
        y = z - H @ self.x # Yenilik (Innovation)
        
        S = H @ self.P @ H.T + self.R # Yenilik Kovaryansı
        K = self.P @ H.T @ np.linalg.inv(S) # Kalman Kazancı
        
        # Güncelleme
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ H) @ self.P
        
        return self.x[0], self.x[1]

# Global EKF instance (Sensors.py tarafından başlatılacak)
ekf_filter = None

def get_fused_position(state, raw_lat, raw_lon, imu_ax, imu_ay, dt=0.5, gps_trustworthy=True):
    global ekf_filter
    
    current_profile = state.get("ekf_profile", "İHA (UAV) - Yüksek Dinamik")
    
    if ekf_filter is None:
        ekf_filter = LooselyCoupledEKF(raw_lat, raw_lon, profile_name=current_profile)
    elif getattr(state, "prev_ekf_profile", "") != current_profile:
        # Profil değişmiş, filtreyi güncelle
        ekf_filter.update_parameters(current_profile)
        state.prev_ekf_profile = current_profile
    
    # 1. Prediction (IMU her zaman çalışır)
    pred_lat, pred_lon = ekf_filter.predict(imu_ax, imu_ay, dt)
    
    # 2. Update (Sadece GPS güvenilirse/sağlıklıysa)
    if gps_trustworthy:
        final_lat, final_lon = ekf_filter.update(raw_lat, raw_lon)
    else:
        # Spoofing/Jamming varsa sadece tahmine güven (Dead Reckoning)
        final_lat, final_lon = pred_lat, pred_lon
        
    return final_lat, final_lon
