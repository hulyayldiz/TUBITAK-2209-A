"""Independent, label-after-inference evaluation of Jammertest 2024 PVT/RF logs."""
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from jammertest_adapter import ARCHIVE, event_intervals, iter_scenarios
from navigation import process_navigation
from real_data_catalog import ROOT
from validation import finish_frame, new_state, step_features

OUTPUT = ROOT / "validation_results" / "jammertest_20261023"
CORE_FILES = ("detection.py", "navigation.py", "fusion.py", "features.py", "receiver_profile.py",
              "ml_detection.py", "config.py")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024*1024):
            digest.update(block)
    return digest.hexdigest()


def _summary(truth, predicted, times):
    truth, predicted = np.asarray(truth, dtype=bool), np.asarray(predicted, dtype=bool)
    tp, fn = int(np.sum(truth & predicted)), int(np.sum(truth & ~predicted))
    starts = np.flatnonzero(truth & ~np.r_[False, truth[:-1]])
    events = []
    for start in starts:
        stop = start
        while stop < len(truth) and truth[stop]:
            stop += 1
        hits = np.flatnonzero(predicted[start:stop])
        events.append(dict(detected=bool(len(hits)), ttd_s=float(times[start+hits[0]]-times[start]) if len(hits) else None,
                           samples=int(stop-start), alarm_samples=int(np.sum(predicted[start:stop]))))
    return dict(tp=tp, fn=fn, recall=tp/(tp+fn) if tp+fn else None,
                episodes=len(events), episodes_detected=sum(event["detected"] for event in events),
                episode_ttd_s=[event["ttd_s"] for event in events], events=events)


def _score_event(start, end, predicted, times):
    mask = (times >= start) & (times <= end)
    observed = np.flatnonzero(mask)
    if not len(observed):
        return dict(evaluable=False, observed_samples=0, event_alarm_samples=0,
                    alarm_present=False, fresh_alarm=False, preexisting_at_onset=None, ttd_s=None)
    hit_indices = observed[predicted[observed]]
    edges = [int(index) for index in hit_indices if index > 0 and not predicted[index-1]]
    prior = np.flatnonzero(times < start)
    preexisting = bool(predicted[prior[-1]]) if len(prior) else bool(predicted[observed[0]])
    first = edges[0] if edges else None
    return dict(evaluable=True, observed_samples=int(len(observed)),
        event_alarm_samples=int(np.sum(predicted[observed])), alarm_present=bool(len(hit_indices)),
        fresh_alarm=first is not None, preexisting_at_onset=preexisting,
        ttd_s=float(times[first]-start) if first is not None else None,
        onset_before_capture=bool(start < times[0]))


def _merge_rf(nav, rf):
    result = pd.merge_asof(nav.sort_values("timestamp_utc"), rf.sort_values("timestamp_utc"),
        on="timestamp_utc", direction="nearest", tolerance=pd.Timedelta(seconds=1.5))
    result["rf_monitor_fresh"] = result["jamming_state"].notna()
    return result


