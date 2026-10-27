"""Explicit FRU body-to-NEU specific-force rotation; no inferred absolute heading."""
import math
import numpy as np


def navigation_imu(sample):
    if sample.get("frame") == "navigation":
        return sample
    attitude = sample.get("attitude", {})
    if not attitude.get("valid", False) or not attitude.get("heading_independent", False):
        return dict(sample, navigation_unavailable="Independent roll/pitch/yaw required")
    if attitude.get("convention") != "FRU_to_NEU":
        return dict(sample, navigation_unavailable="Unknown attitude convention")
    roll, pitch, yaw = [math.radians(float(attitude[key])) for key in ("roll_deg", "pitch_deg", "yaw_deg")]
    c, s = math.cos, math.sin
    rx = np.array([[1,0,0],[0,c(roll),-s(roll)],[0,s(roll),c(roll)]])
    ry = np.array([[c(pitch),0,s(pitch)],[0,1,0],[-s(pitch),0,c(pitch)]])
    rz = np.array([[c(yaw),-s(yaw),0],[s(yaw),c(yaw),0],[0,0,1]])
    raw = np.array([sample["accel"][axis] for axis in "xyz"], dtype=float)
    bias = np.array(sample.get("accel_bias_m_s2", [0,0,0]), dtype=float)
    if not np.isfinite([roll, pitch, yaw, *raw, *bias]).all():
        raise ValueError("Nonfinite attitude/acceleration")
    acceleration = rz @ ry @ rx @ (raw-bias) - np.array([0,0,9.80665])
    return dict(sample, frame="navigation", heading_independent=True,
                heading_deg=float(attitude["yaw_deg"]),
                accel=dict(zip("xyz", acceleration.tolist())))
