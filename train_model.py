"""Train prototype models with run-level partitions and explicit limitations."""

import os
import random
import shutil
import tempfile
import hashlib
from features import FEATURE_SCHEMA
from artifact_io import dump_joblib, save_torch, save_numpy
import numpy as np
import pandas as pd
import torch
from datetime import datetime
from pathlib import Path

# Sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sklearn.metrics import classification_report, confusion_matrix

# Yerel modül
try:
    from lstm_vae import LSTMVAE, vae_loss
except ImportError:
    from models.lstm_vae import LSTMVAE, vae_loss

# --- Sabitler ---
CSV_PATH       = "gnss_training_motion_v2.csv"
RF_PATH        = "gnss_rf_model.pkl"
VAE_PATH       = "gnss_lstm_vae.pth"
THRESHOLD_PATH = "vae_threshold.npy"
SCALER_PATH    = "gnss_scaler.pkl"

FEATURES    = ["cn0", "accel", "heading_drift", "residual"]
TARGET      = "target_label"
SEQ_LEN     = 10
VAE_INPUT   = 4
VAE_HIDDEN  = 32
VAE_LATENT  = 8
VAE_EPOCHS  = 40
VAE_LR      = 1e-3
BATCH_SIZE  = 16


# ──────────────────────────────────────────────────────────────
# 1. VERİ YÜKLEME VE DOĞRULAMA
# ──────────────────────────────────────────────────────────────
def load_and_validate(csv_path=CSV_PATH):
    """
    CSV'yi yükler, eksik sütunları kontrol eder ve oturum kimliği ister.
    """
    if not os.path.exists(csv_path):
        return None, "❌ Eğitim verisi bulunamadı. Önce simülasyonu 'Veri Toplama' moduyla çalıştırın."

    df = pd.read_csv(csv_path)

    # Sütun kontrolü
    missing = [c for c in FEATURES + [TARGET, "run_id"] if c not in df.columns]
    if missing:
        return None, f"❌ CSV'de eksik sütun: {missing}"

    df = df.dropna(subset=FEATURES + [TARGET])

    # Signal loss and large jumps are valid attack observations.
    df = df[np.isfinite(df[FEATURES].to_numpy(dtype=float)).all(axis=1)]
    df = df[df["cn0"].between(0.0, 65.0) & (df["residual"] >= 0)]

    # Sınıf standartlaştırma (JAMMING_WARNING vs JAMMING uyumsuzluğunu çözer)
    df[TARGET] = df[TARGET].apply(lambda x: "JAMMING" if "JAMMING" in str(x).upper() else str(x).upper())

    df["run_id"] = df["run_id"].astype(str).str.strip()
    if df["run_id"].eq("").any() or df["run_id"].nunique() < 3:
        return None, "En az üç ayrı, dolu run_id oturumu gerekir; satır bazlı rastgele bölme yapılmaz."

    # Minimum class/session support for grouped holdout and grouped CV.
    counts = df[TARGET].value_counts()
    if len(df) < 50 or any(counts.get(cls, 0) < 5 for cls in ["NORMAL", "SPOOFING", "JAMMING"]):
        return None, "Her sınıf için en az 5 geçerli örnek ve toplam en az 50 satır gerekli."
    group_support = df.groupby(TARGET)["run_id"].nunique()
    if any(group_support.get(cls, 0) < 3 for cls in ["NORMAL", "SPOOFING", "JAMMING"]):
        return None, "Her sınıf en az üç toplama oturumunda bulunmalı; grup holdout kurulamıyor."

    return df, None