def _run_detector(frame):
    """Run physical rules + declared receiver MON-RF monitor; C/N0/ML are absent."""
    state = new_state()
    state.use_dataset_mode = True
    state.cn0_available = False
    state.imu_data = {}
    state.vae_buffer = []
    state.receiver_profile_name = "receiver-unvalidated"
    physical, receiver, fix_loss, times = [], [], [], []
    previous_time = None
    gap_resets = 0
    for row in frame.itertuples(index=False):
        t = float(row.timestamp_s)
        dt = .5 if previous_time is None else t-previous_time
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("Non-monotonic Jammertest PVT clock")
        if dt > 5.:
            # A receiver outage is not persistence evidence. Start a fresh
            # decision segment at the first returned fix.
            state = new_state()
            state.use_dataset_mode = True
            state.cn0_available = False
            state.imu_data = {}
            state.vae_buffer = []
            state.receiver_profile_name = "receiver-unvalidated"
            state.prev_lat = state.true_lat = state.last_good_lat = float(row.lat)
            state.prev_lon = state.true_lon = state.last_good_lon = float(row.lon)
            state.prev_speed = state.current_speed = float(row.speed_kmh)
            dt = .5
            gap_resets += 1
        state.navigation_time = t
        state.sample_time_s = t
        state.sample_dt = dt
        previous_accuracy = state.get("speed_accuracy_m_s")
        state.speed_accuracy_m_s = float(row.speed_accuracy_m_s) if np.isfinite(row.speed_accuracy_m_s) and row.speed_accuracy_m_s > 0 else None
        state.previous_speed_accuracy_m_s = previous_accuracy
        state.horizontal_accuracy_m = float(row.horizontal_accuracy_m) if np.isfinite(row.horizontal_accuracy_m) and row.horizontal_accuracy_m > 0 else None
        state.receiver_rf_observables = (dict(jamming_state=float(row.jamming_state),
            jam_indicator=float(row.jam_indicator), noise_per_ms=float(row.noise_per_ms),
            agc_count=float(row.agc_count)) if row.rf_monitor_fresh else {})
        state.receiver_rf_observables["fix_valid"] = bool(row.fix_valid)
        observation = (float(row.lat), float(row.lon), float(row.speed_kmh), float("nan"))
        decision, reason, _ = step_features(state, observation, dt)
        fix_loss.append(float(state.get("fix_loss_duration_s", 0.)) >= 3. - 1e-6)
        process_navigation(state, *observation, True, .5, 40., dt=dt, decision=(decision, reason))
        physical.append(decision != "NORMAL")
        receiver.append(bool(state.get("receiver_rf_observables", {}).get("jamming_state") in (2., 3.)))
        times.append(pd.Timestamp(row.timestamp_utc).timestamp())
        finish_frame(state, observation)
        previous_time = t
    return np.asarray(physical), np.asarray(receiver), np.asarray(fix_loss), np.asarray(times), gap_resets


