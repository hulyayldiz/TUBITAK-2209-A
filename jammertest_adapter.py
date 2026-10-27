"""Verified adapters for the public Jammertest 2024 u-blox receiver export.

The source archive is retained unchanged. Scenario event clocks are published
with a trailing Z, but the source log is CEST wall time; the source study
documents the +02:00 conversion to UTC. Receiver PVT time remains UTC.
"""
from datetime import datetime, timezone
import json
from pathlib import PurePosixPath
import re
import tarfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from real_data_catalog import ROOT

ARCHIVE = ROOT / "dataset_gercek" / "external" / "jammertest_2024" / "GNSS_DATASET_JAMMING_SPOOFING.tar.gz"
EVENT_ZONE = ZoneInfo("Europe/Oslo")
UTC = timezone.utc


def _event_clock_to_utc(value):
    """Interpret the source's mislabeled Z timestamp as Norway local time."""
    raw = str(value).strip()
    # Published scenario.json timestamps end in Z even though these are CEST
    # wall-clock readings. The Jammertest 2024 analysis confirms CEST is UTC+2.
    local = datetime.fromisoformat(raw.removesuffix("Z").replace(" ", "T"))
    if local.tzinfo is not None:
        local = local.replace(tzinfo=None)
    return local.replace(tzinfo=EVENT_ZONE).astimezone(UTC)


def event_intervals(scenario):
    """Pair logged start/end events and return UTC truth intervals with provenance."""
    intervals, opened = [], None
    for event in scenario.get("attack_log", []):
        text = str(event.get("event", "")).strip()
        stamp = _event_clock_to_utc(event["timestamp_utc"])
        lowered = text.lower()
        if "start" in lowered:
            if opened is not None:
                raise ValueError("Nested Jammertest attack-log start events")
            opened = (stamp, text, event["timestamp_utc"])
        elif "end" in lowered:
            if opened is None or stamp <= opened[0]:
                raise ValueError("Unpaired or non-increasing Jammertest attack-log end")
            intervals.append(dict(start_utc=opened[0].isoformat(), end_utc=stamp.isoformat(),
                start_source_text=opened[1], end_source_text=text,
                start_source_timestamp=opened[2], end_source_timestamp=event["timestamp_utc"],
                source_clock="Europe/Oslo CEST wall time, despite Z suffix"))
            opened = None
    if opened is not None:
        raise ValueError("Unclosed Jammertest attack-log event")
    return intervals


