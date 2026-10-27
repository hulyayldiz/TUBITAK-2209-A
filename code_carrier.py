"""Causal GPS L1 code-minus-carrier monitor; receiver spoof flags are not inputs.

Geometry and common receiver-clock changes cancel in P - lambda*phase.
Ionosphere, multipath and cycle slips do not: this detects inconsistency, not
cryptographic signal identity. Calibration remains receiver-specific.
"""
from collections import deque
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

CONTRACT = 'grid-gps-l1-cmc-v1'
WAVELENGTH_M = 299792458./1575420000.
WINDOW_S = 20.
FAST_WINDOW_S = 1.
FAST_MIN_SAMPLES = 6
FAST_CONFIRM_S = .4
MIN_CHANNELS = 4
COHERENCE = .75
CONFIRM_S = 3.
# CMC is a 20-second rolling fit. Keep a confirmed alert through one fit
# horizon plus the confirmation interval so a brief loss of coherent channel
# evidence does not make an ongoing event disappear from the operator view.
CLEAR_HOLD_S = WINDOW_S + CONFIRM_S
PROFILE_PATH = Path(__file__).resolve().parent/'models'/'grid_cmc_profile.json'


def grid_cmc(channel, window_s=WINDOW_S, min_samples=20):
    """14 GRID fields on columns, as documented by UT channeldef.txt.

    GPS PRNs 1..32/type 0 only; SBAS is excluded. Pseudorange/phase validity
    and phase/half-cycle flags reset arcs. Error bit 1 (receiver spoof alarm)
    is deliberately ignored, including when deriving validity.
    """
    if (not math.isfinite(float(window_s)) or window_s < 1.
            or not isinstance(min_samples, int) or min_samples < 6):
        raise ValueError('CMC window must be finite and >=1s and require at least six samples')
    channel = np.asarray(channel, dtype=float)
    if channel.ndim != 2 or channel.shape[1] != 14:
        raise ValueError('Expected documented GRID channel matrix')
    if not len(channel):
        return pd.DataFrame(columns=['time', 'cmc_epoch_s', 'cmc_rates', 'cmc_channels', 'cmc_rate_m_s'])
    raw_times = channel[:, 0]*604800.+channel[:, 1]
    if not np.isfinite(raw_times).all() or np.any(np.diff(raw_times) < 0):
        raise ValueError('GRID raw receiver clock must be finite and nondecreasing')
    arcs, rows = {}, []
    starts = np.r_[0, np.flatnonzero(np.diff(raw_times) != 0)+1, len(channel)]
    for first, last in zip(starts[:-1], starts[1:]):
        epoch = channel[first:last]
        t = float(raw_times[first])
        rates, times, seen = [], [], set()
        for sample in epoch:
            if sample[12] != 0 or not 1 <= sample[13] <= 32:
                continue
            prn = int(sample[13])
            if prn in seen:
                raise ValueError('Duplicate GPS PRN in one GRID epoch')
            seen.add(prn)
            valid = (np.isfinite(sample).all() and sample[2] != 9999 and sample[9] == 1
                     and sample[11] >= 5 and (int(sample[10]) & 0b101) == 0
                     and sample[7] > 1e6 and sample[8] >= 25.)
            if not valid:
                arcs.pop(prn, None)
                continue
            arc = arcs.setdefault(prn, deque())
            if arc and (t <= arc[-1][0] or t-arc[-1][0] > .5):
                arc.clear()
            arc.append((t, sample[7]-WAVELENGTH_M*sample[6]))
            while len(arc) > 1 and arc[1][0] <= t-window_s:
                arc.popleft()
            if len(arc) < min_samples or t-arc[0][0] < window_s-1e-6:
                continue
            values = np.asarray(arc)
            x = values[:, 0]-values[:, 0].mean()
            rate = float(x @ (values[:, 1]-values[:, 1].mean())/(x@x))
            rates.append(rate)
            times.append(sample[2]*604800.+sample[3]+sample[4])
        if len(rates) >= MIN_CHANNELS:
            # Store the individual rates so agreement is tested against the
            # calibrated bound, not just a sign that near-zero noise can share.
            rows.append(dict(time=max(times), cmc_epoch_s=t,
                cmc_rates=json.dumps(rates), cmc_channels=len(rates), cmc_rate_m_s=float(np.median(rates))))
    return pd.DataFrame(rows, columns=['time', 'cmc_epoch_s', 'cmc_rates', 'cmc_channels', 'cmc_rate_m_s'])


