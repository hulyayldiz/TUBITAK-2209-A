"""Read-only local data audit against a previously fetched upstream metadata snapshot."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "validation_results/data_audit_20261023"


def git_blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()


def describe_csv(path):
    raw = path.read_bytes()
    frame = pd.read_csv(path)
    label = next((key for key in ("Data Type", "label", "Attack_Flag", "target_label") if key in frame), None)
    return dict(file=path.relative_to(ROOT).as_posix(), rows=len(frame), columns=frame.columns.tolist(),
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), git_blob_sha1=git_blob(raw),
                labels={str(key): int(value) for key, value in frame[label].value_counts(dropna=False).items()} if label else None)


def source_match(path, repository, upstream):
    raw = path.read_bytes()
    exact = git_blob(raw) == upstream["git_blob_sha1"]
    lf = git_blob(raw.replace(b"\r\n", b"\n")) == upstream["git_blob_sha1"]
    return dict(repository=repository["repository"], commit=repository["commit"],
                upstream_git_blob_sha1=upstream["git_blob_sha1"], exact_bytes=exact,
                matches_after_crlf_to_lf=lf, upstream_url=upstream["url"])


def audit(snapshot):
    av, gnss = snapshot["repositories"]
    av_files = {entry["path"]: entry for entry in av["files"]}
    gnss_files = {entry["path"]: entry for entry in gnss["files"]}
    base_path = ROOT / "dataset_gercek/AV-GPS-Dataset-1.csv"
    base = pd.read_csv(base_path)
    rows = []
    paths = sorted((ROOT / "dataset_gercek").glob("*.csv")) + [
        ROOT / "dataset_gercek/GNSS_Jamming/jamming_metadata_by_day_Antarctica.csv",
        ROOT / "texbat_scenario1_mock.csv", ROOT / "ornek_dron_saldiri_logu.csv",
        ROOT / "gnss_training_dataset.csv", ROOT / "validation_results/synthetic_training.csv"]
    for path in paths:
        if not path.exists():
            continue
        info = describe_csv(path)
        if path.name in av_files:
            info["upstream"] = source_match(path, av, av_files[path.name])
            info["classification"] = "publisher_released_field_dataset_copy" if info["upstream"]["exact_bytes"] else "unverified_modified_copy"
        elif path.name in gnss_files:
            info["upstream"] = source_match(path, gnss, gnss_files[path.name])
            info["classification"] = "publisher_daily_aggregate_not_raw_navigation" if info["upstream"]["matches_after_crlf_to_lf"] else "unverified_aggregate"
            frame = pd.read_csv(path)
            info["jamming_days"] = int(frame["jamming_detected"].sum())
            info["jamming_event_count"] = int(frame["jamming_event_count"].sum())
        elif path.parent.name == "dataset_gercek":
            frame = pd.read_csv(path)
            anchors = ("Run Time", "GPS Latitude", "GPS Longitude")
            if (len(frame) == len(base) and set(base).issubset(frame)
                    and all((base[key].eq(frame[key]) | (base[key].isna() & frame[key].isna())).all()
                            for key in anchors)):
                identical = [column for column in base
                             if (base[column].eq(frame[column]) | (base[column].isna() & frame[column].isna())).all()]
                info.update(classification="modified_AV1_not_original_field_recording",
                            base=base_path.relative_to(ROOT).as_posix(), identical_base_columns=identical,
                            changed_base_columns=[column for column in base if column not in identical],
                            added_columns=[column for column in frame if column not in base],
                            changed_labels=int(base["Data Type"].ne(frame["Data Type"]).sum()),
                            measured_origin_of_added_signal_column="not documented")
            else:
                info["classification"] = "unverified"
        elif path.name == "gnss_training_dataset.csv":
            info["classification"] = "legacy_training_log_origin_unverified"
        else:
            info["classification"] = "synthetic_generated_by_project_code"
        rows.append(info)
    raw_files = [path.relative_to(ROOT).as_posix() for path in (ROOT / "dataset_gercek").rglob("*")
                 if path.is_file() and path.suffix.lower() in (".ubx", ".bin", ".iq", ".zip", ".mat")]
    return dict(verified_on=snapshot["verified_on"], source_snapshot="upstream_snapshot.json",
                files=rows, available_raw_capture_files=raw_files,
                scope="Provenance and byte consistency, not independent certification of publishers' experiments")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_OUTPUT / "upstream_snapshot.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "inventory.json")
    args = parser.parse_args()
    snapshot_bytes = args.snapshot.read_bytes()
    result = audit(json.loads(snapshot_bytes))
    result["source_snapshot_sha256"] = hashlib.sha256(snapshot_bytes).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in result["files"]:
        print(f"{row['file']}: {row['rows']} rows, {row['classification']}")


if __name__ == "__main__":
    main()
