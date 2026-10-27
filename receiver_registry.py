"""Explicit receiver/motion contracts and offline normal-only calibration.

Passing a separate normal-session check authorizes a profile for replay; it
does not certify spoofing detection or the complete navigation chain.
"""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

PROFILE_DIR = Path(__file__).resolve().parent/'receiver_profiles'
SCHEMA = 'receiver-observables-v2'


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value):
        raise ValueError('Profile id must use lowercase letters, digits, hyphens or underscores')
    return value


def constant_column(frame, column):
    if column not in frame or frame[column].isna().any():
        raise ValueError(f'Missing receiver metadata: {column}')
    values = frame[column].astype(str).unique()
    if len(values) != 1 or not values[0].strip() or values[0] != values[0].strip():
        raise ValueError(f'Receiver metadata must be constant: {column}')
    return values[0]


def validate_profile(data, candidate=False):
    from receiver_profile import FEATURES, WINDOW_S
    if not isinstance(data, dict):
        raise ValueError('Receiver profile must be a JSON object')
    if data.get('schema') != SCHEMA or data.get('features') != list(FEATURES):
        raise ValueError('Receiver profile schema mismatch')
    identifier(data.get('profile_id'))
    if not isinstance(data.get('receiver_id'), str) or not 1 <= len(data['receiver_id']) <= 128:
        raise ValueError('Invalid receiver identity')
    if data.get('motion') not in ('static', 'moving'):
        raise ValueError('Receiver motion must be static or moving')
    mask = data.get('enabled_features')
    if not isinstance(mask, list) or len(mask) != 4 or any(type(x) is not bool for x in mask) or not any(mask):
        raise ValueError('Invalid enabled receiver features')
    if data['motion'] == 'moving' and mask[0]:
        raise ValueError('Static position feature cannot be applied to a moving receiver')
    for key in ('center', 'limits'):
        values = np.asarray(data.get(key), dtype=float)
        if values.shape != (4,) or not np.isfinite(values).all() or (key == 'limits' and (values <= 0).any()):
            raise ValueError('Invalid receiver bounds')
    if (data.get('window_s') != WINDOW_S or type(data.get('warmup_s')) not in (int, float)
            or not math.isfinite(data['warmup_s']) or not WINDOW_S <= data['warmup_s'] <= 120.):
        raise ValueError('Invalid receiver acquisition time')
    sigma = data.get('position_sigma_m')
    if type(sigma) not in (int, float) or not math.isfinite(sigma) or sigma <= 0:
        raise ValueError('Invalid receiver position uncertainty')
    calibration = data.get('calibration', {})
    if not isinstance(calibration, dict):
        raise ValueError('Invalid calibration metadata')
    if calibration.get('trusted_normal_attested') is not True:
        raise ValueError('Normal calibration must be explicitly attested')
    if not candidate:
        validation = data.get('validation', {})
        if not isinstance(validation, dict):
            raise ValueError('Invalid validation metadata')
        if (validation.get('status') != 'passed' or validation.get('alarm_samples') != 0
                or validation.get('fully_assessed_samples', 0) < 100):
            raise ValueError('Receiver profile has not passed normal-session validation')
        for section in (calibration, validation):
            if not re.fullmatch(r'[0-9a-f]{64}', str(section.get('source_sha256', ''))):
                raise ValueError('Missing calibration/validation source digest')
            if not isinstance(section.get('session_id'), str) or not 1 <= len(section['session_id']) <= 128:
                raise ValueError('Missing calibration/validation session identity')
        if (calibration['source_sha256'] == validation['source_sha256']
                or calibration['session_id'] == validation['session_id']):
            raise ValueError('Calibration and validation must use separate sessions')
    return data


@lru_cache(maxsize=16)
def _read(path, modified_ns, size):
    raw = Path(path).read_bytes()
    data = validate_profile(json.loads(raw))
    if Path(path).stem != data['profile_id']:
        raise ValueError('Receiver profile filename/id mismatch')
    return data, hashlib.sha256(raw).hexdigest()