@lru_cache(maxsize=4)
def _read(path, modified_ns, size):
    raw = Path(path).read_bytes()
    profile = json.loads(raw)
    if (profile.get('schema') != CONTRACT or profile.get('window_s') != WINDOW_S
            or profile.get('fast_window_s') != FAST_WINDOW_S
            or profile.get('fast_min_samples') != FAST_MIN_SAMPLES
            or profile.get('fast_confirm_s') != FAST_CONFIRM_S):
        raise ValueError('Invalid code-carrier calibration schema/window')
    for center_key, limit_key in (('center_m_s', 'limit_m_s'),
                                  ('fast_center_m_s', 'fast_limit_m_s')):
        if (not math.isfinite(float(profile[center_key]))
                or not math.isfinite(float(profile[limit_key])) or profile[limit_key] <= 0):
            raise ValueError('Invalid code-carrier calibration bounds')
    return profile, hashlib.sha256(raw).hexdigest()


def load_profile():
    stat = PROFILE_PATH.stat()
    return _read(str(PROFILE_PATH), stat.st_mtime_ns, stat.st_size)


class CodeCarrierEvidence:
    def __init__(self, confirm_s=CONFIRM_S, clear_hold_s=CLEAR_HOLD_S, min_count=3):
        self.confirm_s = float(confirm_s)
        self.clear_hold_s = float(clear_hold_s)
        self.min_count = int(min_count)
        self._reset()

    def _reset(self):
        self.last_t = None
        self.start_t = None
        self.last_anomalous_t = None
        self.count = 0
        self.detected = False

    def observe(self, t, rates, center, limit):
        if self.last_t is not None and t == self.last_t:
            return self.detected  # A held epoch does not create confirmation time.
        if self.last_t is not None and (t < self.last_t or t-self.last_t > .5):
            self._reset()
        self.last_t = t
        values = np.asarray(rates, dtype=float)-center
        common = float(np.median(values))
        sign = 1. if common >= 0 else -1.
        fraction = float(np.mean(values*sign > limit))
        anomalous = abs(common) > limit and fraction >= COHERENCE
        if anomalous:
            self.start_t = t if self.start_t is None else self.start_t
            self.last_anomalous_t = t
            self.count += 1
        else:
            self.start_t, self.count = None, 0
        confirmed = bool(self.start_t is not None and self.count >= self.min_count
                         and t-self.start_t >= self.confirm_s-1e-6)
        if confirmed:
            self.detected = True
        elif self.last_anomalous_t is not None and t-self.last_anomalous_t > self.clear_hold_s:
            self.detected = False
        return self.detected


def _calibration_bounds(data, safety_factor=1.5):
    if len(data) < 100:
        raise ValueError('Insufficient normal code-carrier calibration')
    center = float(data.cmc_rate_m_s.median())
    limit = max(.15, float(np.max(np.abs(data.cmc_rate_m_s-center)))*safety_factor)
    return center, limit