# ──────────────────────────────────────────────────────────────
# 2. RANDOM FOREST EĞİTİMİ
# ──────────────────────────────────────────────────────────────
def train_random_forest(df):
    """
    Session-level holdout and grouped CV; refuses row-only partitions.
    Döndürür: (model, scaler, report_str, cv_scores)
    """
    le = LabelEncoder()
    X = df[FEATURES].to_numpy(dtype=float)
    y = df[TARGET].to_numpy(dtype=str) # LabelEncoder öncesi sınıf isimlerini sakla

    groups = df["run_id"].astype(str).to_numpy()
    classes = set(y)
    partition = None
    for random_state in range(42, 142):
        train_indices, test_indices = next(GroupShuffleSplit(
            n_splits=1, test_size=.2, random_state=random_state).split(X, y, groups))
        if set(y[train_indices]) == classes and set(y[test_indices]) == classes:
            partition = train_indices, test_indices
            break
    if partition is None:
        raise ValueError("Oturum bazlı holdout her sınıfı iki bölüme ayıramadı; daha çeşitli oturum toplayın")
    train_indices, test_indices = partition
    X_train_raw, X_test_raw = X[train_indices], X[test_indices]
    y_train_raw, y_test_raw = y[train_indices], y[test_indices]
    train_groups = groups[train_indices]
    folds = min(5, int(df.iloc[train_indices].groupby(TARGET)["run_id"].nunique().min()))
    if folds < 2:
        raise ValueError("Grouped CV için her sınıfta en az iki eğitim oturumu gerekir")
    cv_splits = None
    for random_state in range(42, 142):
        candidate = list(StratifiedGroupKFold(n_splits=folds, shuffle=True,
                                              random_state=random_state).split(
                                                  X_train_raw, y_train_raw, train_groups))
        if all(set(y_train_raw[train]) == classes and set(y_train_raw[test]) == classes
               for train, test in candidate):
            cv_splits = candidate
            break
    if cv_splits is None:
        raise ValueError("Grouped CV her fold'da tüm sınıfları tutamıyor; daha çeşitli oturum toplayın")
    split_method = f"run-group holdout (20%); {folds}-fold grouped CV"
    le.fit(y_train_raw)
    y_train, y_test = le.transform(y_train_raw), le.transform(y_test_raw)
    if len(np.unique(y_train)) != len(le.classes_):
        raise ValueError("Run split omitted a training class; collect additional sessions")
    param_grid = {"model__n_estimators": [100,200], "model__max_depth": [None,10,20],
                  "model__min_samples_split": [2,5]}
    pipeline = Pipeline([("scaler", StandardScaler()), ("model", RandomForestClassifier(
        class_weight="balanced", random_state=42, n_jobs=1))])
    grid_search = GridSearchCV(pipeline, param_grid, cv=cv_splits,
                              scoring="f1_weighted", n_jobs=2, verbose=0)
    grid_search.fit(X_train_raw, y_train)
    best_pipeline = grid_search.best_estimator_
    scaler, best_rf = best_pipeline.named_steps["scaler"], best_pipeline.named_steps["model"]
    X_test = scaler.transform(X_test_raw)
    # Internal model-selection CV, never includes the reserved holdout rows/runs.
    cv_scores = cross_val_score(best_pipeline, X_train_raw, y_train, cv=cv_splits,
                               scoring="f1_weighted", n_jobs=2)

    # Test seti değerlendirmesi
    y_pred = best_rf.predict(X_test)
    target_names = le.classes_

    report = classification_report(y_test, y_pred, labels=np.arange(len(target_names)), target_names=target_names, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=np.arange(len(target_names)))

    # --- Grafik Oluşturma (Confusion Matrix & ROC) ---
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        from sklearn.metrics import roc_curve, auc
        from sklearn.preprocessing import label_binarize

        # 1. Confusion Matrix
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=target_names, yticklabels=target_names)
        plt.title('Karmaşıklık Matrisi (Ayrılmış Holdout)')
        plt.ylabel('Gerçek Sınıf')
        plt.xlabel('Tahmin Edilen Sınıf')
        plt.tight_layout()
        plt.savefig('confusion_matrix.png')
        plt.close()

        # 2. ROC Curve
        n_classes = len(target_names)
        y_test_bin = label_binarize(y_test, classes=range(n_classes))
        y_score = best_rf.predict_proba(X_test)

        plt.figure(figsize=(8, 6))
        for i in range(n_classes):
            if np.sum(y_test_bin[:, i]) > 0: # Sınıfın test setinde var olduğundan emin ol
                fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_score[:, i])
                roc_auc = auc(fpr, tpr)
                plt.plot(fpr, tpr, lw=2, label=f'{target_names[i]} (AUC = {roc_auc:.2f})')

        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('Yanlış Pozitif Oranı (FPR)')
        plt.ylabel('Doğru Pozitif Oranı (TPR)')
        plt.title('ROC Eğrisi (Receiver Operating Characteristic)')
        plt.legend(loc="lower right")
        plt.tight_layout()
        plt.savefig('roc_curve.png')
        plt.close()
    except Exception as e:
        print(f"Grafik oluşturulurken hata (Matplotlib/Seaborn eksik olabilir): {e}")
    # ---------------------------------------------------

    # Model ve encoder'ı birlikte sakla
    model_bundle = {
        "feature_schema": FEATURE_SCHEMA,
        "model": best_rf,
        "scaler": scaler,
        "validation_split": split_method,
        "training_run_count": int(len(np.unique(groups[train_indices]))),
        "holdout_run_count": int(len(np.unique(groups[test_indices]))),
        "label_encoder": le,
        "best_params": grid_search.best_params_,
        "cv_mean_f1": cv_scores.mean(),
        "cv_std_f1": cv_scores.std(),
        "confusion_matrix": cm.tolist(),
        "trained_at": datetime.now().isoformat()
    }

    dump_joblib(model_bundle, RF_PATH)
    dump_joblib(scaler, SCALER_PATH)

    summary = (
        f"📊 RF Eğitim Tamamlandı\n"
        f"En İyi Parametreler: {grid_search.best_params_}\n"
        f"Grouped CV F1 (model selection): {len(cv_splits)} folds, "
        f"{cv_scores.mean():.4f} ± {cv_scores.std():.4f}; bağımsız performans tahmini değildir.\n\n"
        f"Split yöntemi: {split_method}\nHoldout Raporu:\n{report}\n"
        f"Confusion Matrix:\n{cm}\n\n"
        f"Görseller (ROC ve CM) dizine .png olarak kaydedildi."
    )

    return model_bundle, scaler, summary, cv_scores


