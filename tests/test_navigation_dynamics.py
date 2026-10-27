"""Missing IMU does not imply known zero acceleration or disable security."""
import math

import numpy as np
import pytest

from fusion import LooselyCoupledEKF
from navigation import process_navigation
from validation import new_state, step_features, finish_frame


def test_bounded_normal_turn_is_tracked_without_imu_and_without_relabelled_rejections():
    state = new_state()
    state.prev_speed = 21.6
    state.prev_heading = 0.
    origin = state.prev_lat, state.prev_lon
    for t in np.arange(0., 90., .2):
        state.navigation_time = float(t)
        angle = .2*t
        lat = origin[0]+30.*math.sin(angle)/111320
        lon = origin[1]+30.*(1-math.cos(angle))/(111320*math.cos(math.radians(origin[0])))
        observation = lat, lon, 21.6, float('nan')
        rule, reason, _ = step_features(state, observation, .2)
        result = process_navigation(state, *observation, True, .5, 40., dt=.2, decision=(rule, reason))
        assert result[3] == 'NORMAL'
        assert state.gnss_measurement_used  # zero alarms cannot hide rejected updates
        assert not state.imu_navigation_available
        assert state.effective_acceleration_variance == pytest.approx((2.*9.81)**2/3.)
        finish_frame(state, observation)


def test_independent_imu_and_static_receiver_keep_original_process_noise():
    for kind in ('independent', 'static'):
        state = new_state()
        state.prev_speed = 0.
        if kind == 'independent':
            state.imu_data = dict(frame='navigation', heading_independent=True, accel=dict(x=0., y=0.))
        else:
            state.receiver_profile_result = dict(available=True, motion='static')
        process_navigation(state, state.prev_lat, state.prev_lon, 0., 45., True, .5, 40., decision=('NORMAL', ''))
        assert state.effective_acceleration_variance == state.ekf_filter.acceleration_variance


def test_gps_assisted_attitude_is_not_independent_imu():
    state = new_state()
    state.imu_data = dict(frame='navigation', heading_independent=False, accel=dict(x=100., y=100.))
    process_navigation(state, state.prev_lat, state.prev_lon, 0., 45., True, .5, 40., decision=('NORMAL', ''))
    assert not state.imu_navigation_available
    assert state.effective_acceleration_variance > state.ekf_filter.acceleration_variance


def test_outlier_rejection_and_attack_quarantine_remain_active_without_imu():
    state = new_state()
    state.prev_speed = 0.
    lat, lon = state.prev_lat, state.prev_lon
    for index in range(100):
        state.navigation_time = index*.2
        process_navigation(state, lat, lon, 0., 45., True, .5, 40., dt=.2, decision=('NORMAL', ''))
    state.navigation_time += .2
    result = process_navigation(state, lat+20./111320, lon, 0., 45., True, .5, 40.,
                                dt=.2, decision=('NORMAL', ''))
    assert result[3] == 'SPOOFING' and not state.gnss_measurement_used
    assert state.ekf_filter.last_nis > -2*math.log(.001)
    assert state.navigation_mode == 'MOTION_PREDICTION'
    # Even the original location cannot bypass the security quarantine.
    state.navigation_time += .2
    process_navigation(state, lat, lon, 0., 45., True, .5, 40., dt=.2, decision=('NORMAL', ''))
    assert not state.gnss_measurement_used


def test_process_noise_is_not_inflated_based_on_rejected_residual():
    state = new_state()
    state.prev_speed = 0.
    lat, lon = state.prev_lat, state.prev_lon
    process_navigation(state, lat, lon, 0., 45., True, .5, 40., decision=('NORMAL', ''))
    variance = state.effective_acceleration_variance
    for i in range(10):
        state.navigation_time = 1.+i*.5
        process_navigation(state, lat+1., lon+1., 0., 45., True, .5, 40., decision=('SPOOFING', 'jump'))
        assert not state.gnss_measurement_used
        assert state.effective_acceleration_variance == variance


def test_invalid_variance_does_not_mutate_filter_state():
    ekf = LooselyCoupledEKF(38., 39.)
    before = ekf.x.copy(), ekf.P.copy()
    with pytest.raises(ValueError, match='variance'):
        ekf.predict(1., 1., acceleration_variance=float('nan'))
    assert np.array_equal(ekf.x, before[0]) and np.array_equal(ekf.P, before[1])