def evaluate():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = {name: sha256_file(ROOT/name) for name in CORE_FILES}
    archive_sha = sha256_file(ARCHIVE)
    scenario_reports, all_rows = [], []
    monitor_values = Counter()
    for folder, metadata, nav, rf in iter_scenarios():
        frame = _merge_rf(nav, rf)
        physical, receiver, fix_loss, epoch, gap_resets = _run_detector(frame)
        intervals = event_intervals(metadata)
        truth = np.zeros(len(frame), dtype=bool)
        event_results = []
        for event in intervals:
            start = pd.Timestamp(event["start_utc"]).timestamp()
            end = pd.Timestamp(event["end_utc"]).timestamp()
            mask = (epoch >= start) & (epoch <= end)
            truth |= mask
            event_result = _score_event(start, end, physical, epoch)
            event_result["event"] = event
            event_result["event_type"] = metadata.get("attack_type")
            event_result["scenario_id"] = metadata.get("scenario_id")
            fix_loss_result = _score_event(start, end, fix_loss, epoch)
            event_result["fix_loss_alarm_present"] = fix_loss_result["alarm_present"]
            event_result["fix_loss_fresh_alarm"] = fix_loss_result["fresh_alarm"]
            event_result["fix_loss_ttd_s"] = fix_loss_result["ttd_s"]
            event_results.append(event_result)
        # Event timing is applied only after all predictions have been produced.
        scores = _summary(truth, physical, epoch)
        all_rows.extend(event_results)
        valid_monitor = frame.loc[frame.rf_monitor_fresh, "jamming_state"]
        monitor_values.update({f"state_{int(value)}": int(count) for value, count in valid_monitor.value_counts().items()})
        outside = ~truth
        report = dict(folder=folder, scenario_id=metadata.get("scenario_id"),
            scenario_name=metadata.get("scenario"), attack_type=metadata.get("attack_type"),
            motion=nav.receiver_motion.iloc[0], pvt_samples=len(nav), monitored_samples=int(frame.rf_monitor_fresh.sum()),
            pvt_gap_resets=gap_resets,
            cno_available=False, independent_imu=False, independent_reference=False,
            event_intervals=len(intervals), event_samples=int(truth.sum()),
            physical_event_sample_recall=scores["recall"],
            physical_event_episode_detection=sum(event["fresh_alarm"] for event in event_results),
            physical_event_alarm_presence=sum(event["alarm_present"] for event in event_results),
            physical_events=len(intervals), physical_event_ttd_s=[event["ttd_s"] for event in event_results
                if event["fresh_alarm"]],
            manufacturer_monitor_event_recall=_summary(truth, receiver, epoch)["recall"],
            physical_alarms_outside_logged_windows=int(np.sum(physical & outside)),
            outside_window_samples=int(outside.sum()),
            outside_window_note="Not scored as false alarms: the publisher labels attack windows, not certified clean intervals.",
            monitor_status_counts=dict(Counter(int(value) for value in valid_monitor)))
        scenario_reports.append(report)
    after = {name: sha256_file(ROOT/name) for name in CORE_FILES}
    if before != after:
        raise RuntimeError("Detector code changed during Jammertest evaluation")
    fresh_ttd = [event["ttd_s"] for event in all_rows if event["fresh_alarm"] and event["ttd_s"] is not None]
    fix_loss_ttd = [event["fix_loss_ttd_s"] for event in all_rows
                    if event["fix_loss_fresh_alarm"] and event["fix_loss_ttd_s"] is not None]
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        source=dict(doi="10.5281/zenodo.15911589", version=3, archive_bytes=ARCHIVE.stat().st_size,
            archive_sha256=archive_sha, publisher_md5="c7b00c63bb1ee5db80c7692a2b06e169",
            timezone_source="Jammertest 2024 analysis documents source event log as CEST (UTC+2); Z suffix mislabels local time.",
            event_time_policy="Scenario attack_log wall time interpreted as Europe/Oslo; PVT real_time parsed as UTC."),
        protocol="Independent public real receiver dataset; no training or threshold fitting. Scenario metadata and event labels are applied after detector inference. Physical rules receive no C/N0. Receiver MON-RF state is evaluated separately. No clean false-alarm rate is claimed.",
        code_sha256=before, scenario_count=len(scenario_reports),
        total_pvt_samples=sum(item["pvt_samples"] for item in scenario_reports),
        total_event_samples=sum(item["event_samples"] for item in scenario_reports),
        total_logged_events=sum(item["physical_events"] for item in scenario_reports),
        physical_events_detected=sum(item["physical_event_episode_detection"] for item in scenario_reports),
        event_summary=dict(evaluable_events=sum(bool(event["evaluable"]) for event in all_rows),
            fresh_alarm_events=sum(bool(event["fresh_alarm"]) for event in all_rows),
            alarm_present_events=sum(bool(event["alarm_present"]) for event in all_rows),
            preexisting_at_onset_events=sum(bool(event["preexisting_at_onset"]) for event in all_rows),
            fresh_ttd_mean_s=float(np.mean(fresh_ttd)) if fresh_ttd else None,
            fresh_ttd_median_s=float(np.median(fresh_ttd)) if fresh_ttd else None,
            fresh_ttd_min_s=float(np.min(fresh_ttd)) if fresh_ttd else None,
            fresh_ttd_max_s=float(np.max(fresh_ttd)) if fresh_ttd else None,
            fix_loss_alarm_events=sum(bool(event["fix_loss_alarm_present"]) for event in all_rows),
            fix_loss_fresh_events=sum(bool(event["fix_loss_fresh_alarm"]) for event in all_rows),
            fix_loss_ttd_median_s=float(np.median(fix_loss_ttd)) if fix_loss_ttd else None),
        scenarios=scenario_reports, receiver_monitor_state_counts=dict(monitor_values),
        limitations=["The data are a Jammertest receiver campaign, not an IHA flight or independent IMU truth.",
            "PVT coordinates and velocity are receiver outputs; they are not ground-truth position or motion.",
            "The dataset has no C/N0 in the integrated NAV-PVT stream; RF/VAE models are not scored.",
            "Unlogged portions are not assumed clean, so they cannot produce a false-alarm-rate estimate.",
            "An uncalibrated jamInd value is retained as evidence only; no universal threshold is imposed."])
    OUTPUT.joinpath("results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    pd.DataFrame(scenario_reports).to_csv(OUTPUT/"scenario_metrics.csv", index=False)
    pd.DataFrame(all_rows).to_csv(OUTPUT/"event_metrics.csv", index=False)
    return report


if __name__ == "__main__":
    result = evaluate()
    print("Fresh event detections:", json.dumps(result["event_summary"], ensure_ascii=False))