def load_registered_profile(profile_id):
    path = PROFILE_DIR/(identifier(profile_id)+'.json')
    stat = path.stat()
    return _read(str(path), stat.st_mtime_ns, stat.st_size)


def source_contract(frame, source):
    """Resolve only an explicitly declared identity; never infer it from values."""
    source = dict(source)
    metadata = {'receiver_id', 'receiver_motion', 'receiver_profile_id'}
    if not metadata.intersection(frame.columns):
        return source
    receiver_id = constant_column(frame, 'receiver_id')
    motion = constant_column(frame, 'receiver_motion')
    if not 1 <= len(receiver_id) <= 128 or motion not in ('static', 'moving'):
        raise ValueError('Invalid receiver identity/motion')
    if source.get('receiver_profile') == 'texbat-grid-static-v1':
        raise ValueError('Cannot override the known GRID contract with receiver metadata')
    requested = constant_column(frame, 'receiver_profile_id') if 'receiver_profile_id' in frame else None
    candidates = []
    if requested:
        profile, _ = load_registered_profile(requested)
        if (profile['receiver_id'], profile['motion']) != (receiver_id, motion):
            raise ValueError('Receiver identity/motion does not match requested profile')
        candidates = [requested]
    else:
        for path in sorted(PROFILE_DIR.glob('*.json')):
            # Corrupt installed profiles must be repaired, not silently used.
            profile, _ = load_registered_profile(path.stem)
            if (profile['receiver_id'], profile['motion']) == (receiver_id, motion):
                candidates.append(profile['profile_id'])
        if len(candidates) > 1:
            raise ValueError('Multiple receiver profiles match; declare receiver_profile_id')
    source.update(receiver_id=receiver_id, receiver_motion=motion,
                  receiver_profile='receiver:'+candidates[0] if candidates else 'receiver-unvalidated')
    return source


def read_normal(path, receiver_id, motion):
    frame = pd.read_csv(path)
    if (constant_column(frame, 'receiver_id'), constant_column(frame, 'receiver_motion')) != (receiver_id, motion):
        raise ValueError('Normal recording receiver identity/motion mismatch')
    session = constant_column(frame, 'session_id')
    required = ['timestamp_s', 'lat', 'lon', 'speed_kmh']
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors='raise')
    if not np.isfinite(frame[required].to_numpy()).all() or not (frame.timestamp_s.diff().iloc[1:] > 0).all():
        raise ValueError('Normal calibration requires finite data and a strictly increasing clock')
    if (len(frame) < 150 or frame.timestamp_s.iloc[-1]-frame.timestamp_s.iloc[0] < 120.
            or not frame.lat.between(-89.999, 89.999).all() or not frame.lon.between(-180, 180).all()
            or (frame.speed_kmh < 0).any()):
        raise ValueError('Insufficient or invalid normal receiver recording')
    from dataset_loader import normalize_column_name, parse_attack_label
    label_aliases = {'label', 'target_label', 'attack', 'attack_label', 'data type', 'attack_mode'}
    for column in frame.columns:
        if normalize_column_name(column) in label_aliases:
            if any(parse_attack_label(value) != 'normal' for value in frame[column]):
                raise ValueError('Attack-labelled data cannot be used for normal calibration')
    return frame, session, hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess_normal(frame, profile):
    from receiver_profile import receiver_decision
    from validation import State
    state = State(dataset_df=frame, col_map={'lat': 'lat', 'lon': 'lon'}, receiver_profile_name='candidate')
    alarms = fully_assessed = 0
    for index, row in enumerate(frame.itertuples()):
        state.dataset_index = index+1
        state.sample_time_s = float(row.timestamp_s)
        state.sample_dt = float(row.timestamp_s-frame.timestamp_s.iloc[index-1]) if index else .5
        state.receiver_observables = {name: float(getattr(row, name)) for name in
            ('receiver_clock_bias_m', 'receiver_clock_drift_m_s') if hasattr(row, name)}
        result = receiver_decision(state, float(getattr(row, 'cn0', float('nan'))),
                                   profile_override=(profile, 'offline-candidate'))
        alarms += bool(result['detected'])
        fully_assessed += bool(result.get('fully_assessed'))
    return dict(alarm_samples=alarms, fully_assessed_samples=fully_assessed, samples=len(frame))


