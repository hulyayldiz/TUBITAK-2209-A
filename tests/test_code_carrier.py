import json

import numpy as np
import pandas as pd
import pytest

from code_carrier import grid_cmc, CodeCarrierEvidence, WAVELENGTH_M, CLEAR_HOLD_S


def channels(pull=0., slip=False, error_bits=0, moving=True):
    rows = []
    for t in np.arange(0., 80.1, .2):
        for prn in range(1, 7):
            row = np.zeros(14)
            row[1:5] = [t, 1705., 1000.+int(t), t-int(t)]
            geometry = 2e7+prn*1e5+(100.+prn)*t if moving else 2e7+prn*1e5
            clock = 3e5 if t >= 40. else 0.  # matched ORT/code/phase change cancels
            row[6] = (geometry+clock)/WAVELENGTH_M
            row[7] = geometry+clock+max(0., t-30.)*pull
            row[8:14] = [45., 1., error_bits, 6., 0., prn]
            if slip and prn == 1 and t >= 40.:
                row[6] += 1000.
                if t < 40.2:
                    row[10] = 1.  # phase anomaly resets this arc
            rows.append(row)
    return np.asarray(rows)


def test_code_carrier_cancels_motion_and_common_receiver_clock_steps():
    frame = grid_cmc(channels())
    assert frame.cmc_channels.min() == 6
    assert np.max(np.abs(frame.cmc_rate_m_s)) < 1e-6


def test_code_only_pull_is_observable_without_imu_or_spoofing_flags():
    frame = grid_cmc(channels(pull=1.2))
    assert frame.cmc_rate_m_s.iloc[-1] == pytest.approx(1.2)
    same = grid_cmc(channels(pull=1.2, error_bits=2))
    pd.testing.assert_frame_equal(frame, same)  # receiver spoof flag is never evidence


def test_short_cmc_window_reduces_detection_delay_without_changing_confirmation():
    import json
    detected_at = {}
    for window in (5., 20.):
        frame = grid_cmc(channels(pull=1.2), window_s=window)
        monitor = CodeCarrierEvidence()
        for row in frame.itertuples():
            if monitor.observe(row.cmc_epoch_s, json.loads(row.cmc_rates), 0., .15):
                detected_at[window] = row.cmc_epoch_s
                break
    assert detected_at[5.] < detected_at[20.]


def test_cycle_slip_resets_arc_and_one_bad_satellite_does_not_vote_as_six():
    data = grid_cmc(channels(slip=True))
    assert np.max(np.abs(data.cmc_rate_m_s)) < 1e-6
    assert data.loc[data.cmc_epoch_s.between(40., 59.8), 'cmc_channels'].max() == 5
    evidence = CodeCarrierEvidence()
    for t in np.arange(0., 30., .2):
        assert not evidence.observe(float(t), [20., 0., 0., 0., 0., 0.], 0., .15)


def test_confirmation_counts_record_time_and_does_not_bridge_gaps():
    monitor = CodeCarrierEvidence()
    assert not monitor.observe(0., [1.]*6, 0., .15)
    for _ in range(100):
        assert not monitor.observe(0., [1.]*6, 0., .15)
    assert not monitor.observe(10., [1.]*6, 0., .15)
    for t in np.arange(10.2, 13.1, .2):
        detected = monitor.observe(float(t), [1.]*6, 0., .15)
    assert detected
    assert monitor.observe(13.2, [0.]*6, 0., .15)
    held = [monitor.observe(float(t), [0.]*6, 0., .15)
            for t in np.arange(13.4, 13.2+CLEAR_HOLD_S+.3, .2)]
    assert any(held) and not held[-1]


def test_clear_hold_does_not_hide_a_missing_data_gap():
    monitor = CodeCarrierEvidence()
    for t in np.arange(0., 3.1, .2):
        detected = monitor.observe(float(t), [1.]*6, 0., .15)
    assert detected
    assert not monitor.observe(4., [1.]*6, 0., .15)  # >0.5s discontinuity resets state


def test_channel_clock_and_duplicate_prn_are_rejected():
    data = channels()
    with pytest.raises(ValueError, match='nondecreasing'):
        grid_cmc(data[::-1])
    data[1, 13] = data[0, 13]
    with pytest.raises(ValueError, match='Duplicate'):
        grid_cmc(data)


def test_raw_channel_contract_is_not_inferred_from_csv_columns():
    from code_carrier import decision
    from validation import State
    state = State(receiver_profile_name='texbat-grid-static-v1', dataset_summary={'source': {}})
    result = decision(state, dict(cmc_epoch_s=30., cmc_rates=json.dumps([1.]*6)))
    assert not result['available'] and not result['detected']


def test_fast_monitor_can_alarm_before_slow_window_is_ready():
    from code_carrier import decision, CONTRACT
    from validation import State
    state = State(receiver_profile_name='texbat-grid-static-v1',
                  dataset_summary={'source': {'cmc_contract': CONTRACT}})
    result = None
    for t in np.arange(0., 3.1, .2):
        result = decision(state, dict(fast_cmc_epoch_s=float(t),
                                      fast_cmc_rates=json.dumps([1.]*6)))
    assert result['available'] and result['detected'] and result['fast_detected']
    assert result['window_s'] == 1.
