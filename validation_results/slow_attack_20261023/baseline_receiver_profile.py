"""Normal-calibrated GRID static receiver monitor; no attack labels are read.

This is an explicit alternative observation domain, not a probability model
trained on synthetic vehicle dynamics. Startup is reported as unassessed.
"""
from collections import deque
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import numpy as np

PROFILE_ID = 'texbat-grid-static-v1'
PROFILE_PATH = Path(__file__).resolve().parent/'models'/'texbat_grid_profile.json'
FEATURES = ('position_rate_m_s', 'clock_rate_m_s', 'cn0_change_db', 'reported_clock_drift_m_s')
WINDOW_S = 10.
WARMUP_S = 30.


class ReceiverWindow:
    def __init__(self):
        self.history = deque()
        self.start = None
        self.streak = 0
        self.duration = 0.

    def observe(self, t, lat, lon, cn0, bias, drift):
        if not all(math.isfinite(x) for x in (t, lat, lon, cn0, bias, drift)):
            self.history.clear()
            self.start = None
            self.streak, self.duration = 0, 0.
            return None
        if self.history and t <= self.history[-1][0]:
            self.history.clear()
            self.start = None
            self.streak, self.duration = 0, 0.
        if self.start is None:
            self.start = t
        self.history.append((t, lat, lon, cn0, bias))
        while len(self.history) > 1 and self.history[1][0] <= t-WINDOW_S:
            self.history.popleft()
        anchor = self.history[0]
        elapsed = t-anchor[0]
        if elapsed < WINDOW_S-1e-6:
            return None
        distance = math.hypot((lat-anchor[1])*111320,
                              (lon-anchor[2])*111320*math.cos(math.radians(lat)))
        return np.array([distance/elapsed, (bias-anchor[4])/elapsed, cn0-anchor[3], drift])


@lru_cache(maxsize=4)
def _read_profile(path, modified_ns, size):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if data.get('schema') != PROFILE_ID or data.get('features') != list(FEATURES):
        raise ValueError('Receiver profile schema mismatch')
    for key in ('center', 'limits'):
        values = np.asarray(data[key], dtype=float)
        if values.shape != (len(FEATURES),) or not np.isfinite(values).all():
            raise ValueError('Invalid receiver profile bounds')
        if key == 'limits' and (values <= 0).any():
            raise ValueError('Invalid receiver profile limits')
    if not math.isfinite(float(data['position_sigma_m'])) or data['position_sigma_m'] <= 0:
        raise ValueError('Invalid receiver position uncertainty')
    if data.get('window_s') != WINDOW_S or data.get('warmup_s') != WARMUP_S:
        raise ValueError('Receiver timing contract mismatch')
    return data, hashlib.sha256(raw).hexdigest()


def load_profile():
    stat = PROFILE_PATH.stat()
    return _read_profile(str(PROFILE_PATH), stat.st_mtime_ns, stat.st_size)


