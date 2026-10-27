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
        self.acceleration_variance = q_val
        
        # Ölçüm Gürültüsü (R)
        r_val = profile["R"]
        # Profiles specify SI variances; convert to degrees at the current latitude.
        scale = np.array([self.LAT_TO_M, self.LAT_TO_M * math.cos(math.radians(self.x[0]))])
        self.R = np.diag(np.full(2, profile.get("position_variance_m2", .25)) / scale**2)
        
        # Kovaryansı sıfırla (Yeni profile uyum için hızlandırma)
        self.P = np.diag(np.array([25., 25., 4., 4.]) / np.tile(scale, 2)**2)

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
            
        latitude = math.radians(self.x[0])
        longitude_accel_derivative = (ay_m_s2 / self.LAT_TO_M * math.sin(latitude)
                                      / math.cos(latitude)**2 * math.pi / 180)
        F[1, 0] = .5 * dt**2 * longitude_accel_derivative
        F[3, 0] = dt * longitude_accel_derivative
        self.x = new_state
        
        # 3. Kovaryans Tahmini (P = FPF' + Q)
        scale = np.array([self.LAT_TO_M, self.LAT_TO_M * math.cos(math.radians(self.x[0]))])
        G = np.vstack((np.diag(.5 * dt**2 / scale), np.diag(dt / scale)))
        self.Q = G @ G.T * self.acceleration_variance
        self.P = F @ self.P @ F.T + self.Q
        
        return self.x[0], self.x[1]

    def update(self, gps_lat, gps_lon, measurement_covariance=None, gate=True):
        """EKF Correction: GPS verisi ile durumu düzelt."""
        # Gözlem Matrisi (H) - Jacobian of h(x). h(x) = [lat, lon] lineer olduğu için H sabit.
        H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        z = np.array([gps_lat, gps_lon])
        y = z - H @ self.x # Yenilik (Innovation)
        
        R = self.R if measurement_covariance is None else measurement_covariance
        S = H @ self.P @ H.T + R
        self.last_nis = float(y @ np.linalg.solve(S, y))
        self.last_measurement_used = not gate or self.last_nis <= -2*math.log(.001)
        if not self.last_measurement_used:
            return self.x[0], self.x[1]
        K = np.linalg.solve(S, H @ self.P).T
        
        # Güncelleme
        self.x = self.x + K @ y
        correction = np.eye(4) - K @ H
        self.P = correction @ self.P @ correction.T + K @ R @ K.T
        
        return self.x[0], self.x[1]

def get_fused_position(state, raw_lat, raw_lon, imu_ax, imu_ay, dt=0.5, gps_trustworthy=True,
                       degraded_cn0=None):
    ekf_filter = state.get("ekf_filter")
    
    current_profile = state.get("ekf_profile", "İHA (UAV) - Yüksek Dinamik")
    
    if ekf_filter is None:
        start_lat = raw_lat if gps_trustworthy else state.get("last_good_lat", raw_lat)
        start_lon = raw_lon if gps_trustworthy else state.get("last_good_lon", raw_lon)
        ekf_filter = LooselyCoupledEKF(start_lat, start_lon, profile_name=current_profile)
        heading = math.radians(state.get("prev_heading", 0.))
        speed = state.get("prev_speed", 0.) / 3.6
        ekf_filter.x[2] = speed * math.cos(heading) / 111320
        ekf_filter.x[3] = speed * math.sin(heading) / (111320 * math.cos(math.radians(start_lat)))
        state.ekf_filter = ekf_filter
        state.prev_ekf_profile = current_profile
    elif getattr(state, "prev_ekf_profile", "") != current_profile:
        # Profil değişmiş, filtreyi güncelle
        ekf_filter.update_parameters(current_profile)
        state.prev_ekf_profile = current_profile
    
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be positive and finite")
    # 1. Prediction (IMU her zaman çalışır)
    pred_lat, pred_lon = ekf_filter.predict(imu_ax, imu_ay, dt)
    
    # 2. Update (Sadece GPS güvenilirse/sağlıklıysa)
    state.gnss_measurement_used = False
    if gps_trustworthy or degraded_cn0 is not None:
        covariance = None
        accuracy = state.get('horizontal_accuracy_m')
        if accuracy is not None and math.isfinite(accuracy) and accuracy > 0:
            scale = np.array([111320., 111320.*math.cos(math.radians(raw_lat))])
            covariance = np.diag(np.full(2, accuracy**2)/scale**2)
            # Never make a receiver claim more precise than the configured floor.
            covariance = np.diag(np.maximum(np.diag(covariance), np.diag(ekf_filter.R)))
        if degraded_cn0 is not None:
            # Signal loss is not proof of coordinate manipulation. Downweight only
            # physically plausible fixes; innovation gating still rejects jumps.
            factor = max(16., 16*(45/max(float(degraded_cn0), 1.))**2)
            covariance = (ekf_filter.R if covariance is None else covariance) * factor
        final_lat, final_lon = ekf_filter.update(raw_lat, raw_lon, covariance, gate=True)
        state.gnss_measurement_used = ekf_filter.last_measurement_used
    else:
        # Spoofing/Jamming varsa sadece tahmine güven (Dead Reckoning)
        final_lat, final_lon = pred_lat, pred_lon
        
    scale = np.array([111320., 111320*math.cos(math.radians(ekf_filter.x[0]))])
    position_covariance = ekf_filter.P[:2, :2] * np.outer(scale, scale)
    state.position_sigma_m = math.sqrt(max(0., float(np.linalg.eigvalsh(position_covariance)[-1])))
    return final_lat, final_lon
