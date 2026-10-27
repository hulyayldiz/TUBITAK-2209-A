import io
import math
import zipfile

import numpy as np
import pandas as pd
import pytest

from dataset_adapters import ecef_to_geodetic, mat_dataframe, texbat_navsol, zip_dataframe
from dataset_loader import _process_dataset_dataframe, get_next_dataset_row, load_dataset_from_local_path
from detection import calculate_metrics
from real_data_catalog import SOURCES
from validation import State


def nav_fixture():
    values = np.zeros((12, 3))
    values[0] = 1705
    values[1] = [100, 101, 102]
    values[3] = 6378137
    values[8] = 10  # ECEF Y is local east at lat=lon=0.
    values[11] = 2
    return {'navsol': values}


def test_wgs84_conversion_and_horizontal_velocity_units():
    lat, lon = ecef_to_geodetic(np.array([6378137., 0.]), np.array([0., 6378137.]), np.array([0., 0.]))
    assert lat == pytest.approx([0., 0.])
    assert lon == pytest.approx([0., 90.])
    frame = texbat_navsol(nav_fixture())
    assert frame.speed_kmh.tolist() == pytest.approx([36.] * 3)
    assert frame.timestamp_s.tolist() == [0., 1., 2.]
    assert 'cn0' not in frame and 'label' not in frame


def test_channel_alignment_does_not_use_future_or_stale_measurements():
    channel = np.zeros((14, 4))
    channel[2] = 1705
    channel[3] = [100, 100, 101, 102]
    channel[4] = [.1, .2, .2, .2]  # all later than nav epochs of same second
    channel[8] = [40, 42, 44, 46]
    channel[9] = 1
    assert texbat_navsol(nav_fixture(), {'channel': channel}).cn0.isna().all()
    channel[4] = 0
    frame = texbat_navsol(nav_fixture(), {'channel': channel})
    assert frame.cn0.tolist() == pytest.approx([41, 44, 46])
    channel[9] = 0  # receiver-invalid measurements never included
    assert texbat_navsol(nav_fixture(), {'channel': channel}).cn0.isna().all()