def receiver_decision(state, cn0):
    try:
        profile, version = load_profile()
    except (ValueError, OSError, KeyError, TypeError) as error:
        return dict(available=False, detected=False, status='unavailable', reason=str(error))
    if state.get('receiver_profile_version') != version:
        state.pop('receiver_profile_monitor', None)
        state.receiver_profile_version = version
    monitor = state.get('receiver_profile_monitor')
    if monitor is None:
        monitor = ReceiverWindow()
        state.receiver_profile_monitor = monitor
    obs = state.get('receiver_observables', {})
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in
               (cn0, obs.get('receiver_clock_bias_m'), obs.get('receiver_clock_drift_m_s'))):
        state.pop('receiver_profile_monitor', None)
        return dict(available=False, detected=False, status='unavailable', reason='Missing finite receiver observables')
    frame = state.dataset_df.iloc[state.dataset_index-1]
    state.horizontal_accuracy_m = float(profile['position_sigma_m'])
    values = monitor.observe(state.sample_time_s, float(frame[state.col_map['lat']]),
        float(frame[state.col_map['lon']]), cn0, obs.get('receiver_clock_bias_m', float('nan')),
        obs.get('receiver_clock_drift_m_s', float('nan')))
    warmed = (monitor.start is not None and state.sample_time_s-monitor.start >= WARMUP_S)
    if values is None or not warmed:
        return dict(available=True, detected=False, status='warming_up', ratios=[],
                    reason='30 s receiver acquisition / 10 s observable window')
    ratios = np.abs(values-np.asarray(profile['center'], dtype=float))/np.asarray(profile['limits'], dtype=float)
    # The two clock features are one evidence group, not independent votes.
    # One marginal statistical departure is advisory; require two modalities
    # or a strong (3x calibrated bound) departure before confirming an alarm.
    groups = np.array([ratios[0], max(ratios[1], ratios[3]), ratios[2]])
    marginal = bool(np.any(groups > 1.))
    anomalous = bool(np.count_nonzero(groups > 1.) >= 2 or np.max(groups) >= 3.)
    monitor.streak = monitor.streak+1 if anomalous else 0
    interval = float(state.get('sample_dt', 0.))
    monitor.duration = monitor.duration+interval if anomalous else 0.
    detected = monitor.streak >= 3 and monitor.duration >= 2.-1e-6
    return dict(available=True, detected=detected,
                status='alarm' if detected else 'advisory' if marginal else 'monitoring',
                values=values.tolist(), ratios=ratios.tolist(),
                evidence=[FEATURES[i] for i, ratio in enumerate(ratios) if ratio > 1.],
                reason='Normal-calibrated receiver observables; not proof of spoofing identity')


def calibrate_profile():
    from scipy.io import loadmat
    from dataset_adapters import texbat_navsol
    from real_data_catalog import EXTERNAL, verify_source_file
    root = EXTERNAL/'texbat'/'cleanStatic'
    verify_source_file(root/'navsol.mat')
    frame = texbat_navsol(loadmat(root/'navsol.mat'), loadmat(root/'channel.mat'))
    monitor, samples = ReceiverWindow(), []
    for row in frame.itertuples():
        if row.timestamp_s >= 120.:
            break  # Reserved continuation is never accessed for fitting limits.
        values = monitor.observe(row.timestamp_s, row.lat, row.lon, row.cn0,
                                 row.receiver_clock_bias_m, row.receiver_clock_drift_m_s)
        if values is not None and WARMUP_S <= row.timestamp_s < 120.:
            samples.append(values)
    values = np.asarray(samples)
    if len(values) < 100 or not np.isfinite(values).all():
        raise ValueError('Insufficient trusted normal calibration')
    center = np.median(values, axis=0)
    # Fixed margin and resolution floors; neither attack records nor the
    # reserved normal continuation are used to select these limits.
    limits = np.maximum(np.max(np.abs(values-center), axis=0)*1.5, [.2, .02, .5, .01])
    training = frame.loc[frame.timestamp_s < 120.]
    xy = np.array([(training.lat-training.lat.median())*111320,
        (training.lon-training.lon.median())*111320*math.cos(math.radians(training.lat.median()))])
    sigma = max(.5, float(np.sqrt(np.max(np.linalg.eigvalsh(np.cov(xy))))))
    profile = dict(schema=PROFILE_ID, features=list(FEATURES), center=center.tolist(),
        limits=limits.tolist(), window_s=WINDOW_S, warmup_s=WARMUP_S,
        position_sigma_m=sigma,
        confirmation_s=2., confirmation_samples=3,
        calibration=dict(source='TEXBAT cleanStatic only', start_s=WARMUP_S, stop_s=120.,
            samples=len(samples), development_continuation_start_s=130.,
            continuation_used_for_policy_development=True,
            independent_session_holdout=False,
            files={name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                   for name in ('navsol.mat', 'channel.mat')}),
        policy='Training max deviation times 1.5 with fixed floors; attack labels unused. '
               'Known static GRID scenarios only; alarms are receiver anomalies, not certified spoofing.')
    PROFILE_PATH.write_text(json.dumps(profile, indent=2)+'\n', encoding='utf-8')
    return profile


if __name__ == '__main__':
    print(json.dumps(calibrate_profile(), indent=2))
