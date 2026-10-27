"""Parser and reference-track join for HK-UrbanSpoof GNSS/INS truth files.

The smoothed GNSS/INS solution is evaluation reference only. It must not be
fed into the detector as if it were an independent onboard sensor.
"""
import hashlib
import json

import pandas as pd

from real_data_catalog import ROOT

DATA_DIR = ROOT / "dataset_gercek" / "external" / "hk_urban_spoof"
MANIFEST = ROOT / "hk_urban_spoof_manifest.json"
REQUIRED = ("UTCTime", "Latitude", "Longitude", "H-Ell", "VEast", "VNorth",
            "VUp", "Roll", "Pitch", "Heading")


def load_reference_track(scenario="S2"):
    """Load a pinned, hash-verified S2/S3 reference track in canonical units."""
    name = f"{str(scenario).upper()}_GT.txt"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next((item for item in manifest["files"] if item["name"] == name), None)
    if entry is None:
        raise ValueError(f"No pinned HK-UrbanSpoof reference file for {scenario}")
    path = DATA_DIR / name
    payload = path.read_bytes()
    if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValueError(f"HK-UrbanSpoof integrity check failed: {name}")
    lines = payload.decode("utf-8-sig").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.split()[:1] == ["UTCTime"]), None)
    if header_index is None or header_index + 2 >= len(lines):
        raise ValueError(f"Missing table header in {name}")
    columns = lines[header_index].split()
    if not set(REQUIRED).issubset(columns):
        raise ValueError(f"Unexpected HK-UrbanSpoof columns in {name}")
    frame = pd.read_csv(path, sep=r"\s+", skiprows=header_index + 2, names=columns,
                        usecols=columns, engine="python")
    frame = frame.apply(pd.to_numeric, errors="coerce").dropna(subset=list(REQUIRED))
    if frame.empty:
        raise ValueError(f"No valid reference rows in {name}")
    if (not frame["UTCTime"].is_monotonic_increasing
            or frame["UTCTime"].duplicated().any()
            or not frame["Latitude"].between(-90, 90).all()
            or not frame["Longitude"].between(-180, 180).all()):
        raise ValueError(f"Invalid time or position values in {name}")
    out = pd.DataFrame({
        "timestamp_utc": pd.to_datetime(frame["UTCTime"], unit="s", utc=True),
        "reference_lat": frame["Latitude"].astype(float),
        "reference_lon": frame["Longitude"].astype(float),
        "reference_altitude_m": frame["H-Ell"].astype(float),
        "reference_velocity_east_m_s": frame["VEast"].astype(float),
        "reference_velocity_north_m_s": frame["VNorth"].astype(float),
        "reference_velocity_up_m_s": frame["VUp"].astype(float),
        "reference_roll_deg": frame["Roll"].astype(float),
        "reference_pitch_deg": frame["Pitch"].astype(float),
        "reference_heading_deg": frame["Heading"].astype(float),
    })
    out.attrs["source"] = {"name": "HK-UrbanSpoof", "scenario": str(scenario).upper(),
        "reference_type": "post-processed smoothed GNSS/INS; evaluation reference only",
        "source_url": manifest["source_url"], "commit": manifest["commit"],
        "license": manifest["license"]}
    return out


def merge_hk_reference(receiver_frame, reference_frame, tolerance_s=0.1):
    """Nearest-time join reference fields; unmatched receiver rows remain NaN."""
    if tolerance_s < 0:
        raise ValueError("tolerance_s must be non-negative")
    if "timestamp_utc" not in receiver_frame or "timestamp_utc" not in reference_frame:
        raise ValueError("Both frames require timestamp_utc")
    left, right = receiver_frame.copy(), reference_frame.copy()
    left["timestamp_utc"] = pd.to_datetime(left["timestamp_utc"], utc=True, errors="raise")
    right["timestamp_utc"] = pd.to_datetime(right["timestamp_utc"], utc=True, errors="raise")
    if right["timestamp_utc"].duplicated().any():
        raise ValueError("Reference timestamps must be unique")
    ref_columns = [c for c in right.columns if c != "timestamp_utc"]
    right = right.rename(columns={c: f"_hk_{c}" for c in ref_columns})
    right = right.rename(columns={"_hk_reference_lat": "reference_lat", "_hk_reference_lon": "reference_lon"})
    joined = pd.merge_asof(left.sort_values("timestamp_utc"), right.sort_values("timestamp_utc"),
        on="timestamp_utc", direction="nearest", tolerance=pd.Timedelta(seconds=tolerance_s))
    # Preserve the signed alignment residual for auditable matching.
    nearest = pd.merge_asof(left[["timestamp_utc"]].sort_values("timestamp_utc"),
        reference_frame[["timestamp_utc"]].assign(_ref_time=pd.to_datetime(reference_frame["timestamp_utc"], utc=True)).sort_values("timestamp_utc"),
        on="timestamp_utc", direction="nearest", tolerance=pd.Timedelta(seconds=tolerance_s))
    joined["reference_time_delta_s"] = (nearest["_ref_time"] - nearest["timestamp_utc"]).dt.total_seconds().to_numpy()
    return joined
