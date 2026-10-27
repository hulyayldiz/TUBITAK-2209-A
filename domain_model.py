"""Separate C/N0-free AV model. Trained only on file 1; evaluated on other files."""
from pathlib import Path
import hashlib
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from artifact_io import artifact_cache, dump_joblib
import logging

PATH = Path("gnss_kinematic_model.pkl")
SCHEMA = "av-kinematics-v1"
REQUIRED = ["Run Time", "GPS Latitude", "GPS Longitude", "Velocity (m/s)",
            "Heading (deg)", "GPS Course", "GPS HDOP", "GPS VDOP", "Satellite Locks", "Satellite Count", "Yaw Rate (deg/s)"]
FEATURES = ["speed", "speed_change", "coordinate_speed", "speed_mismatch", "course_difference", "hdop", "vdop", "locks", "satellites", "yaw_rate"]


def av_features(data):
    if not set(REQUIRED).issubset(data.columns):
        return None
    values = data[REQUIRED].copy()
    for column in REQUIRED[1:]:
        values[column] = pd.to_numeric(values[column], errors="coerce")
    times = pd.to_timedelta(values["Run Time"], errors="coerce").dt.total_seconds()
    dt = times.diff().where(lambda value: value > 0)
    latitude, longitude = np.radians(values["GPS Latitude"]), np.radians(values["GPS Longitude"])
    haversine = np.sin(latitude.diff()/2)**2 + np.cos(latitude)*np.cos(latitude.shift())*np.sin(longitude.diff()/2)**2
    distance = 6371000*2*np.arcsin(np.sqrt(haversine.clip(0,1)))
    speed = values["Velocity (m/s)"]
    coordinate_speed = distance/dt
    frame = pd.DataFrame(dict(speed=speed, speed_change=speed.diff()/dt,
        coordinate_speed=coordinate_speed, speed_mismatch=(coordinate_speed-speed).abs(),
        course_difference=((values["GPS Course"]-values["Heading (deg)"]+180)%360-180).abs(),
        hdop=values["GPS HDOP"], vdop=values["GPS VDOP"], locks=values["Satellite Locks"],
        satellites=values["Satellite Count"], yaw_rate=values["Yaw Rate (deg/s)"]))
    return frame[FEATURES].replace([np.inf, -np.inf], np.nan)


def identity_hashes(data):
    columns = ["Run Time", "GPS Latitude", "GPS Longitude", "Velocity (m/s)"]
    return pd.util.hash_pandas_object(data[columns].astype(str), index=False).to_numpy(dtype="uint64")


def train_av_model(path=Path("dataset_gercek/AV-GPS-Dataset-1.csv")):
    data = pd.read_csv(path)
    frame = av_features(data)
    if frame is None:
        raise ValueError("AV sensor columns missing")
    target = pd.to_numeric(data["Data Type"], errors="raise").to_numpy(dtype=int)
    if set(target) != {0,1}:
        raise ValueError("Expected binary attack labels")
    model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
        RandomForestClassifier(n_estimators=150, max_depth=16, min_samples_leaf=3,
                               class_weight="balanced", random_state=731, n_jobs=2))
    model.fit(frame.to_numpy(dtype=float), target)
    bundle = dict(schema=SCHEMA, model=model, features=FEATURES,
                  training_path=str(path), training_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                  training_rows=len(data), training_identity_hashes=np.unique(identity_hashes(data)), threshold=.8)
    dump_joblib(bundle, PATH)
    load_av_model.clear()
    return {key: bundle[key] for key in ("schema", "training_path", "training_sha256", "training_rows", "threshold")}


@artifact_cache(PATH)
def load_av_model():
    if not PATH.exists():
        return None
    try:
        bundle = joblib.load(PATH)
    except Exception as error:
        logging.error("AV model load failed: %s", error)
        return None
    if bundle.get("schema") != SCHEMA or bundle.get("features") != FEATURES:
        return None
    bundle["model"].named_steps["randomforestclassifier"].n_jobs = 1
    return bundle


def av_probabilities(frame, bundle=None):
    bundle = load_av_model() if bundle is None else bundle
    if bundle is None or frame is None:
        return None
    classes = bundle["model"].classes_
    index = list(classes).index(1)
    return bundle["model"].predict_proba(np.asarray(frame, dtype=float))[:, index]