def calibrate(normal, validation, *, receiver_id, profile_id, motion, trusted_normal=False,
              warmup_s=30., position_sigma_m=None):
    from receiver_profile import FEATURES, ReceiverWindow, WINDOW_S
    if not trusted_normal:
        raise ValueError('Explicit trusted-normal attestation is required; no automatic online fitting')
    identifier(profile_id)
    if motion not in ('static', 'moving') or not WINDOW_S <= warmup_s <= 120.:
        raise ValueError('Invalid receiver motion or warmup')
    training, training_session, training_sha = read_normal(normal, receiver_id, motion)
    heldout, heldout_session, heldout_sha = read_normal(validation, receiver_id, motion)
    if training_sha == heldout_sha or training_session == heldout_session:
        raise ValueError('Calibration and validation must use separate sessions')
    mask = [motion == 'static', 'receiver_clock_bias_m' in training, 'cn0' in training,
            'receiver_clock_drift_m_s' in training]
    if not any(mask):
        raise ValueError('No usable receiver observables; moving position alone is not a static reference')
    required = [column for column, enabled in zip(
        ('lat', 'receiver_clock_bias_m', 'cn0', 'receiver_clock_drift_m_s'), mask) if enabled]
    for frame in (training, heldout):
        for column in required:
            if column not in frame or not np.isfinite(pd.to_numeric(frame[column], errors='coerce')).all():
                raise ValueError(f'Missing finite receiver observable: {column}')
    if motion == 'moving' and position_sigma_m is None:
        raise ValueError('Moving receiver needs a documented position_sigma_m; trajectory spread is not sensor noise')
    if position_sigma_m is None:
        xy = np.array([(training.lat-training.lat.median())*111320,
            (training.lon-training.lon.median())*111320*np.cos(np.radians(training.lat.median()))])
        position_sigma_m = max(.5, float(np.sqrt(np.max(np.linalg.eigvalsh(np.cov(xy))))))
    monitor, samples = ReceiverWindow(), []
    start = float(training.timestamp_s.iloc[0])
    for row in training.itertuples():
        values = monitor.observe(float(row.timestamp_s), float(row.lat), float(row.lon),
            float(getattr(row, 'cn0', float('nan'))),
            float(getattr(row, 'receiver_clock_bias_m', float('nan'))),
            float(getattr(row, 'receiver_clock_drift_m_s', float('nan'))), enabled=mask)
        if values is not None and row.timestamp_s-start >= warmup_s:
            samples.append(values)
    if len(samples) < 100:
        raise ValueError('Insufficient fully observed calibration windows')
    values = np.asarray(samples)
    values[:, ~np.asarray(mask)] = 0.
    center = np.median(values, axis=0)
    limits = np.maximum(np.max(np.abs(values-center), axis=0)*1.5, [.2, .02, .5, .01])
    profile = dict(schema=SCHEMA, profile_id=profile_id, receiver_id=receiver_id, motion=motion,
        features=list(FEATURES), enabled_features=mask, center=center.tolist(), limits=limits.tolist(),
        position_sigma_m=position_sigma_m, window_s=WINDOW_S, warmup_s=warmup_s,
        calibration=dict(trusted_normal_attested=True, source_sha256=training_sha,
                         session_id=training_session, samples=len(samples)),
        validation=dict(source_sha256=heldout_sha, session_id=heldout_session),
        policy='Normal-only receiver-specific bounds; separate normal session; not attack/field certification.')
    validate_profile(profile, candidate=True)
    assessment = assess_normal(heldout, profile)
    profile['validation'].update(assessment, status='passed' if
        assessment['alarm_samples'] == 0 and assessment['fully_assessed_samples'] >= 100 else 'failed')
    return profile


def save_profile(profile):
    validate_profile(profile)  # Failed candidates can be reported but never installed.
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILE_DIR/(identifier(profile['profile_id'])+'.json')
    # Exclusive creation preserves existing calibration and experiment history.
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(profile, ensure_ascii=False, indent=2)+'\n')
    return path