def decision(state, frame):
    source = state.get('dataset_summary', {}).get('source', {})
    if state.get('receiver_profile_name') != 'texbat-grid-static-v1' or source.get('cmc_contract') != CONTRACT:
        return dict(available=False, detected=False, status='unavailable', reason='No calibrated raw-channel contract')
    try:
        profile, version = load_profile()
        if state.get('code_carrier_version') != version:
            state.pop('code_carrier_monitor', None)
            state.pop('code_carrier_fast_monitor', None)
            state.code_carrier_version = version
        slow_t = float(frame.get('cmc_epoch_s', float('nan')))
        slow_raw_rates = frame.get('cmc_rates', '[]')
        slow_rates = np.asarray(json.loads(slow_raw_rates), dtype=float) if isinstance(slow_raw_rates, str) else np.array([])
        slow_valid = (math.isfinite(slow_t) and slow_rates.ndim == 1 and len(slow_rates) >= MIN_CHANNELS
                      and np.isfinite(slow_rates).all())
        if slow_valid:
            monitor = state.get('code_carrier_monitor')
            if monitor is None:
                monitor = CodeCarrierEvidence()
                state.code_carrier_monitor = monitor
            slow_detected = monitor.observe(slow_t, slow_rates, profile['center_m_s'], profile['limit_m_s'])
        else:
            state.pop('code_carrier_monitor', None)
            slow_detected = False
        fast_t = float(frame.get('fast_cmc_epoch_s', float('nan')))
        fast_raw_rates = frame.get('fast_cmc_rates', '[]')
        fast_rates = np.asarray(json.loads(fast_raw_rates), dtype=float) if isinstance(fast_raw_rates, str) else np.array([])
        fast_valid = (math.isfinite(fast_t) and fast_rates.ndim == 1 and len(fast_rates) >= MIN_CHANNELS
                      and np.isfinite(fast_rates).all())
        if fast_valid:
            fast_monitor = state.get('code_carrier_fast_monitor')
            if fast_monitor is None:
                fast_monitor = CodeCarrierEvidence(confirm_s=FAST_CONFIRM_S)
                state.code_carrier_fast_monitor = fast_monitor
            fast_detected = fast_monitor.observe(fast_t, fast_rates, profile['fast_center_m_s'],
                                                 profile['fast_limit_m_s'])
        else:
            state.pop('code_carrier_fast_monitor', None)
            fast_detected = False
        if not slow_valid and not fast_valid:
            return dict(available=False, detected=False, status='warming_up',
                        reason='Continuous valid GPS L1 arcs unavailable')
        detected = slow_detected or fast_detected
        rates = slow_rates if slow_valid else fast_rates
        center = profile['center_m_s'] if slow_valid else profile['fast_center_m_s']
        limit = profile['limit_m_s'] if slow_valid else profile['fast_limit_m_s']
        common = float(np.median(rates)-center)
        fraction = float(np.mean((rates-center)*(1. if common >= 0 else -1.) > limit))
        return dict(available=True, detected=detected, status='alarm' if detected else 'monitoring',
                    common_rate_m_s=common, limit_m_s=limit, coherent_fraction=fraction, channels=len(rates),
                    fast_detected=fast_detected, window_s=WINDOW_S if slow_valid else FAST_WINDOW_S)
    except (ValueError, OSError, KeyError, TypeError) as error:
        state.pop('code_carrier_monitor', None)
        state.pop('code_carrier_fast_monitor', None)
        return dict(available=False, detected=False, status='unavailable', reason=str(error))


def calibrate():
    from scipy.io import loadmat
    from real_data_catalog import EXTERNAL, verify_source_file
    path = EXTERNAL/'texbat'/'cleanStatic'/'channel.mat'
    verify_source_file(path)
    # Raw RRT seconds, explicitly reserved normal prefix only.
    channels = loadmat(path)['channel'].T
    channels = channels[channels[:, 1] < 120.]
    slow = grid_cmc(channels, window_s=WINDOW_S)
    slow = slow.loc[slow.cmc_epoch_s >= 50.]
    center, limit = _calibration_bounds(slow)
    fast = grid_cmc(channels, window_s=FAST_WINDOW_S, min_samples=FAST_MIN_SAMPLES)
    fast = fast.loc[fast.cmc_epoch_s >= 50.]
    fast_center, fast_limit = _calibration_bounds(fast, safety_factor=1.0)
    profile = dict(schema=CONTRACT, window_s=WINDOW_S, center_m_s=center, limit_m_s=limit,
        fast_window_s=FAST_WINDOW_S, fast_min_samples=FAST_MIN_SAMPLES,
        fast_confirm_s=FAST_CONFIRM_S, fast_center_m_s=fast_center, fast_limit_m_s=fast_limit,
        calibration=dict(source='TEXBAT cleanStatic only', source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         recording_start_s=50., recording_stop_s=120., samples=len(slow),
                         fast_samples=len(fast), independent_holdout=False),
        policy='Common CMC rate; >=4 GPS channels and >=75% coherent rates beyond bound. '
               'The 1s fast fit uses six samples and 0.4s confirmation; the 20s fit uses 3s confirmation. '
               'Confirmed alarms clear only after one slow fit horizon '
               'plus confirmation interval without anomalous evidence. No attack times, receiver spoof '
               'flags or IMU used; not proof of signal identity.')
    PROFILE_PATH.write_text(json.dumps(profile, indent=2)+'\n', encoding='utf-8')
    return profile


if __name__ == '__main__':
    print(json.dumps(calibrate(), indent=2))
