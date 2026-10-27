"""Export verified Jammertest PVT + MON-RF sessions as app-readable CSVs.

The source archive is never extracted or modified. Exported files contain only
receiver observations; attack labels remain in an adjacent audit manifest.
"""
from datetime import datetime, timezone
import json

import pandas as pd

from jammertest_adapter import ARCHIVE, event_intervals, iter_scenarios, scenario_key
from real_data_catalog import ROOT
from validate_jammertest import sha256_file

OUTPUT = ARCHIVE.parent / "normalized"


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    archive_sha = sha256_file(ARCHIVE)
    records = []
    for folder, metadata, nav, rf in iter_scenarios():
        frame = pd.merge_asof(nav.sort_values("timestamp_utc"), rf.sort_values("timestamp_utc"),
            on="timestamp_utc", direction="nearest", tolerance=pd.Timedelta(seconds=1.5))
        frame["rf_monitor_fresh"] = frame.jamming_state.notna()
        frame["session_id"] = scenario_key(folder)
        frame = frame.rename(columns={"jam_indicator":"receiver_jam_indicator",
            "jamming_state":"receiver_jamming_state", "noise_per_ms":"receiver_noise_per_ms",
            "agc_count":"receiver_agc_count", "fix_valid":"receiver_fix_valid"})
        frame["receiver_jamming_state"] = frame["receiver_jamming_state"].where(frame["rf_monitor_fresh"])
        key = scenario_key(folder)
        target = OUTPUT / f"{key}.csv"
        pending = target.with_suffix(".csv.pending")
        frame.drop(columns=["timestamp_utc"]).to_csv(pending, index=False)
        pending.replace(target)
        events = dict(source_scenario=folder, scenario_id=metadata.get("scenario_id"),
            scenario_type=metadata.get("attack_type"), receiver_motion=nav.receiver_motion.iloc[0],
            event_clock_policy="Europe/Oslo CEST wall time converted to UTC; source JSON appends an incorrect Z",
            intervals=event_intervals(metadata))
        event_path = OUTPUT / f"{key}.events.json"
        event_path.write_text(json.dumps(events, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        records.append(dict(scenario=folder, csv_path=target.relative_to(ROOT).as_posix(),
            csv_bytes=target.stat().st_size, csv_sha256=sha256_file(target),
            event_path=event_path.relative_to(ROOT).as_posix(), event_sha256=sha256_file(event_path),
            rows=len(frame), receiver_id=frame.receiver_id.iloc[0],
            receiver_motion=frame.receiver_motion.iloc[0], cno_available=False,
            independent_imu=False, labels_in_csv=False))
        print(folder.encode("ascii", "backslashreplace").decode("ascii"), len(frame), flush=True)
    manifest = dict(schema="jammertest-normalized-v1", created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_doi="10.5281/zenodo.15911589", archive_sha256=archive_sha,
        source_policy="PVT coordinates multiplied by 1e7; gSpeed m/s converted to km/h; MON-RF fields retained; no C/N0/IMU/labels fabricated.",
        files=records)
    dest = OUTPUT/"manifest.json"
    pending = dest.with_suffix(".json.pending")
    pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    pending.replace(dest)
    print(f"Exported {len(records)} sessions to {OUTPUT}")
    return manifest


if __name__ == "__main__":
    export()
