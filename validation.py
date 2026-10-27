"""Reproducible offline validation. No radio transmission or hardware success claims."""
import argparse
import hashlib
import json
import math
import platform
import random
import time
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import torch

import config
from detection import run_firewall_rules
from features import extract_features, FEATURE_SCHEMA
from ml_detection import get_hybrid_decision, load_rf_bundle, load_scaler, load_vae_model
from navigation import process_navigation
from sensors import simulate_sensors, calculate_distance_km


class State(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def new_state():
    return State(true_lat=config.DEFAULT_LAT, true_lon=config.DEFAULT_LON,
                 prev_lat=config.DEFAULT_LAT, prev_lon=config.DEFAULT_LON,
                 last_good_lat=config.DEFAULT_LAT, last_good_lon=config.DEFAULT_LON,
                 current_speed=60., prev_speed=60., current_heading=45., prev_heading=45.,
                 acceleration=0., attack_mode="normal", prev_attack_mode="normal",
                 spoof_offset_lat=0., spoof_offset_lon=0., spoof_speed_offset=0.,
                 spoof_persistence=0, jamming_state="none", ins_active=False,
                 vae_buffer=[], navigation_time=0., sim_logs=[])


def label_at(scenario, t, duration):
    # A minute of clean pre-roll; recovery occupies the final quarter.
    return scenario if scenario != "normal" and 60 <= t < duration * .75 else "normal"


def step_features(state, observation, dt):
    lat, lon, speed, cn0 = observation
    rule, reason = run_firewall_rules(state, lat, lon, cn0, speed,
                                     config.NOMINAL_CN0, .5, 40., 45., dt=dt)
    features = extract_features(state, lat, lon, speed, cn0, dt)
    return rule, reason, features


def finish_frame(state, observation):
    state.prev_lat, state.prev_lon, state.prev_speed, _ = observation
    state.prev_heading = state.get("observed_heading", state.prev_heading)
    state.prev_attack_mode = state.attack_mode


def synthetic_features(seed, scenario, steps=1200, dt=.5):
    random.seed(seed)
    state = new_state()
    records = []
    for index in range(steps):
        t = index * dt
        state.attack_mode = label_at(scenario, t, steps * dt)
        observation = simulate_sensors(state, dt=dt)
        _, _, features = step_features(state, observation, dt)
        records.append(dict(zip(["cn0", "accel", "heading_drift", "residual"], features),
                            target_label=("SPOOFING" if state.attack_mode == "slow_spoofing"
                                          else state.attack_mode.upper()),
                            run_id=str(seed), sample_time_s=t))
        finish_frame(state, observation)
    return records


def train_synthetic(output):
    """Training seeds are disjoint from calibration and evaluation seeds."""
    import train_model as training
    records = []
    for seed in (11, 22, 33):
        for scenario in ("normal", "jamming", "spoofing", "slow_spoofing"):
            records.extend(synthetic_features(seed, scenario, steps=720))
    data = pd.DataFrame(records)
    path = output / "synthetic_training.csv"
    data.to_csv(path, index=False)
    random.seed(123)
    np.random.seed(123)
    torch.manual_seed(123)
    _, _, report, _ = training.train_random_forest(data)
    vae_model, _, vae_report = training.train_vae(data)
    (output / "training_report.txt").write_text(report + "\n\n" + vae_report, encoding="utf-8")
    for loader in (load_rf_bundle, load_scaler, load_vae_model):
        loader.clear()
    # Calibration uses separate normal runs, including persistence of correlated
    # windows. Evaluation outcomes and attack labels are not calibration inputs.
    model = load_vae_model()
    if model is None or vae_model is None:
        raise RuntimeError("VAE failed to load after training")
    calibration = getattr(vae_model, "normal_calibration", None)
    if calibration is None:
        raise RuntimeError("Separate normal-run calibration missing")
    (output / "normal_calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    load_vae_model.clear()
    return {"source": "synthetic only", "training_seeds": [11, 22, 33],
            "calibration_seeds": calibration["calibration_seeds"], "rows": len(data),
            "normal_calibration_quantile": calibration["normal_quantile"],
            "vae_threshold": calibration["threshold"], "normal_calibration": calibration,
            "feature_schema": FEATURE_SCHEMA, "training_csv_sha256": sha256(path)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def classification_summary(truth, predicted, times):
    truth, predicted = np.asarray(truth, bool), np.asarray(predicted, bool)
    tp = int(np.sum(truth & predicted)); fn = int(np.sum(truth & ~predicted))
    fp = int(np.sum(~truth & predicted)); tn = int(np.sum(~truth & ~predicted))
    starts = np.flatnonzero(truth & ~np.r_[False, truth[:-1]])
    episodes = []
    for start in starts:
        stop = start
        while stop < len(truth) and truth[stop]:
            stop += 1
        hits = np.flatnonzero(predicted[start:stop])
        episodes.append(float(times[start + hits[0]] - times[start]) if len(hits) else None)
    return dict(tp=tp, fp=fp, tn=tn, fn=fn,
                recall=tp/(tp+fn) if tp+fn else None,
                false_alarm_rate=fp/(fp+tn) if fp+tn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                episode_ttd_s=episodes, missed_episodes=sum(t is None for t in episodes))


def evaluate_synthetic(seed, scenario, steps, dt=.5):
    random.seed(seed)
    state = new_state()
    truth, times, latency, raw_errors, final_errors, fused_errors = [], [], [], [], [], []
    predictions = {name: [] for name in ("rule", "rf", "vae", "hybrid", "inertial")}
    phases = {"clean": [], "attack": [], "recovery": []}
    reasons = {}
    for index in range(steps):
        t = index * dt
        state.navigation_time = t
        state.sample_dt = dt
        state.attack_mode = label_at(scenario, t, steps*dt)
        observation = simulate_sensors(state, dt=dt)
        rule, reason, features = step_features(state, observation, dt)
        state.vae_buffer.append(features)
        state.vae_buffer = state.vae_buffer[-10:]
        started = time.perf_counter()
        final, _, rf, _ = get_hybrid_decision(rule, features, state, state.vae_buffer)
        latency.append((time.perf_counter()-started)*1000)
        lat, lon, speed, cn0 = observation
        nav = process_navigation(state, lat, lon, speed, cn0, True, .5, 40,
                                 dt=dt, decision=(final, reason))
        fused = (state.fused_lat, state.fused_lon)
        truth.append(state.attack_mode != "normal")
        times.append(t)
        predictions["rule"].append(rule != "NORMAL")
        predictions["rf"].append(rf not in ("NORMAL", "RF_HATASI", "?") and state.rf_attack_score >= .5)
        predictions["vae"].append(state.vae_detected)
        predictions["hybrid"].append(nav[3] != "NORMAL")
        predictions["inertial"].append(state.get("inertial_consistency", {}).get("detected", False))
        phase = ("clean" if scenario == "normal" or t < 60 else
                 "attack" if state.attack_mode != "normal" else "recovery")
        phases[phase].append(index)
        if state.attack_mode == "normal" and nav[3] != "NORMAL":
            source = ("navigation" if final == "NORMAL" else
                      "physical_or_inertial" if rule != "NORMAL" else "ml")
            reasons[source] = reasons.get(source, 0) + 1
        reference = (state.true_lat, state.true_lon)
        raw_errors.append(calculate_distance_km(*reference, lat, lon)*1000)
        final_errors.append(calculate_distance_km(*reference, *nav[:2])*1000)
        fused_errors.append(calculate_distance_km(*reference, *fused)*1000)
        finish_frame(state, observation)
    phase_metrics = {
        phase: {"samples": len(indices), "alarms": sum(predictions["hybrid"][i] for i in indices),
                "alarm_rate": (sum(predictions["hybrid"][i] for i in indices)/len(indices)
                               if indices else None)}
        for phase, indices in phases.items()}
    return dict(seed=seed, scenario=scenario, steps=steps, simulated_seconds=steps*dt,
                phase_metrics=phase_metrics, false_alarm_sources=reasons,
                layers={name: classification_summary(truth, values, times) for name, values in predictions.items()},
                inference_ms={"median": float(np.median(latency)), "p95": float(np.quantile(latency, .95)),
                              "max": float(max(latency))},
                raw_rmse_m=float(np.sqrt(np.mean(np.square(raw_errors)))),
                navigation_rmse_m=float(np.sqrt(np.mean(np.square(final_errors)))),
                ekf_rmse_m=float(np.sqrt(np.mean(np.square(fused_errors)))))


def evaluate_av(path):
    """External AV logs: evaluate each contiguous run without merging repeated runs."""
    data = pd.read_csv(path)
    from domain_model import load_av_model, av_features, av_probabilities, identity_hashes
    domain = load_av_model()
    domain_truth, domain_predictions, domain_times = [], [], []
    overlapping_training_rows = 0
    if domain is not None and av_features(data) is not None and Path(path).resolve() != Path(domain["training_path"]).resolve():
        overlap = np.isin(identity_hashes(data), domain["training_identity_hashes"])
        overlapping_training_rows = int(overlap.sum())
        probabilities = av_probabilities(av_features(data), domain)
        data["_domain_prediction"] = probabilities >= domain["threshold"]
        data["_domain_holdout"] = ~overlap
    data["_time"] = pd.to_timedelta(data["Run Time"], errors="coerce").dt.total_seconds()
    original = len(data)
    # Coalesce only adjacent equal times. Global deduplication would erase repeated
    # recordings (and attacks) that reuse the same run-time clock.
    groups = data["_time"].ne(data["_time"].shift()).cumsum()
    data = data.groupby(groups, sort=False).tail(1)
    state = new_state()
    segments = []
    truth, predicted, times = [], [], []
    previous_t = None
    for _, row in data.iterrows():
        t = float(row["_time"])
        lat, lon = float(row["GPS Latitude"]), float(row["GPS Longitude"])
        speed = float(row["Velocity (m/s)"]) * 3.6
        if not all(math.isfinite(v) for v in (t, lat, lon, speed)):
            continue
        if previous_t is None or t < previous_t:
            if truth:
                segments.append(classification_summary(truth, predicted, times))
            state = new_state()
            truth, predicted, times = [], [], []
            state.prev_lat = state.last_good_lat = lat
            state.prev_lon = state.last_good_lon = lon
            state.prev_speed = speed
            state.prev_heading = float(row["GPS Course"])
            previous_t = t
            continue
        dt = t - previous_t
        if dt <= 0:
            continue
        state.acceleration = 0.
        rule, _ = run_firewall_rules(state, lat, lon, float("nan"), speed, 45., .5, 40., 45., dt=dt)
        truth.append(int(row["Data Type"]) != 0)
        if bool(row.get("_domain_holdout", False)):
            domain_truth.append(int(row["Data Type"]) != 0)
            domain_predictions.append(bool(row["_domain_prediction"]))
            domain_times.append(float(len(domain_times)))
        predicted.append(rule != "NORMAL")
        times.append(t)
        if rule == "NORMAL":
            state.last_good_lat, state.last_good_lon = lat, lon
        finish_frame(state, (lat, lon, speed, float("nan")))
        previous_t = t
    if truth:
        segments.append(classification_summary(truth, predicted, times))
    tp, fp, tn, fn = [sum(segment[key] for segment in segments) for key in ("tp", "fp", "tn", "fn")]
    episodes = [event for segment in segments for event in segment["episode_ttd_s"]]
    domain_metrics = classification_summary(domain_truth, domain_predictions, domain_times) if domain_truth else None
    if domain_metrics is not None:
        domain_metrics.pop("episode_ttd_s", None)
        domain_metrics.pop("missed_episodes", None)
    return dict(file=str(path), sha256=sha256(path), source="external AV-GPS log, unchanged",
                input_rows=original, evaluated_rows=tp+fp+tn+fn, segments=len(segments),
                duplicate_timestamps_removed=original-len(data),
                evaluated_layer="kinematic rules only", cn0_available=False, independent_position_truth=False,
                hybrid_result=None, rmse_m=None,
                kinematic_rf=domain_metrics,
                training_overlap_rows_removed=overlapping_training_rows,
                tp=tp, fp=fp, tn=tn, fn=fn,
                recall=tp/(tp+fn) if tp+fn else None,
                false_alarm_rate=fp/(fp+tn) if fp+tn else None,
                episode_ttd_s=episodes, missed_episodes=sum(event is None for event in episodes))


def write_report(output, results):
    lines = ["# Güncel doğrulama raporu", "", f"Tarih: {results['created_at']}", "",
             "Bu rapor yazılım simülasyonu ve yerel AV-GPS kayıtlarının yeniden oynatılmasıdır. GPS/IMU saha testi değildir.", "",
             "Eğitim, normal eşik kalibrasyonu ve değerlendirme rastgele tohumları ayrıdır. Değerlendirme verisiyle yeniden ayarlama yapılmaz.", "",
             "Yavaş spoofing 0.5 m/s konum sürüklemesidir. `slow_spoofing` C/N0 değişimi içerir; eğitimde bulunmayan `stealth_spoofing` normal C/N0 dağılımını korur.", "",
             "`rule` katmanı fiziksel kuralları ve varsa bağımsız IMU/yönelim kontrolünü içerir; `inertial` yalnız tutarlılık kontrolüdür. "
             f"Değerlendirme tohumları: {results['protocol']['evaluation_seeds']}. Eğitim ve kalibrasyon geçmişi ham JSON'dadır.", "",
             "Her saldırı koşusunda 60 saniye normal başlangıç ve son çeyrekte normal toparlanma vardır. Yanlış alarmlar toparlanma dönemini de kapsar.", "",
             "| Senaryo | Katman | Tespit (%) | Yanlış alarm (%) | Kaçırılan / toplam olay | Ortalama TTD (s) |",
             "|---|---|---:|---:|---:|---:|"]
    for scenario in dict.fromkeys(r['scenario'] for r in results['synthetic']):
        runs = [r for r in results['synthetic'] if r['scenario'] == scenario]
        for layer in ("rule", "rf", "vae", "hybrid", "inertial"):
            stats = [r['layers'][layer] for r in runs]
            tp, fn, fp, tn = [sum(s[k] for s in stats) for k in ("tp", "fn", "fp", "tn")]
            episodes = [e for s in stats for e in s['episode_ttd_s']]
            hits = [e for e in episodes if e is not None]
            recall = f"{100*tp/(tp+fn):.2f}" if tp+fn else "—"
            fpr = f"{100*fp/(fp+tn):.2f}" if fp+tn else "—"
            ttd = f"{np.mean(hits):.2f}" if hits else "—"
            lines.append(f"| {scenario} | {layer} | {recall} | {fpr} | {sum(e is None for e in episodes)}/{len(episodes)} | {ttd} |")
    lines.extend(["", "### Temiz başlangıç ve toparlanma", "",
                  "Toparlanma alarmları saldırı dışı yanlış alarm hesabına dahildir; temiz başlangıçla ayrı gösterilir. Saldırı etiketi yalnız değerlendirmede kullanılır.", "",
                  "| Senaryo | Temiz örnek / alarm | Toparlanma örnek / alarm |",
                  "|---|---:|---:|"])
    for scenario in dict.fromkeys(r['scenario'] for r in results['synthetic']):
        runs = [r for r in results['synthetic'] if r['scenario'] == scenario]
        values = [sum(r['phase_metrics'][phase][key] for r in runs)
                  for phase in ('clean', 'recovery') for key in ('samples', 'alarms')]
        lines.append(f"| {scenario} | {values[0]} / {values[1]} | {values[2]} / {values[3]} |")
    lines.extend(["", "TTD, saldırının başlangıcından ilk alarma kadar geçen simülasyon süresidir. Kaçırılan olaylar sıfır saniye sayılmaz.", "",
                  "| Senaryo | Ham GPS RMSE (m) | Navigasyon RMSE (m) | EKF RMSE (m) | Çıkarım p95 (ms), koşular ortalaması |",
                  "|---|---:|---:|---:|---:|"])
    for scenario in dict.fromkeys(r['scenario'] for r in results['synthetic']):
        runs = [r for r in results['synthetic'] if r['scenario'] == scenario]
        a,b,c = [np.sqrt(np.mean([r[key]**2 for r in runs])) for key in ('raw_rmse_m','navigation_rmse_m','ekf_rmse_m')]
        lines.append(f"| {scenario} | {a:.2f} | {b:.2f} | {c:.2f} | {np.mean([r['inference_ms']['p95'] for r in runs]):.2f} |")
    lines.extend(["", "## Harici veri", "",
                  "C/N0 tabanlı RF/VAE modeli AV-GPS dosyalarında eğitilmemiştir. Ayrı C/N0 gerektirmeyen AV modeli yalnız dosya 1'de eğitilir; dosya 2 ve 3 ayrılmış değerlendirmedir. Dosya 1 için AV model test skoru verilmez. Eğitimdeki konum/zaman/hız kimliğiyle çakışan test satırları çıkarılır. Dosya 2 ve 3 birbirleriyle kısmen örtüşür; bağımsız tekrarlar gibi birleştirilmez. Bağımsız doğru konum bulunmadığından konum RMSE'si çıkarılamaz. İlk tablo yalnız fiziksel kuralları ölçer.", "",
                  "| Dosya | Örnek | Tespit (%) | Yanlış alarm (%) |", "|---|---:|---:|---:|"])
    for r in results['external']:
        rec = f"{100*r['recall']:.2f}" if r['recall'] is not None else "—"
        fpr = f"{100*r['false_alarm_rate']:.2f}" if r['false_alarm_rate'] is not None else "—"
        lines.append(f"| {Path(r['file']).name} | {r['evaluated_rows']} | {rec} | {fpr} |")
    lines.extend(["", "### Ayrı kinematik RF: eğitim dışı kayıtlar", "",
                  "| Dosya | Tespit (%) | Yanlış alarm (%) | Eğitimle çakışan çıkarılan satır |",
                  "|---|---:|---:|---:|"])
    for r in results["external"]:
        metrics = r.get("kinematic_rf")
        if metrics is not None:
            recall = "—" if metrics["recall"] is None else f"{100*metrics['recall']:.2f}"
            fpr = "—" if metrics["false_alarm_rate"] is None else f"{100*metrics['false_alarm_rate']:.2f}"
            lines.append(f"| {Path(r['file']).name} | {recall} | {fpr} | {r['training_overlap_rows_removed']} |")
    lines.extend(["", "## Sınırlar ve saha doğrulaması", "",
                  "- Simülatörün konumu yalnız hata ölçümüne verilir; tespit özelliklerine ve GPS güven kararına verilmez.",
                  "- Yavaş ve fiziksel olarak tutarlı spoofing, bağımsız konum/hız/yön referansı olmadan güvenilir biçimde ayrılamayabilir. Kaçırılan olaylar raporda saklanmaz.",
                  "- Düşük C/N0 koordinat manipülasyonu kanıtı değildir. Jamming'de fiziksel yenilik kapısını geçen ölçümler düşük ağırlıkla birleştirilir; spoofing/tutarsız ölçümde ataletsel tahmin kullanılır. Konum belirsizliği izlenir; gerçek araç kontrol komutu yoktur.",
                  "- Jamming simülasyonunda ham GPS hatası ataletsel tahminden düşük olabilir; müdahale her koşulda konum iyileşmesi sağlamaz.",
                  "- Bağımsız yönelim ve navigasyon eksenindeki IMU mevcutsa yeni zaman penceresi kontrolü kullanılır. Simülatör bu bağımsız yönelimi 0.2° standart sapmalı varsayar; çıplak MPU6050 mutlak yönelim sağlamaz. Bu girdiler yoksa kontrol devre dışıdır.",
                  "- Alt metre RMSE, sıfırıncı gün koruması veya saha güvenliği garantisi verilmez.",
                  "- Gerçek GPS/IMU saha doğrulaması: tamamlanmadı. Bağımsız referans konum, zaman eşlemeli IMU ve etiketli pasif kayıt gerekir.",
                  "- Sentetik eğitimden saha verisine genelleme bu raporla doğrulanmış sayılmaz.", "",
                  f"Ayrıntılı sayımlar, her olayın TTD'si, model ve veri SHA-256 değerleri: `validation_results.json`.", ""])
    (output / "VALIDATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--report-date", type=date.fromisoformat)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--seed-start", type=int, default=30001,
                        help="First evaluation seed; choose fresh seeds after development")
    parser.add_argument("--output", type=Path, default=Path("validation_results"))
    args = parser.parse_args()
    if args.runs < 1 or args.steps < 240:
        parser.error("runs >= 1 and steps >= 240 required")
    args.output.mkdir(exist_ok=True, parents=True)
    torch.set_num_threads(1)
    manifest = args.output / "training_manifest.json"
    if args.train:
        provenance = train_synthetic(args.output)
        manifest.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    else:
        provenance = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
    if load_rf_bundle()[0] is None or load_vae_model() is None:
        raise RuntimeError("Compatible trained models required. Run with --train.")
    from domain_model import load_av_model, train_av_model
    if args.train or load_av_model() is None:
        train_av_model()
    domain_bundle = load_av_model()
    evaluation_seeds = set(range(args.seed_start, args.seed_start+args.runs))
    if provenance and evaluation_seeds.intersection(
            provenance.get("training_seeds", [])+provenance.get("calibration_seeds", [])):
        raise ValueError("Evaluation seeds must be disjoint from training and calibration")
    results = dict(av_training={key: domain_bundle[key] for key in ("schema", "training_path", "training_sha256", "training_rows", "threshold")}, created_at=(str(args.report_date) if args.report_date is not None else datetime.now(ZoneInfo("Europe/Istanbul")).isoformat()),
                   python=platform.python_version(), feature_schema=FEATURE_SCHEMA,
                   training=provenance, model_sha256={str(p):sha256(p) for p in
                       map(Path, ("gnss_rf_model.pkl", "gnss_scaler.pkl", "gnss_lstm_vae.pth", "vae_threshold.npy", "gnss_kinematic_model.pkl"))},
                   protocol={"dt_s": .5, "steps_per_run": args.steps, "runs_per_scenario": args.runs,
                             "evaluation_seeds": [args.seed_start+i for i in range(args.runs)],
                             "cn0_fraction": .5, "acceleration_slider": 40, "heading_threshold_deg": 45},
                   source_sha256={name: sha256(name) for name in ("validation.py", "features.py", "detection.py", "navigation.py", "sensors.py", "fusion.py", "ml_detection.py", "config.py", "models/lstm_vae.py", "inertial_monitor.py", "domain_model.py", "imu_processing.py", "artifact_io.py", "nmea_stream.py", "forensic_ledger.py", "train_model.py", "vae_calibration.py")},
                   synthetic=[], external=[], field_validation="not performed")
    for scenario in ("normal", "jamming", "spoofing", "slow_spoofing", "stealth_spoofing"):
        for run in range(args.runs):
            print(f"Evaluating {scenario}, run {run+1}/{args.runs}", flush=True)
            results['synthetic'].append(evaluate_synthetic(args.seed_start+run, scenario, args.steps))
    for index in (1, 2, 3):
        path = Path(f"dataset_gercek/AV-GPS-Dataset-{index}.csv")
        if path.exists():
            results['external'].append(evaluate_av(path))
    (args.output / "validation_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_report(args.output, results)
    print(f"Report: {args.output / 'VALIDATION_REPORT.md'}", flush=True)


if __name__ == "__main__":
    main()