def adapt_nav_pvt(frame, scenario):
    """Normalize one published nav_pvt.csv without fabricating C/N0, IMU, or truth."""
    required = {"real_time", "lat", "lon", "gSpeed", "fixType", "hAcc", "sAcc"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Jammertest NAV-PVT fields missing: {sorted(required-set(frame.columns))}")
    data = frame.copy()
    times = pd.to_datetime(data["real_time"], utc=True, errors="coerce")
    raw_lat = pd.to_numeric(data["lat"], errors="coerce")
    raw_lon = pd.to_numeric(data["lon"], errors="coerce")
    # The CSV export stores u-blox NAV-PVT coordinates in deg*1e-7 but
    # omits the scale in its column names. Reject other representations.
    if not raw_lat.notna().all() or not raw_lon.notna().all():
        raise ValueError("Jammertest coordinate fields contain non-numeric values")
    if float(raw_lat.abs().median()) > 1e-4 or float(raw_lon.abs().median()) > 1e-4:
        raise ValueError("Jammertest coordinate scale differs from the audited 1e-7 degree format")
    lat, lon = raw_lat * 1e7, raw_lon * 1e7
    speed = pd.to_numeric(data["gSpeed"], errors="coerce")
    fix = pd.to_numeric(data["fixType"], errors="coerce")
    hacc = pd.to_numeric(data["hAcc"], errors="coerce")
    sacc = pd.to_numeric(data["sAcc"], errors="coerce")
    valid_fix = (np.isfinite(lat) & np.isfinite(lon) & (fix >= 3) & (speed >= 0)
                 & lat.between(-89.999, 89.999) & lon.between(-180, 180))
    # Keep post-acquisition invalid-fix epochs: dropping them hides GNSS
    # outages, a potentially useful interference indicator. Leading no-fix
    # startup is omitted because there is no prior lock to lose.
    usable_clock = times.notna() & np.isfinite(fix)
    data = pd.DataFrame(dict(timestamp_utc=times[usable_clock],
        lat=lat[usable_clock].where(valid_fix[usable_clock]),
        lon=lon[usable_clock].where(valid_fix[usable_clock]),
        speed_kmh=(speed[usable_clock]*3.6).where(valid_fix[usable_clock]),
        fix_type=fix[usable_clock], fix_valid=valid_fix[usable_clock].astype(bool),
        horizontal_accuracy_m=hacc[usable_clock].where(valid_fix[usable_clock]),
        speed_accuracy_m_s=sacc[usable_clock].where(valid_fix[usable_clock])))
    data = data.sort_values("timestamp_utc", kind="stable").drop_duplicates("timestamp_utc", keep="last")
    data = data.loc[data.fix_valid.cummax()].copy()
    if len(data) < 2 or not data.fix_valid.any() or np.any(data.timestamp_utc.diff().dropna().dt.total_seconds() <= 0):
        raise ValueError("Jammertest PVT clock is not strictly increasing")
    data[["lat", "lon", "speed_kmh"]] = data[["lat", "lon", "speed_kmh"]].ffill()
    # Accuracy fields describe the current fix and must not be carried across
    # an outage; keep them unavailable on invalid-fix epochs.
    data["timestamp_s"] = (data.timestamp_utc-data.timestamp_utc.iloc[0]).dt.total_seconds()
    params = scenario.get("attack_parameters", {})
    motion = str(params.get("Rover states", params.get("rover_states", "unknown"))).strip().lower()
    if motion not in ("static", "stationary", "dynamic", "moving"):
        raise ValueError(f"Unrecognized Jammertest receiver motion contract: {motion!r}")
    data["receiver_id"] = "jammertest-ublox-nav-pvt"
    data["receiver_motion"] = "static" if motion in ("static", "stationary") else "moving" if motion in ("dynamic", "moving") else "unknown"
    data.attrs["source"] = dict(adapter="jammertest-ublox-nav-pvt-v1",
        receiver_id="jammertest-ublox-nav-pvt", receiver_motion=data.receiver_motion.iloc[0],
        receiver_profile="receiver-unvalidated", coordinate_input="degrees times 1e-7",
        speed_origin="u-blox NAV-PVT gSpeed in m/s converted to km/h",
        accuracy_origin="u-blox NAV-PVT hAcc and sAcc; not independent truth",
        cn0_available=False, independent_imu=False, independent_reference=False,
        labels="not embedded in inference rows; scenario event log kept separately",
        event_clock="Europe/Oslo CEST wall time converted to UTC; source JSON incorrectly appends Z",
        raw_observables_missing=["C/N0", "independent IMU/attitude", "independent position reference"])
    return data.reset_index(drop=True)


def adapt_mon_rf(frame):
    """Collapse duplicate per-band MON-RF rows into fresh epoch-level fields."""
    required = {"real_time", "jamInd_01", "jamInd_02", "jammingState_01", "jammingState_02",
                "noisePerMS_01", "noisePerMS_02", "agcCnt_01", "agcCnt_02"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Jammertest MON-RF fields missing: {sorted(required-set(frame.columns))}")
    data = frame.copy()
    data["timestamp_utc"] = pd.to_datetime(data.real_time, utc=True, errors="coerce")
    fields = {}
    for target, pair in (("jam_indicator", ("jamInd_01", "jamInd_02")),
                         ("jamming_state", ("jammingState_01", "jammingState_02")),
                         ("noise_per_ms", ("noisePerMS_01", "noisePerMS_02")),
                         ("agc_count", ("agcCnt_01", "agcCnt_02"))):
        values = data[list(pair)].apply(pd.to_numeric, errors="coerce")
        array = values.to_numpy(dtype=float)
        finite = array[np.isfinite(array)]
        if finite.size and ((finite < 0).any() or (finite > 65535).any()):
            raise ValueError(f"Invalid u-blox MON-RF field: {target}")
        fields[target] = values.max(axis=1)
    data = pd.DataFrame({"timestamp_utc": data.timestamp_utc, **fields}).dropna(subset=["timestamp_utc"])
    data = data.groupby("timestamp_utc", as_index=False, sort=True).max()
    return data


def scenario_key(path):
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", str(path)).strip("_.")
    return clean[:120] or "scenario"


def iter_scenarios(archive_path=ARCHIVE):
    """Yield (folder, metadata, normalized PVT, normalized RF) without extraction."""
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for member in archive.getmembers():
            if PurePosixPath(member.name).name != "scenario.json" or not member.isfile():
                continue
            folder = str(PurePosixPath(member.name).parent)
            metadata = json.load(archive.extractfile(member))
            nav_member = members.get(f"{folder}/nav_pvt.csv")
            rf_member = members.get(f"{folder}/mon_rf.csv")
            if nav_member is None or rf_member is None:
                continue
            nav = pd.read_csv(archive.extractfile(nav_member))
            rf = pd.read_csv(archive.extractfile(rf_member))
            yield folder, metadata, adapt_nav_pvt(nav, metadata), adapt_mon_rf(rf)
