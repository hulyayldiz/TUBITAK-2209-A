import hashlib

import pandas as pd
import pytest

from dataset_adapters import cmu_flight_dataframe
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row
from validation import State


def test_cmu_schema_uses_latitude_y_longitude_x_and_measured_speed():
    raw = pd.DataFrame(dict(time=[0., .2], position_x=[-79., -79.], position_y=[40., 40.],
                            velocity_x=[3., 3.], velocity_y=[4., 4.], speed=[99., 99.]))
    data = cmu_flight_dataframe(raw)
    assert data.lat.tolist() == [40., 40.] and data.lon.tolist() == [-79., -79.]
    assert data.speed_kmh.tolist() == [18., 18.]  # not the commanded 99 m/s
    assert data.horizontal_accuracy_m.tolist() == [2., 2.]
    state = State()
    _process_dataset_dataframe(raw, 'CMU.csv', state)
    assert get_next_dataset_row(state)[:3] == (40., -79., 18.)
    assert not state.cn0_available and not state.ground_truth_available
    assert state.imu_data == {} and state.reference_position is None


def test_cmu_invalid_or_reversed_clock_is_not_silently_fixed():
    raw = pd.DataFrame(dict(time=[.2, 0.], position_x=[-79., -79.], position_y=[40., 40.],
                            velocity_x=[3., 3.], velocity_y=[4., 4.]))
    with pytest.raises(ValueError, match='clock'):
        cmu_flight_dataframe(raw)


def test_independent_evaluation_freeze_detects_a_changed_detector(tmp_path, monkeypatch):
    import validate_independent_real as evaluator
    monkeypatch.setattr(evaluator, 'ROOT', tmp_path)
    (tmp_path/'model').write_bytes(b'original')
    frozen = dict(sha256={'model': hashlib.sha256(b'original').hexdigest()})
    evaluator.check_freeze(frozen)
    (tmp_path/'model').write_bytes(b'changed')
    with pytest.raises(ValueError, match='invalidated'):
        evaluator.check_freeze(frozen)