def zip_bytes(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    out.seek(0)
    return zipfile.ZipFile(out)


def test_zurich_clock_units_body_imu_and_unavailable_sensor_contract():
    gps = 'Timpstemp,imgid,lat,lon,fix_type,vel_n_m_s,vel_e_m_s\n'
    gps += '2000000,2,47.00001,8,3,3,4\n1000000,1,47,8,3,3,4\n'
    imu = 'Timpstemp,x,y,z,Error_count\n1900000,1,2,-9.8,0\n'
    with zip_bytes({'Log Files/OnboardGPS.csv': gps, 'Log Files/RawAccel.csv': imu}) as archive:
        frame = zip_dataframe(archive)
    assert frame.timestamp_s.tolist() == [0., 1.]
    assert frame.speed_kmh.tolist() == pytest.approx([18., 18.])
    assert frame.imu_available.tolist() == [False, True]
    assert frame.attrs['source']['out_of_order_boundaries'] == 1
    state = State()
    assert _process_dataset_dataframe(frame, 'flight.zip', state)
    get_next_dataset_row(state)
    assert state.imu_data == {}
    get_next_dataset_row(state)
    assert state.imu_data['frame'] == 'body'
    assert not state.cn0_available and not state.ground_truth_available
    state.use_dataset_mode = True
    assert all(math.isnan(x) for x in calculate_metrics(state, 'NORMAL', 47, 8, 47, 8))


def test_unknown_matrix_and_ambiguous_zip_are_rejected():
    with pytest.raises(ValueError, match='MAT'):
        mat_dataframe({'big': np.zeros((100, 100))})
    with zip_bytes({'one.csv': 'a\n1', 'two.csv': 'b\n2'}) as archive:
        with pytest.raises(ValueError, match='ZIP'):
            zip_dataframe(archive)


def test_modified_catalog_source_is_rejected_before_replacing_current_data(tmp_path, monkeypatch):
    import hashlib
    import json
    import real_data_catalog as catalog
    monkeypatch.setattr(catalog, 'ROOT', tmp_path)
    monkeypatch.setattr(catalog, 'EXTERNAL', tmp_path/'external')
    path = catalog.EXTERNAL/'one.csv'
    path.parent.mkdir()
    original = b'lat,lon,speed_kmh\n47,8,10\n'
    path.write_bytes(original)
    (tmp_path/'real_data_manifest.json').write_text(json.dumps(dict(files=[dict(
        relative_path='one.csv', sha256=hashlib.sha256(original).hexdigest())])), encoding='utf-8')
    path.write_bytes(original.replace(b'10', b'99'))
    state = State(dataset_df='previous data')
    assert not load_dataset_from_local_path(str(path), state)
    assert state.dataset_df == 'previous data'
    assert 'manifest' in state.dataset_error


def test_reload_resets_dataset_chain_and_navigation_source():
    state = State(last_dataset_hash='old', active_navigation_source=('old',))
    frame = pd.DataFrame(dict(lat=[47.], lon=[8.], speed_kmh=[10.]))
    _process_dataset_dataframe(frame, 'new.csv', state)
    assert 'last_dataset_hash' not in state and 'active_navigation_source' not in state


def test_source_manifest_stays_identical_when_existing_bytes_are_reverified(tmp_path, monkeypatch):
    import download_real_data as downloader
    monkeypatch.setattr(downloader, 'EXTERNAL', tmp_path)
    monkeypatch.setattr(downloader, 'MANIFEST', tmp_path/'manifest.json')
    monkeypatch.setattr(downloader, 'FILES', {'source.csv': 'https://example.com/source.csv'})
    (tmp_path/'source.csv').write_bytes(b'original source')
    downloader.download_all()
    first = downloader.MANIFEST.read_bytes()
    downloader.download_all()
    assert downloader.MANIFEST.read_bytes() == first


@pytest.mark.parametrize('sources_present', [False, True])
def test_legacy_texbat_entry_point_never_silently_generates_mock(tmp_path, monkeypatch, sources_present):
    import runpy
    from pathlib import Path
    import real_data_catalog
    import validate_real_data
    script = Path(__file__).resolve().parents[1]/'texbat_loader.py'
    calls = []
    monkeypatch.setattr(real_data_catalog, 'available_sources',
                        lambda: {'TEXBAT example': tmp_path} if sources_present else {})
    monkeypatch.setattr(validate_real_data, 'validate_sources', lambda: calls.append('real'))
    monkeypatch.chdir(tmp_path)
    if sources_present:
        runpy.run_path(str(script), run_name='__main__')
        assert calls == ['real']
    else:
        with pytest.raises(SystemExit, match='download_real_data'):
            runpy.run_path(str(script), run_name='__main__')
    assert not (tmp_path/'texbat_scenario1_mock.csv').exists()


@pytest.mark.parametrize('name,path', list(SOURCES.items()))
def test_downloaded_real_sources_pass_common_loader(name, path):
    if not path.exists():
        pytest.skip('Run python download_real_data.py for source integration checks')
    state = State()
    assert load_dataset_from_local_path(str(path), state), state.get('dataset_error')
    assert state.dataset_summary['adapter'] in ('texbat-grid-v1', 'zurich-mav-v1', 'cmu-flight-v1')
    assert state.last_uploaded_digest
    frame = state.dataset_df
    assert len(frame) > 1000
    assert np.isfinite(frame[['lat', 'lon', 'speed_kmh', 'timestamp_s']]).all().all()
    assert (frame.timestamp_s.diff().iloc[1:] > 0).all()
    first = get_next_dataset_row(state)
    assert first is not None and not state.ground_truth_available
    assert state.cn0_available == ('TEXBAT' in name)
