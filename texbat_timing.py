"""Published TEXBAT timelines and post-hoc scoring, independent of inference.

AFIT 2016 tables 1/2 use the start of DS2 as their common origin. The UT
DS7 description instead states intervals in DS7 recording seconds. Both
interpretations are retained rather than silently resolving their conflict.
"""
import numpy as np
import pandas as pd

AFIT_URL = 'https://radionavlab.ae.utexas.edu/images/stories/files/papers/LemmenesGNSSpaper.pdf'
UT_DS7_URL = 'https://rnl-data.ae.utexas.edu/datastore/texbat/texbat_ds7_and_ds8.pdf'
OFFSETS = dict(cleanStatic=0., ds2=2.99691752, ds3=2.20332084, ds7=0.)


def timeline(scenario, variant='primary'):
    if scenario == 'cleanStatic':
        return dict(scenario=scenario, onset_s=None, activation_s=None, pull_s=None,
                    source_url=AFIT_URL, timing_uncertainty_s=.1)
    if scenario == 'ds7' and variant == 'primary':
        return dict(scenario=scenario, activation_s=None, onset_s=110., capture_s=130.,
            pull_s=150., end_s=468., source_url=UT_DS7_URL, source_pages=[4, 5],
            timing_uncertainty_s=.1, conflict=True, time_reference='DS7 recording start')
    events = dict(ds2=(99.4, 110.1, 133.), ds3=(114.1, 118.9, 195.), ds7=(None, 110., 136.))
    if scenario not in events:
        raise ValueError('No verified timeline for this scenario')
    shift = OFFSETS[scenario]-OFFSETS['ds2']
    activation, onset, pull = events[scenario]
    return dict(scenario=scenario, activation_s=activation-shift if activation is not None else None,
        onset_s=onset-shift, pull_s=pull-shift, end_s=None,
        source_url=AFIT_URL, source_pages=[2, 3, 5, 6], timing_uncertainty_s=.1,
        time_reference='Per-file recording start; converted from common DS2 origin',
        common_reference_shift_s=shift, conflict=scenario == 'ds7')


def recording_clock(nav_contents, channel_contents):
    """Recover file-relative RRT, not time since the first valid nav solution.

ORT-RRT is measured at the nearest channel epoch. Out-of-range matches
and nonmonotonic clocks fail rather than receiving a guessed zero offset.
"""
    from dataset_adapters import _matrix
    nav = _matrix(nav_contents, 'navsol', (12, 13))
    valid = np.isfinite(nav[:, :12]).all(axis=1) & (nav[:, 11] >= 2)
    valid &= np.linalg.norm(nav[:, 3:6], axis=1) > 6e6
    nav = nav[valid]
    channel = _matrix(channel_contents, 'channel', (14,))
    channel = channel[np.isfinite(channel[:, :5]).all(axis=1) & (channel[:, 2] != 9999)]
    if not len(nav) or not len(channel):
        raise ValueError('Recording clock requires valid navigation and channel timestamps')
    week = nav[0, 0]
    nav_ort = (nav[:, 0]-week)*604800+nav[:, 1]+nav[:, 2]
    ort = (channel[:, 2]-week)*604800+channel[:, 3]+channel[:, 4]
    rrt = channel[:, 0]*604800+channel[:, 1]
    epochs = pd.DataFrame(dict(ort=ort, offset=ort-rrt)).groupby('ort', as_index=False).offset.median()
    epochs = epochs.sort_values('ort')
    times = epochs.ort.to_numpy()
    indices = np.searchsorted(times, nav_ort)
    left = np.maximum(0, indices-1)
    right = np.minimum(len(times)-1, indices)
    nearest = np.where(np.abs(nav_ort-times[left]) <= np.abs(nav_ort-times[right]), left, right)
    distance = np.abs(nav_ort-times[nearest])
    if np.any(distance > .25):
        raise ValueError('No channel timestamp within 0.25 s of navigation solution')
    result = nav_ort-epochs.offset.to_numpy()[nearest]
    if not np.isfinite(result).all() or np.any(result < 0) or np.any(np.diff(result) <= 0):
        raise ValueError('Invalid recording clock')
    return result, dict(first_navigation_recording_s=float(result[0]),
        last_navigation_recording_s=float(result[-1]), max_channel_match_error_s=float(distance.max()),
        gps_week=int(week), ort_minus_rrt_s=float(epochs.offset.median()),
        ort_minus_rrt_spread_s=float(epochs.offset.max()-epochs.offset.min()))


def score_timeline(times, predictions, schedule):
    times, predicted = np.asarray(times, dtype=float), np.asarray(predictions, dtype=bool)
    if (times.ndim != 1 or predicted.ndim != 1 or len(times) != len(predicted) or not len(times)
            or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)):
        raise ValueError('Finite increasing times and matching decisions required')
    onset = schedule['onset_s']
    mask = np.ones(len(times), dtype=bool)
    truth = np.zeros(len(times), dtype=bool)
    if onset is not None:
        uncertainty = schedule.get('timing_uncertainty_s', .1)
        activation = schedule.get('activation_s')
        if activation is not None:
            mask &= ~((times >= activation-uncertainty) & (times < onset-uncertainty))
        mask &= ~((times >= onset-uncertainty) & (times <= onset+uncertainty))
        truth = times > onset+uncertainty
        end = schedule.get('end_s')
        if end is not None:
            mask &= times < end-uncertainty
    tp = int(np.sum(mask & truth & predicted))
    fn = int(np.sum(mask & truth & ~predicted))
    fp = int(np.sum(mask & ~truth & predicted))
    tn = int(np.sum(mask & ~truth & ~predicted))
    # A pre-existing false alarm cannot earn a zero event detection delay.
    rising = predicted & ~np.r_[False, predicted[:-1]]
    fresh = np.flatnonzero(rising & mask & truth) if onset is not None else np.array([], dtype=int)
    first = float(times[fresh[0]]) if len(fresh) else None
    phases = {}
    if onset is not None and schedule.get('pull_s') is not None:
        for name, selected in [('injection_before_pull', (times >= onset) & (times < schedule['pull_s'])),
                                ('after_pull', times >= schedule['pull_s'])]:
            selected &= mask & truth
            n = int(selected.sum())
            phases[name] = dict(samples=n, alarm_samples=int(np.sum(selected & predicted)),
                                missed_samples=int(np.sum(selected & ~predicted)))
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, excluded_boundary_or_activation_samples=int((~mask).sum()),
        recall=tp/(tp+fn) if tp+fn else None,
        miss_rate=fn/(tp+fn) if tp+fn else None,
        false_alarm_rate=fp/(fp+tn) if fp+tn else None,
        attack_episode_detected=bool(len(fresh)) if onset is not None else None,
        first_fresh_alarm_recording_s=first,
        ttd_from_signal_onset_s=first-onset if first is not None else None,
        ttd_relative_to_pull_s=first-schedule['pull_s'] if first is not None else None,
        preexisting_alarm_at_onset=bool(predicted[np.searchsorted(times, onset, side='right')-1])
            if onset is not None and onset >= times[0] else False,
        phases=phases)