# ──────────────────────────────────────────────────────────────
# 3. LSTM-VAE EĞİTİMİ
# ──────────────────────────────────────────────────────────────
def train_vae(df):
    """
    Oturum bazlı normal eğitim ve ayrı sentetik-normal eşik kalibrasyonu yapar.
    Bu kalibrasyon saha yanlış-alarm olasılığı tahmini değildir.
    Döndürür: (model, threshold, summary_str)
    """
    # Split complete recording sessions before building the overlapping windows.
    normal_segments_by_run, current, current_run, previous_run = {}, [], None, None
    def save_segment():
        if current_run is not None and len(current) >= SEQ_LEN:
            normal_segments_by_run.setdefault(current_run, []).append(
                np.asarray(current, dtype=np.float32))

    for _, row in df.iterrows():
        run = str(row.get("run_id", "")).strip()
        normal = str(row[TARGET]).upper() == "NORMAL"
        if not normal or (previous_run is not None and run != previous_run):
            save_segment()
            current = []
            current_run = run if normal else None
        if normal:
            if current_run is None:
                current_run = run
            current.append(row[FEATURES].to_numpy(dtype=np.float32))
        previous_run = run
    save_segment()
    run_ids = sorted(normal_segments_by_run)
    if len(run_ids) < 2:
        return None, None, "LSTM-VAE için en az iki ayrı normal oturum gerekir; aynı oturum içi pencere bölmesi bağımsız doğrulama sayılmaz"
    rng = np.random.RandomState(42)
    shuffled_runs = list(np.asarray(run_ids)[rng.permutation(len(run_ids))])
    validation_count = max(1, int(np.ceil(.2*len(shuffled_runs))))
    validation_runs = set(shuffled_runs[:validation_count])
    training_runs = set(shuffled_runs[validation_count:])
    training_segments = [segment for run in sorted(training_runs)
                         for segment in normal_segments_by_run[run]]
    validation_segments = [segment for run in sorted(validation_runs)
                           for segment in normal_segments_by_run[run]]
    if not training_segments or not validation_segments:
        return None, None, "Eğitim/doğrulama için ayrı oturumlarda yeterli kesintisiz NORMAL sekansı yok"
    training_values = np.concatenate(training_segments)
    X_mean = training_values.mean(axis=0)
    X_std = np.maximum(training_values.std(axis=0), 1e-3)
    def windows(parts):
        sequences = []
        for values in parts:
            normalized = (values-X_mean)/X_std
            sequences.extend(normalized[index:index+SEQ_LEN]
                             for index in range(len(normalized)-SEQ_LEN+1))
        return torch.tensor(np.asarray(sequences), dtype=torch.float32)
    X_seq_train, X_seq_val = windows(training_segments), windows(validation_segments)
    if len(X_seq_train) == 0 or len(X_seq_val) == 0:
        return None, None, "Eğitim ve bağımsız doğrulama için yeterli NORMAL sekansı yok"
    overlap_note = " [örtüşmeli pencereler; eğitim/doğrulama bölümleri ayrık]"

    # Model
    model = LSTMVAE(
        input_size=VAE_INPUT,
        hidden_size=VAE_HIDDEN,
        latent_size=VAE_LATENT,
        seq_len=SEQ_LEN
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=VAE_LR)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=15, gamma=0.5)

    model.train()
    losses = []
    for epoch in range(VAE_EPOCHS):
        epoch_loss = 0.0
        # Mini-batch
        indices = torch.randperm(len(X_seq_train))
        for start in range(0, len(X_seq_train), BATCH_SIZE):
            batch = X_seq_train[indices[start:start + BATCH_SIZE]]
            optimizer.zero_grad()
            recon, mu, logvar = model(batch)
            loss = vae_loss(recon, batch, mu, logvar)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_loss += loss.item()
        scheduler.step()
        losses.append(epoch_loss / max(len(X_seq_train) // BATCH_SIZE, 1))

    model.eval()

    model.feature_mean = X_mean
    model.feature_std = X_std
    from vae_calibration import calibrate_model
    calibration = calibrate_model(model)
    threshold = float(calibration["threshold"])
    model.anomaly_threshold = threshold
    model.persistence_samples = int(calibration["persistence_samples"])
    model.persistence_seconds = float(calibration["persistence_seconds"])

    # Store one complete model+calibration bundle after the normal-only
    # calibration procedure succeeds. No provisional threshold is installed.
    save_torch({"state_dict": model.state_dict(), "mean": X_mean.tolist(), "std": X_std.tolist(),
                "feature_schema": FEATURE_SCHEMA, "threshold": threshold,
                "persistence_samples": model.persistence_samples,
                "persistence_seconds": model.persistence_seconds,
                "normal_calibration": calibration}, VAE_PATH)
    save_numpy(threshold, THRESHOLD_PATH)
    model.normal_calibration = calibration

    final_loss = losses[-1] if losses else 0
    summary = (
        f"🧠 LSTM-VAE Eğitim Tamamlandı{overlap_note}\n"
        f"Eğitim Sekans Sayısı: {len(X_seq_train)} | Val: {len(X_seq_val)}\n"
        f"Son Epoch Kaybı: {final_loss:.4f}\n"
        f"Eşik: ayrı sentetik normal oturumlarda q={calibration['normal_quantile']:.4f}; "
        f"{calibration['normal_windows']} örtüşmeli pencere, {len(calibration['runs'])} kalibrasyon koşusu. "
        "Bu ampirik simülasyon kalibrasyonudur; saha FAR garantisi değildir.\n"
        f"Eğitim oturumu: {len(training_runs)} | İç doğrulama oturumu: {len(validation_runs)}\n"
        f"Eğitim Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    return model, threshold, summary


# ──────────────────────────────────────────────────────────────
# 4. ANA EĞİTİM FONKSİYONU (UI'dan çağrılır)
# ──────────────────────────────────────────────────────────────
def run_model_training(csv_path=CSV_PATH):
    """
    Tüm eğitim pipeline'ını çalıştırır.
    Döndürür: (success: bool, message: str, full_report: str | None)
    """
    # 1. Veri yükleme
    df, err = load_and_validate(csv_path)
    if err:
        return False, err, None

    full_report_parts = [
        f"{'='*60}",
        f"GNSS HİBRİT MODEL EĞİTİM RAPORU",
        f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Toplam Veri: {len(df)} satır",
        f"Toplama oturumu: {df['run_id'].nunique()} | Girdi SHA-256: {hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()}",
        f"Sınıf Dağılımı:\n{df[TARGET].value_counts().to_string()}",
        f"{'='*60}",
    ]

    artifact_keys = ("RF_PATH", "SCALER_PATH", "VAE_PATH", "THRESHOLD_PATH")
    targets = {key: Path(globals()[key]).resolve() for key in artifact_keys}
    original_paths = {key: globals()[key] for key in artifact_keys}
    target_parent = targets["RF_PATH"].parent
    try:
        random.seed(42)
        np.random.seed(42)
        torch.manual_seed(42)
        with tempfile.TemporaryDirectory(prefix=".gnss-model-stage-", dir=target_parent) as stage_name:
            stage = Path(stage_name)
            for key in artifact_keys:
                globals()[key] = str(stage / targets[key].name)
            try:
                _, _, rf_summary, cv_scores = train_random_forest(df)
                vae_model, threshold, vae_summary = train_vae(df)
                if vae_model is None or threshold is None:
                    raise RuntimeError(vae_summary or "VAE eğitim/kalibrasyon başarısız")
            finally:
                globals().update(original_paths)

            staged = {key: stage / targets[key].name for key in artifact_keys}
            missing_artifacts = [path.name for path in staged.values() if not path.is_file()]
            if missing_artifacts:
                raise RuntimeError(f"Eksik model artefaktı: {missing_artifacts}")
            backups = {key: stage / f"backup-{targets[key].name}" for key in artifact_keys
                       if targets[key].exists()}
            for key, backup in backups.items():
                shutil.copy2(targets[key], backup)
            installed = []
            try:
                for key in artifact_keys:
                    targets[key].parent.mkdir(parents=True, exist_ok=True)
                    os.replace(staged[key], targets[key])
                    installed.append(key)
            except Exception:
                for key in reversed(installed):
                    if key in backups:
                        os.replace(backups[key], targets[key])
                    else:
                        targets[key].unlink(missing_ok=True)
                raise
        full_report_parts.extend((rf_summary, vae_summary))
    except Exception as e:
        globals().update(original_paths)
        return False, f"Model eğitimi/kalibrasyonu başarısız; önceki model dosyaları korundu: {e}", None

    full_report = "\n\n".join(full_report_parts)

    # Raporu diske yaz
    report_path = f"training_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    cv_f1 = cv_scores.mean() if cv_scores is not None else 0.0
    msg = (f"Model eğitildi. Oturum bazlı grouped-CV F1={cv_f1:.3f} ± {cv_scores.std():.3f}; "
           "bu geliştirme metriği bağımsız saha performansı değildir.")

    return True, msg, full_report


# ──────────────────────────────────────────────────────────────
# 5. KOMUT SATIRINDAN ÇALIŞTIRMA
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Model eğitimi başlatılıyor...")
    success, msg, report = run_model_training()
    print(f"\n{'✅' if success else '❌'} {msg}")
    if report:
        print("\n" + report)
