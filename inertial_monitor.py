"""Windowed GNSS/independent IMU-AHRS consistency, without attack labels or truth position."""
from collections import deque
import math
import numpy as np


class InertialMonitor:
    def __init__(self, window_s=20.):
        self.window_s = window_s
        self.samples = deque()
        self.time = 0.
        self.dv = np.zeros(2)
        self.displacement = np.zeros(2)
        self.streak = 0

    def update(self, lat, lon, speed, imu, dt):
        if not imu.get("heading_independent", False) or imu.get("frame") != "navigation":
            self.samples.clear()
            self.dv[:] = 0.
            self.displacement[:] = 0.
            self.time = 0.
            self.streak = 0
            return dict(available=False, detected=False, reason="Independent navigation-frame heading/IMU absent")
        heading = float(imu["heading_deg"])
        accel = np.array([imu["accel"]["x"], imu["accel"]["y"]], dtype=float)
        if not all(math.isfinite(x) for x in [lat, lon, speed, heading, dt, *accel]) or dt <= 0:
            raise ValueError("Invalid inertial-monitor observation")
        self.time += dt
        self.displacement += self.dv * dt + .5 * accel * dt**2
        self.dv += accel * dt
        angle = math.radians(heading)
        direction = np.array([math.cos(angle), math.sin(angle)])
        perpendicular = np.array([-direction[1], direction[0]])
        speed_ms = speed / 3.6
        speed_std = float(imu.get("speed_std_m_s", .06))
        heading_std = math.radians(float(imu.get("heading_std_deg", .2)))
        velocity_cov = (speed_std**2 * np.outer(direction, direction)
                        + (speed_ms*heading_std)**2 * np.outer(perpendicular, perpendicular))
        self.samples.append((self.time, lat, lon, speed_ms*direction,
                             self.dv.copy(), self.displacement.copy(), velocity_cov))
        while len(self.samples) > 1 and self.samples[1][0] <= self.time-self.window_s:
            self.samples.popleft()
        anchor_t, anchor_lat, anchor_lon, anchor_velocity, anchor_dv, anchor_displacement, covariance = self.samples[0]
        elapsed = self.time-anchor_t
        if elapsed < 5.:
            self.streak = 0
            return dict(available=True, detected=False, warming_up=True, nis=0., error_m=0.)
        observed = np.array([(lat-anchor_lat)*111320,
                             (lon-anchor_lon)*111320*math.cos(math.radians(anchor_lat))])
        expected = anchor_velocity*elapsed + self.displacement-anchor_displacement-anchor_dv*elapsed
        residual = observed-expected
        noise = float(imu.get("noise_std_m_s2", .02))
        bias = float(imu.get("bias_std_m_s2", .002))
        position_variance = (2*.3**2 + noise**2*elapsed**3*dt/3 + (.5*bias*elapsed**2)**2)
        reference_velocity_covariance = covariance + np.eye(2)*noise**2*elapsed*dt
        covariance = covariance*elapsed**2 + np.eye(2)*position_variance
        nis = float(residual @ np.linalg.solve(covariance, residual))
        anomalous = nis > -2*math.log(.001) and np.linalg.norm(residual) > 2.
        self.streak = self.streak+1 if anomalous else 0
        reference_position = [anchor_lat+expected[0]/111320,
                              anchor_lon+expected[1]/(111320*math.cos(math.radians(anchor_lat)))]
        reference_velocity = anchor_velocity+self.dv-anchor_dv
        return dict(available=True, detected=self.streak >= 3, warming_up=False,
                    anomalous=bool(anomalous), nis=nis, error_m=float(np.linalg.norm(residual)), window_s=elapsed,
                    reference_position=reference_position, reference_velocity=reference_velocity.tolist(),
                    reference_position_covariance=covariance.tolist(),
                    reference_velocity_covariance=reference_velocity_covariance.tolist())


def check_inertial_consistency(state, lat, lon, speed, dt, cn0=float("nan")):
    discontinuity = False
    monitor = state.get("inertial_monitor")
    if monitor is None:
        monitor = InertialMonitor()
        state.inertial_monitor = monitor
    if math.isfinite(cn0) and cn0 < 25.:
        state.inertial_monitor = InertialMonitor()
        result = dict(available=False, detected=False, reason="GNSS too noisy for inertial consistency test")
    else:
        # A discontinuity invalidates the window's anchor, including on recovery.
        previous_lat = state.get("prev_lat", lat)
        previous_lon = state.get("prev_lon", lon)
        jump_m = math.hypot((lat-previous_lat)*111320,
                            (lon-previous_lon)*111320*math.cos(math.radians(lat)))
        if jump_m > max(50., min(abs(state.get("prev_speed", 0.)), 120.) / 3.6 * dt * 3):
            monitor = InertialMonitor()
            state.inertial_monitor = monitor
            discontinuity = True
        result = monitor.update(lat, lon, speed, state.get("imu_data", {}), dt)
    result["discontinuity"] = discontinuity
    result["monitor_window_s"] = monitor.window_s
    state.inertial_consistency = result
    return result
