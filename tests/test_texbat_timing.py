import numpy as np
import pytest

from texbat_timing import timeline, recording_clock, score_timeline


def test_table2_common_origin_is_converted_to_each_recording():
    assert timeline('ds2')['onset_s'] == pytest.approx(110.1)
    assert timeline('ds3')['onset_s'] == pytest.approx(119.69359668)
    assert timeline('ds3')['pull_s'] == pytest.approx(195.79359668)


def test_ds7_conflicting_sources_remain_separate():
    assert timeline('ds7')['onset_s'] == 110.
    assert timeline('ds7')['pull_s'] == 150.
    assert timeline('ds7', 'afit')['onset_s'] == pytest.approx(112.99691752)
    assert timeline('ds7', 'afit')['pull_s'] == pytest.approx(138.99691752)
    assert timeline('ds7')['conflict']


def test_recording_clock_retains_receiver_startup_instead_of_rebasing_to_zero():
    nav = np.zeros((12, 3))
    nav[0] = 1705
    nav[1] = [500033, 500034, 500035]
    nav[3] = 6378137.
    nav[11] = 2
    channel = np.zeros((14, 4))
    channel[1] = [32., 33., 34., 35.]
    channel[2] = 1705
    channel[3] = [500032, 500033, 500034, 500035]
    result, metadata = recording_clock({'navsol': nav}, {'channel': channel})
    assert result == pytest.approx([33., 34., 35.])
    assert metadata['first_navigation_recording_s'] == 33.
    channel[3] += 10
    with pytest.raises(ValueError, match='timestamp'):
        recording_clock({'navsol': nav}, {'channel': channel})


def test_scoring_excludes_activation_and_measures_fresh_post_attack_alarm():
    schedule = dict(onset_s=3.2, activation_s=2.5, pull_s=5., timing_uncertainty_s=0.)
    result = score_timeline(np.arange(10.), [False, False, True, True, True, False, True, True, False, False], schedule)
    assert (result['tp'], result['fn'], result['fp'], result['tn']) == (3, 3, 1, 2)
    assert result['excluded_boundary_or_activation_samples'] == 1
    assert result['ttd_from_signal_onset_s'] == pytest.approx(2.8)
    assert result['preexisting_alarm_at_onset']


def test_preexisting_continuous_false_alarm_cannot_earn_zero_latency():
    schedule = dict(onset_s=3., activation_s=None, pull_s=5., timing_uncertainty_s=.1)
    result = score_timeline(np.arange(10.), [True]*10, schedule)
    assert result['tp'] > 0 and result['fp'] > 0
    assert result['attack_episode_detected'] is False
    assert result['ttd_from_signal_onset_s'] is None


def test_never_detected_episode_reports_misses_and_no_latency():
    result = score_timeline(np.arange(10.), [False]*10, dict(onset_s=3., pull_s=5.))
    assert result['recall'] == 0. and result['miss_rate'] == 1.
    assert result['attack_episode_detected'] is False
    assert result['ttd_from_signal_onset_s'] is None


def test_clean_record_has_no_fabricated_attack_recall():
    result = score_timeline(np.arange(10.), [False]*10, timeline('cleanStatic'))
    assert result['false_alarm_rate'] == 0.
    assert result['recall'] is None and result['ttd_from_signal_onset_s'] is None
