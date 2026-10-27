import numpy as np
import pandas as pd
import pytest

from hk_urban_spoof import load_reference_track, merge_hk_reference


@pytest.mark.parametrize("scenario", ["S2", "S3"])
def test_pinned_reference_tracks_parse_with_valid_utc_and_position(scenario):
    frame = load_reference_track(scenario)
    assert len(frame) > 10
    assert frame.timestamp_utc.is_monotonic_increasing
    assert frame.reference_lat.between(-90, 90).all()
    assert frame.reference_lon.between(-180, 180).all()
    assert frame.attrs["source"]["reference_type"].startswith("post-processed")


def test_reference_join_keeps_unmatched_receiver_rows_unmatched():
    ref = pd.DataFrame({
        "timestamp_utc": pd.to_datetime(["2025-02-13T07:54:02Z", "2025-02-13T07:54:03Z"], utc=True),
        "reference_lat": [22.0, 22.1], "reference_lon": [114.0, 114.1],
    })
    receiver = pd.DataFrame({"timestamp_utc": pd.to_datetime([
        "2025-02-13T07:54:02.05Z", "2025-02-13T07:54:03.5Z"], utc=True), "lat": [22, 22]})
    out = merge_hk_reference(receiver, ref, tolerance_s=0.1)
    assert out.loc[0, "reference_lat"] == 22.0
    assert out.loc[0, "reference_time_delta_s"] == pytest.approx(-0.05)
    assert np.isnan(out.loc[1, "reference_lat"])

