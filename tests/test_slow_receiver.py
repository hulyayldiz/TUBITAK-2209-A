"""Temporal attack evidence, noise rejection and observation-domain limits."""
import numpy as np
import pandas as pd
import pytest

from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from ml_detection import get_hybrid_decision
from receiver_profile import SlowEvidence
from validation import new_state
from tests.test_real_alarm_fix import profile as profile_fixture  # noqa: F401 - pytest fixture


def replay(change, dt=.5, duration=420.):
    frame = pd.DataFrame(dict(timestamp_s=np.arange(0., duration, dt), lat=38., lon=39.,
        speed_kmh=0., cn0=46., receiver_clock_bias_m=100., receiver_clock_drift_m_s=0.))
    change(frame)
    frame.attrs['source'] = dict(receiver_profile='texbat-grid-static-v1')
    state = new_state()
    state.use_dataset_mode = True
    assert _process_dataset_dataframe(frame, 'slow-case', state)
    results = []
    while (row := get_next_dataset_row(state)) is not None:
        get_hybrid_decision('NORMAL', [row[3], 0., 0., 0.], state)
        results.append(dict(time=state.sample_time_s, **state.receiver_profile_result))
    return results


@pytest.mark.parametrize('sign', [-1., 1.])
def test_weak_single_clock_change_eventually_confirms_without_imu(profile_fixture, sign):  # noqa: F811 - pytest fixture parameter
    def attack(frame):
        frame.loc[frame.timestamp_s >= 50., 'receiver_clock_drift_m_s'] = sign*.045
    result = replay(attack)
    alarms = [row for row in result if row['detected']]
    assert alarms and 150. <= alarms[0]['time'] <= 180.
    assert alarms[0]['detection_paths'] == ['persistent_single_group']
    assert not any(row['detected'] for row in result if row['time'] < 50.)


def test_slow_position_pull_below_short_window_bound_is_detected(profile_fixture):  # noqa: F811 - pytest fixture parameter
    def attack(frame):
        frame.lat += (frame.timestamp_s-50.).clip(lower=0)*.1/111320
    result = replay(attack)
    alarms = [row for row in result if row['detected']]
    assert alarms and 190. <= alarms[0]['time'] <= 210.
    assert alarms[0]['detection_paths'] == ['static_cumulative_drift']
    assert max(alarms[0]['ratios']) < 1.  # old short-window logic stays silent


def test_transient_single_group_and_bounded_normal_wander_do_not_alarm(profile_fixture):  # noqa: F811 - pytest fixture parameter
    def normal(frame):
        frame.lat += np.sin(frame.timestamp_s/15.)*2./111320
        frame.loc[frame.timestamp_s.between(50., 55.), 'receiver_clock_drift_m_s'] = .045
    assert not any(row['detected'] for row in replay(normal))


def test_alternating_noise_and_one_large_spike_do_not_build_persistent_evidence():
    monitor = SlowEvidence()
    for index in range(120):
        z = np.array([0., (-1.)**index*1.5, 0., 0.])
        assert max(monitor.observe(index*10., z)) < 6.
    spike = SlowEvidence()
    assert max(spike.observe(0., np.ones(4)*1000.)) == 1.
    for t in range(10, 100, 10):
        assert max(spike.observe(t, np.zeros(4))) == 0.


def test_no_oversampling_advantage_and_clock_channels_are_one_group():
    slow, fast = SlowEvidence(), SlowEvidence()
    z = np.array([0., 1.5, 0., 1.5])
    for t in np.arange(0., 120.1, .1):
        fast.observe(t, z)
    for t in np.arange(0., 120.1, 10.):
        slow.observe(t, z)
    assert fast.scores() == pytest.approx(slow.scores())
    assert fast.scores().tolist() == [0., 6., 0.]


def test_discontinuity_clears_accumulation_anchor_and_requires_warmup():
    from receiver_profile import ReceiverWindow
    monitor = ReceiverWindow()
    for t in range(50):
        monitor.observe(float(t), 38., 39., 46., 100., 0.)
    monitor.slow.observe(40., np.ones(4)*2.)
    monitor.anchor = np.array([38., 39.])
    assert monitor.observe(100., 38., 39., 46., 100., 0.) is None
    assert monitor.start == 100. and monitor.anchor is None
    assert max(monitor.slow.scores()) == 0.
    assert monitor.observe(101., float('nan'), 39., 46., 100., 0.) is None
    assert monitor.start is None


def test_irregular_windows_do_not_count_overlapping_evidence_twice():
    monitor = SlowEvidence()
    z = np.array([0., 1.5, 0., 0.])
    monitor.observe(30., z, window_start=19.8)
    monitor.observe(40., z, window_start=29.8)
    assert monitor.samples == 1
    monitor.observe(40.2, z, window_start=30.)
    assert monitor.samples == 2


def test_persistent_alarm_clears_when_new_observations_return_to_normal(profile_fixture):  # noqa: F811 - pytest fixture parameter
    def attack(frame):
        frame.loc[frame.timestamp_s.between(50., 200.), 'receiver_clock_drift_m_s'] = .045
    result = replay(attack)
    assert any(row['detected'] for row in result)
    assert not any(row['detected'] for row in result if row['time'] >= 270.)


def test_unknown_or_moving_data_never_inherits_static_anchor_logic():
    frame = pd.DataFrame(dict(timestamp_s=np.arange(100.), lat=38.+np.arange(100.)/111320,
                              lon=39., speed_kmh=3.6))
    state = new_state()
    state.use_dataset_mode = True
    _process_dataset_dataframe(frame, 'unknown-moving.csv', state)
    while (row := get_next_dataset_row(state)) is not None:
        get_hybrid_decision('NORMAL', [row[3], 0., 0., 0.], state)
    assert state.get('receiver_profile_monitor') is None
