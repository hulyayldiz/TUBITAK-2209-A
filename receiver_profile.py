"""Normal-calibrated receiver monitor; no attack labels are read in inference.

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
SEQUENTIAL_LIMIT = 6.
STATIC_HOLD_S = 30.


class SlowEvidence:
    """Engineering CUSUM bounds, not z-scores or calibrated probabilities.

    Observe at most once per disjoint 10 s window. Clock channels remain a
    single modality. Normal observations drain evidence; no live refitting.
    """
    def __init__(self):
        self.positive = np.zeros(len(FEATURES))
        self.negative = np.zeros(len(FEATURES))
        self.last_time = None
        self.samples = 0

    def observe(self, t, signed_ratios, window_start=None):
        window_start = t-WINDOW_S if window_start is None else window_start
        if self.last_time is not None and (t-self.last_time < WINDOW_S-1e-6
                                           or window_start < self.last_time-1e-6):
            return self.scores()
        # One isolated spike cannot fill the accumulator or hold it forever.
        bounded = np.clip(signed_ratios, -2., 2.)
        self.positive = np.clip(self.positive+bounded-1., 0., SEQUENTIAL_LIMIT)
        self.negative = np.clip(self.negative-bounded-1., 0., SEQUENTIAL_LIMIT)
        self.last_time = t
        self.samples += 1
        return self.scores()

    def scores(self):
        features = np.maximum(self.positive, self.negative)
        return np.array([features[0], max(features[1], features[3]), features[2]])


class ReceiverWindow:
    def __init__(self):
        self.history = deque()
        self.start = None
        self.streak = 0
        self.duration = 0.
        self.slow = SlowEvidence()
        self.anchor = None
        self.anchor_exceeded_since = None

    def observe(self, t, lat, lon, cn0, bias, drift, enabled=None):
        enabled = [True]*4 if enabled is None else enabled
        required = [t, lat, lon]
        required += [value for value, active in ((cn0, enabled[2]), (bias, enabled[1]),
                                                 (drift, enabled[3])) if active]
        if not all(math.isfinite(x) for x in required):
            self.__init__()
            return None
        if self.history and (t <= self.history[-1][0] or t-self.history[-1][0] > WINDOW_S):
            # Neither stale evidence nor elapsed gaps count as persistence.
            self.__init__()
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


def receiver_decision(state, cn0, *, profile_override=None):
    try:
        if profile_override is not None:
            # Offline candidate evaluation only; live callers always resolve
            # profiles through the validated registry or the legacy contract.
            profile, version = profile_override
        elif str(state.get('receiver_profile_name', '')).startswith('receiver:'):
            from receiver_registry import load_registered_profile
            profile, version = load_registered_profile(state.receiver_profile_name.split(':', 1)[1])
            identity = state.get('receiver_identity', {})
            if (profile['receiver_id'], profile['motion']) != (identity.get('receiver_id'), identity.get('motion')):
                raise ValueError('Receiver identity/motion mismatch; profile not applied')
        elif state.get('receiver_profile_name') == PROFILE_ID:
            profile, version = load_profile()
        else:
            raise ValueError('No matching receiver profile; legacy GRID calibration not applied')
    except (ValueError, OSError, KeyError, TypeError) as error:
        state.pop('receiver_profile_monitor', None)
        return dict(available=False, detected=False, status='unavailable', reason=str(error))
    if state.get('receiver_profile_version') != version:
        state.pop('receiver_profile_monitor', None)
        state.receiver_profile_version = version
    monitor = state.get('receiver_profile_monitor')
    if monitor is None:
        monitor = ReceiverWindow()
        state.receiver_profile_monitor = monitor
    obs = state.get('receiver_observables', {})
    mask = np.asarray(profile.get('enabled_features', [True]*4), dtype=bool)
    bias, drift = obs.get('receiver_clock_bias_m', float('nan')), obs.get('receiver_clock_drift_m_s', float('nan'))
    required = [value for value, active in ((cn0, mask[2]), (bias, mask[1]), (drift, mask[3])) if active]
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in required):
        state.pop('receiver_profile_monitor', None)
        return dict(available=False, detected=False, status='unavailable', reason='Missing finite receiver observables')
    frame = state.dataset_df.iloc[state.dataset_index-1]
    state.horizontal_accuracy_m = float(profile['position_sigma_m'])
    values = monitor.observe(state.sample_time_s, float(frame[state.col_map['lat']]),
        float(frame[state.col_map['lon']]), cn0, bias, drift, enabled=mask)
    warmup_s = float(profile.get('warmup_s', WARMUP_S))
    elapsed = state.sample_time_s-monitor.start if monitor.start is not None else 0.
    warmed = monitor.start is not None and elapsed >= warmup_s
    coverage = dict(profile_id=profile.get('profile_id', PROFILE_ID),
        motion=profile.get('motion', 'static'), warmup_remaining_s=max(0., warmup_s-elapsed),
        enabled_features=[name for name, active in zip(FEATURES, mask) if active])
    if values is None or not warmed:
        # Reported drift is instantaneous: do not hide strong deviations until
        # the position/CN0/clock-bias difference window becomes available.
        strong = bool(mask[3] and abs(drift-profile['center'][3])/profile['limits'][3] >= 3.)
        monitor.streak = monitor.streak+1 if strong else 0
        monitor.duration = monitor.duration+float(state.get('sample_dt', 0.)) if strong else 0.
        detected = monitor.streak >= 3 and monitor.duration >= 2.-1e-6
        assessed = [FEATURES[3]] if mask[3] else []
        return dict(available=True, detected=detected, status='alarm' if detected else 'warming_up', ratios=[],
                    fully_assessed=False, assessed_features=assessed,
                    pending_features=[name for name in coverage['enabled_features'] if name not in assessed],
                    detection_paths=['startup_strong_clock'] if detected else [], **coverage,
                    reason='Receiver acquisition; instantaneous clock drift checked when available; '
                           'windowed checks pending; physical rules remain active')
    signed_ratios = np.where(mask, (values-np.asarray(profile['center'], dtype=float))/np.asarray(profile['limits'], dtype=float), 0.)
    ratios = np.abs(signed_ratios)
    # The two clock features are one evidence group, not independent votes.
    # Short departures still need two modalities or a strong deviation.
    # A separate slower path can confirm persistent single-modality evidence.
    groups = np.array([ratios[0], max(ratios[1], ratios[3]), ratios[2]])
    marginal = bool(np.any(groups > 1.))
    anomalous = bool(np.count_nonzero(groups > 1.) >= 2 or np.max(groups) >= 3.)
    monitor.streak = monitor.streak+1 if anomalous else 0
    interval = float(state.get('sample_dt', 0.))
    monitor.duration = monitor.duration+interval if anomalous else 0.
    immediate = monitor.streak >= 3 and monitor.duration >= 2.-1e-6
    sequential_scores = monitor.slow.observe(state.sample_time_s, signed_ratios,
                                            window_start=monitor.history[0][0])
    sequential = bool(monitor.slow.samples >= 4 and np.max(sequential_scores) >= SEQUENTIAL_LIMIT)

    # Only this explicitly static receiver domain has a fixed-position
    # contract. Freeze the initial robust anchor; following the live solution
    # would learn away a small continuous pull. This is not independent truth.
    displacement = displacement_limit = None
    if profile.get('motion', 'static') == 'static' and mask[0]:
        if monitor.anchor is None:
            monitor.anchor = np.median(np.asarray(monitor.history)[:, 1:3], axis=0)
        lat, lon = float(frame[state.col_map['lat']]), float(frame[state.col_map['lon']])
        displacement = math.hypot((lat-monitor.anchor[0])*111320,
            (lon-monitor.anchor[1])*111320*math.cos(math.radians(monitor.anchor[0])))
        displacement_limit = max(6.*float(profile['position_sigma_m']),
                                 3.*float(profile['limits'][0])*WINDOW_S)
        if displacement > displacement_limit:
            if monitor.anchor_exceeded_since is None:
                monitor.anchor_exceeded_since = state.sample_time_s
        else:
            monitor.anchor_exceeded_since = None
    static_drift = (monitor.anchor_exceeded_since is not None and
                    state.sample_time_s-monitor.anchor_exceeded_since >= STATIC_HOLD_S)
    detected = immediate or sequential or static_drift
    paths = [name for name, active in (('multi_or_strong', immediate),
             ('persistent_single_group', sequential), ('static_cumulative_drift', static_drift)) if active]
    return dict(available=True, detected=detected,
                status='alarm' if detected else 'advisory' if marginal else 'monitoring',
                values=[float(value) if active else None for value, active in zip(values, mask)], ratios=ratios.tolist(),
                fully_assessed=True, assessed_features=coverage['enabled_features'], pending_features=[], **coverage,
                detection_paths=paths, sequential_scores=sequential_scores.tolist(),
                static_displacement_m=displacement, static_displacement_limit_m=displacement_limit,
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
