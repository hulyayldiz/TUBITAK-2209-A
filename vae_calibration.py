"""Normal-only VAE calibration; evaluation and attack labels are never inputs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
import torch

from artifact_io import save_numpy, save_torch

CALIBRATION_SEEDS = tuple(range(2001, 2021))
CALIBRATION_STEPS = 1200
FEATURE_COLUMNS = ("cn0", "accel", "heading_drift", "residual")


def longest_streak(values):
    longest = current = 0
    for value in values:
        current = current+1 if value else 0
        longest = max(longest, current)
    return longest


def calibration_policy(error_runs, quantile=.9999, sample_dt=.5, max_confirmation_s=5.):
    """Set a normal-tail threshold and exceed the longest normal anomaly streak."""
    if (not .5 < quantile < 1 or not math.isfinite(sample_dt) or sample_dt <= 0
            or not math.isfinite(max_confirmation_s) or max_confirmation_s <= 0):
        raise ValueError("Invalid calibration policy")
    runs = [np.asarray(values, dtype=float) for values in error_runs]
    if not runs or any(v.ndim != 1 or not len(v) or not np.isfinite(v).all() or (v < 0).any() for v in runs):
        raise ValueError("Finite nonnegative errors in separate nonempty runs required")
    values = np.concatenate(runs)
    if len(values) < round(1/(1-quantile)):
        raise ValueError("Insufficient normal samples for requested tail quantile")
    threshold = max(float(np.quantile(values, quantile)), float(np.finfo(np.float32).eps))
    longest = max(longest_streak(run > threshold) for run in runs)
    persistence = max(3, longest+1)
    if persistence*sample_dt > max_confirmation_s:
        raise ValueError("Normal calibration requires excessive VAE delay; model revision needed")
    return dict(threshold=threshold, persistence_samples=persistence,
                persistence_seconds=persistence*sample_dt, normal_quantile=quantile,
                normal_windows=len(values), longest_normal_streak=longest,
                sample_dt_s=sample_dt, max_confirmation_s=max_confirmation_s)


def normal_error_runs(model, seeds=CALIBRATION_SEEDS, steps=CALIBRATION_STEPS):
    from validation import synthetic_features
    error_runs, provenance = [], []
    for seed in seeds:
        rows = synthetic_features(seed, "normal", steps=steps)
        values = np.asarray([[row[key] for key in FEATURE_COLUMNS] for row in rows], dtype=np.float32)
        digest = hashlib.sha256(values.tobytes()).hexdigest()
        values = (values-model.feature_mean)/model.feature_std
        windows = np.asarray([values[i:i+10] for i in range(len(values)-9)])
        errors = []
        with torch.no_grad():
            for start in range(0, len(windows), 128):
                batch = torch.tensor(windows[start:start+128])
                reconstruction, _, _ = model(batch)
                errors.extend(torch.mean(torch.abs(reconstruction-batch), dim=(1, 2)).tolist())
        error_runs.append(errors)
        provenance.append(dict(seed=seed, steps=steps, features_sha256=digest))
    return error_runs, provenance


def calibrate_model(model):
    errors, provenance = normal_error_runs(model)
    policy = calibration_policy(errors)
    return dict(policy, source="synthetic normal only", runs=provenance,
                calibration_seeds=list(CALIBRATION_SEEDS),
                previous_threshold=float(getattr(model, "anomaly_threshold", float("nan"))),
                previous_persistence_samples=int(getattr(model, "persistence_samples", 3)))


def persist_calibration(model_path, threshold_path, calibration):
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    checkpoint.update(threshold=calibration["threshold"],
                      persistence_samples=calibration["persistence_samples"],
                      persistence_seconds=calibration["persistence_seconds"],
                      normal_calibration=calibration)
    # Runtime uses the embedded threshold; publish the complete bundle last.
    save_numpy(calibration["threshold"], threshold_path)
    save_torch(checkpoint, model_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("validation_results/low_false_alarm_20261023"))
    args = parser.parse_args()
    from ml_detection import load_vae_model, VAE_PATH, THRESHOLD_PATH
    torch.set_num_threads(1)
    model = load_vae_model()
    if model is None:
        raise RuntimeError("Compatible trained VAE required")
    calibration = calibrate_model(model)
    args.output.mkdir(parents=True, exist_ok=True)
    calibration["model_before_sha256"] = hashlib.sha256(Path(VAE_PATH).read_bytes()).hexdigest()
    if args.apply:
        for name in (VAE_PATH, THRESHOLD_PATH):
            source = Path(name)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
            backup = args.output / f"previous_{digest}_{source.name}"
            if not backup.exists():
                shutil.copy2(source, backup)
        persist_calibration(VAE_PATH, THRESHOLD_PATH, calibration)
        load_vae_model.clear()
    calibration["applied"] = args.apply
    calibration["model_after_sha256"] = hashlib.sha256(Path(VAE_PATH).read_bytes()).hexdigest()
    (args.output/"normal_calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    print(json.dumps({key: calibration[key] for key in
          ("threshold", "persistence_samples", "persistence_seconds", "normal_windows", "applied")}))


if __name__ == "__main__":
    main()
