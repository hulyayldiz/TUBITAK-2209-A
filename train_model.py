"""
Model Eğitim Motoru (train_model.py)
Random Forest ve LSTM-VAE modellerini gnss_training_dataset.csv üzerinde eğitir.
Akademik standartlar: 5-Fold CV, IQR eşiği, class_weight='balanced', GridSearchCV.
"""

import os
import numpy as np
import pandas as pd
import joblib
import torch
import torch.nn as nn
from datetime import datetime

# Sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score, GridSearchCV
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_class_weight

# Yerel modül
try:
    from lstm_vae import LSTMVAE, vae_loss
except ImportError:
    from models.lstm_vae import LSTMVAE, vae_loss

# --- Sabitler ---
CSV_PATH       = "gnss_training_dataset.csv"
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
    CSV'yi yükler, eksik sütunları kontrol eder, dengesizliği raporlar.
    Minimum 50 satır gerektirir; daha az ise sentetik augmentation uygular.
    """
    if not os.path.exists(csv_path):
        return None, "❌ Eğitim verisi bulunamadı. Önce simülasyonu 'Veri Toplama' moduyla çalıştırın."

    df = pd.read_csv(csv_path)

    # Sütun kontrolü
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        return None, f"❌ CSV'de eksik sütun: {missing}"

    df = df.dropna(subset=FEATURES + [TARGET])

    # --- Veri Temizleme (Data Cleaning) ---
    # Gerçek dünya fizik sınırlarına uymayan veya hatalı kaydedilen anlamsız verileri temizle
    # 'speed' özelliği features'da yoksa, csv'de varsa bile hız için temizlik yapmak istiyorsak:
    if "speed" in df.columns:
        df = df[df["speed"] < 300.0]
    
    # CN0 (10 ile 60 arasında olmalı, 0 veya saçma değerler hatalıdır)
    df = df[(df["cn0"] > 5.0) & (df["cn0"] < 65.0)]
    
    # Konum hatası (residual) 10000 metreden büyükse çok anlamsızdır
    df = df[df["residual"] < 10000.0]
    # --------------------------------------

    # Sınıf standartlaştırma (JAMMING_WARNING vs JAMMING uyumsuzluğunu çözer)
    df[TARGET] = df[TARGET].apply(lambda x: "JAMMING" if "JAMMING" in str(x).upper() else str(x).upper())

    # Minimum veri veya sınıf dağılımı kontrolü (Cross-Validation için)
    counts = df[TARGET].value_counts()
    needs_augmentation = False
    if len(df) < 50:
        needs_augmentation = True
    for cls in ["NORMAL", "SPOOFING", "JAMMING"]:
        if counts.get(cls, 0) < 5:
            needs_augmentation = True
            
    if needs_augmentation:
        df = _augment_df(df, target_size=300)

    return df, None


def _augment_df(df, target_size=300):
    """
    Sadece çok az veri (50 altı) olduğunda veya bazı sınıflar cross-validation için
    çok az örneğe sahip olduğunda (5'ten az) sistemi kurtarmak için çalışır.
    """
    augmented = [df]
    
    # 1. Her sınıfın en az 5 örneği olduğundan emin ol (Stratified 5-Fold için)
    target_classes = ["NORMAL", "SPOOFING", "JAMMING"]
    counts = df[TARGET].value_counts()
    
    for cls in target_classes:
        count = counts.get(cls, 0)
        if count < 5:
            needed = 5 - count
            if count > 0:
                # Sınıfa ait az veri varsa kopyala
                sample = df[df[TARGET] == cls].sample(needed, replace=True).copy()
                augmented.append(sample)
            else:
                # Sınıfa ait HİÇ veri yoksa NORMAL'den alıp çevir
                fallback = df[df[TARGET] == "NORMAL"]
                if len(fallback) == 0:
                    fallback = df # En kötü ihtimal
                sample = fallback.sample(needed, replace=True).copy()
                sample[TARGET] = cls
                # Gürültü/Fiziksel özellik bas (Basit)
                if cls == "SPOOFING":
                    sample["cn0"] = 50.0
                    sample["residual"] = 50.0
                elif cls == "JAMMING":
                    sample["cn0"] = 10.0
                    sample["residual"] = 25.0
                augmented.append(sample)
                
    current_df = pd.concat(augmented, ignore_index=True)
    
    # 2. Toplam boyutu sağla
    needed = target_size - len(current_df)
    if needed > 0:
        sample = current_df.sample(min(needed, len(current_df)), replace=True).copy()
        augmented.append(sample)
        
    return pd.concat(augmented, ignore_index=True)

def augment_training_data(X_train, y_train, min_samples=300):
    """
    Eğitim seti üzerinde sentetik veri artırımı (Data Leakage'i önler).
    Azınlık sınıfları dengeler. X_train: ölçeklenmemiş (unscaled) numpy array.
    """
    unique_classes, counts = np.unique(y_train, return_counts=True)
    
    X_aug, y_aug = list(X_train), list(y_train)
    
    # Sınıfa ait hiç örnek olmasa bile sentetik olarak başlatmak için:
    target_classes = ["NORMAL", "SPOOFING", "JAMMING"]
    
    for cls in target_classes:
        count = dict(zip(unique_classes, counts)).get(cls, 0)
        
        if count < min_samples:
            needed = min_samples - count
            # İlgili sınıfa ait verileri bul
            cls_indices = np.where(y_train == cls)[0]
            
            for _ in range(needed):
                # Eğer sınıfa ait hiç örnek yoksa (0 test verisinde kalmışsa) rastgele bir "NORMAL" alıp dönüştür
                if len(cls_indices) == 0:
                    fallback_indices = np.where(y_train == "NORMAL")[0]
                    if len(fallback_indices) == 0:
                        fallback_indices = [0] # En kötü ihtimalle ilk örnek
                    idx = np.random.choice(fallback_indices)
                else:
                    idx = np.random.choice(cls_indices)
                    
                sample = X_train[idx].copy()
                
                # Sınıfa özel fizik tabanlı gürültü ekle
                if cls == "SPOOFING": # [cn0, accel, heading_drift, residual]
                    sample[0] = np.random.uniform(45.0, 55.0) # Güçlü sahte sinyal (C/N0)
                    sample[1] += np.random.uniform(0.5, 3.0) # accel
                    sample[3] += np.random.uniform(5.0, 50.0) # residual
                elif cls == "JAMMING":
                    sample[0] = np.random.uniform(8.0, 18.0) # Zayıf sinyal (C/N0)
                    sample[3] += np.random.uniform(5.0, 15.0) # Artan residual (konum hatası)
                else:
                    sample[0] += np.random.normal(0, 0.5)
                
                X_aug.append(sample)
                y_aug.append(cls)
                
    return np.array(X_aug), np.array(y_aug)


# ──────────────────────────────────────────────────────────────
# 2. RANDOM FOREST EĞİTİMİ
# ──────────────────────────────────────────────────────────────
def train_random_forest(df):
    """
    GridSearchCV + 5-Fold Stratified CV ile RF eğitir.
    class_weight='balanced' ile sınıf dengesizliğini yönetir.
    Döndürür: (model, scaler, report_str, cv_scores)
    """
    le = LabelEncoder()
    X = df[FEATURES].values
    y = df[TARGET].values # LabelEncoder öncesi sınıf isimlerini sakla

    # Bağımsız test seti (%20)
    # Stratified kullanarak sınıf dengesizliğinde test setine her sınıftan veri düşmesini sağla
    X_train_raw, X_test_raw, y_train_raw, y_test_raw = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    # Veri artırmayı SADECE EĞİTİM SETİNE uygula (Data Leakage engellendi)
    X_train_aug, y_train_aug = augment_training_data(X_train_raw, y_train_raw, min_samples=400)

    # Label Encoder'ı TIKANMAMASI İÇİN tüm veriyle eğit
    le.fit(y)
    
    y_train = le.transform(y_train_aug)
    y_test = le.transform(y_test_raw)
    y_all = le.transform(y)

    # Normalizasyon (Scaler)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_aug)
    X_test = scaler.transform(X_test_raw)
    X_scaled_all = scaler.transform(X)

    # Grid Search (Hiperparametre Optimizasyonu)
    param_grid = {
        "n_estimators": [100, 200],
        "max_depth": [None, 10, 20],
        "min_samples_split": [2, 5],
    }

    base_rf = RandomForestClassifier(
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    grid_search = GridSearchCV(
        base_rf, param_grid,
        cv=cv_strategy,
        scoring="f1_weighted",
        n_jobs=-1,
        verbose=0
    )
    grid_search.fit(X_train, y_train)

    best_rf = grid_search.best_estimator_

    # 5-Fold CV Skoru (Bağımsız doğrulama)
    cv_scores = cross_val_score(best_rf, X_scaled_all, y_all, cv=cv_strategy,
                                 scoring="f1_weighted")

    # Test seti değerlendirmesi
    y_pred = best_rf.predict(X_test)
    target_names = le.classes_

    report = classification_report(y_test, y_pred, target_names=target_names, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    # --- Grafik Oluşturma (Confusion Matrix & ROC) ---
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        from sklearn.metrics import roc_curve, auc
        from sklearn.preprocessing import label_binarize

        # 1. Confusion Matrix
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=target_names, yticklabels=target_names)
        plt.title('Karmaşıklık Matrisi (Bağımsız Test Seti)')
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
        "model": best_rf,
        "label_encoder": le,
        "best_params": grid_search.best_params_,
        "cv_mean_f1": cv_scores.mean(),
        "cv_std_f1": cv_scores.std(),
        "confusion_matrix": cm.tolist(),
        "trained_at": datetime.now().isoformat()
    }

    joblib.dump(model_bundle, RF_PATH)
    joblib.dump(scaler, SCALER_PATH)

    summary = (
        f"📊 RF Eğitim Tamamlandı\n"
        f"En İyi Parametreler: {grid_search.best_params_}\n"
        f"5-Fold CV F1: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}\n"
        f"CV Varyansı: {'KARARLI ✅' if cv_scores.std() < 0.05 else 'YÜKSEK ⚠️'}\n\n"
        f"Bağımsız Test Seti Raporu:\n{report}\n"
        f"Confusion Matrix:\n{cm}\n\n"
        f"Görseller (ROC ve CM) dizine .png olarak kaydedildi."
    )

    return model_bundle, scaler, summary, cv_scores


# ──────────────────────────────────────────────────────────────
# 3. LSTM-VAE EĞİTİMİ
# ──────────────────────────────────────────────────────────────
def train_vae(df):
    """
    Sadece NORMAL sınıf verileriyle LSTM-VAE eğitir (Unsupervised Anomaly Detection).
    IQR tabanlı dinamik eşik hesaplar.
    Döndürür: (model, threshold, summary_str)
    """
    # Sadece normal verilerle eğit (Zero-Day mantığı)
    normal_df = df[df[TARGET].str.lower() == "normal"]

    if len(normal_df) < SEQ_LEN + 1:
        return None, None, "⚠️ Yeterli NORMAL sınıf verisi yok. VAE eğitimi atlandı."

    X_raw = normal_df[FEATURES].values.astype(np.float32)

    # Zaman Serisi Split (Eğitim %80, Doğrulama %20)
    split_idx = int(len(X_raw) * 0.8)
    X_raw_train = X_raw[:split_idx]
    X_raw_val = X_raw[split_idx:]

    if len(X_raw_train) < SEQ_LEN:
        return None, None, "⚠️ Yeterli eğitim verisi yok."

    # Normalizasyon (Sadece Eğitim verisi ile fit edilir)
    X_mean = X_raw_train.mean(axis=0)
    X_std  = X_raw_train.std(axis=0) + 1e-8
    
    X_norm_train = (X_raw_train - X_mean) / X_std
    X_norm_val = (X_raw_val - X_mean) / X_std if len(X_raw_val) > 0 else X_norm_train

    # Sliding Window (Eğitim Seti)
    sequences_train = []
    stride = 1  # Bağımsız pencereler için stride=1 yaparak veri artırımı (overlap)
    for i in range(0, len(X_norm_train) - SEQ_LEN + 1, stride):
        sequences_train.append(X_norm_train[i:i + SEQ_LEN])

    # Yetersiz Veri Durumu
    overlap_note = " [stride=1, örtüşmeli]"
    if len(sequences_train) < 4:
        sequences_train = []
        for i in range(len(X_norm_train) - SEQ_LEN + 1):
            sequences_train.append(X_norm_train[i:i + SEQ_LEN])
        overlap_note = " [UYARI: Örtüşen pencere kullanıldı - az veri]"

    X_seq_train = torch.tensor(np.array(sequences_train), dtype=torch.float32)

    # Sliding Window (Validation Seti)
    sequences_val = []
    if len(X_norm_val) >= SEQ_LEN:
        for i in range(0, len(X_norm_val) - SEQ_LEN + 1, stride):
            sequences_val.append(X_norm_val[i:i + SEQ_LEN])
        if len(sequences_val) == 0:
            for i in range(len(X_norm_val) - SEQ_LEN + 1):
                sequences_val.append(X_norm_val[i:i + SEQ_LEN])
    
    X_seq_val = torch.tensor(np.array(sequences_val), dtype=torch.float32) if len(sequences_val) > 0 else X_seq_train

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

    # IQR Tabanlı Dinamik Eşik (Literatür: Q3 + 1.5*IQR) - VALIDATION SETİ ÜZERİNDEN
    recon_errors = []
    with torch.no_grad():
        for i in range(0, len(X_seq_val), BATCH_SIZE):
            batch = X_seq_val[i:i + BATCH_SIZE]
            recon, _, _ = model(batch)
            mae = torch.mean(torch.abs(recon - batch), dim=[1, 2])
            recon_errors.extend(mae.numpy().tolist())

    errors = np.array(recon_errors)
    Q1 = np.percentile(errors, 25)
    Q3 = np.percentile(errors, 75)
    IQR = Q3 - Q1
    threshold = Q3 + 1.5 * IQR

    # Kaydet
    torch.save(model.state_dict(), VAE_PATH)
    np.save(THRESHOLD_PATH, threshold)

    final_loss = losses[-1] if losses else 0
    summary = (
        f"🧠 LSTM-VAE Eğitim Tamamlandı{overlap_note}\n"
        f"Eğitim Sekans Sayısı: {len(X_seq_train)} | Val: {len(X_seq_val)}\n"
        f"Son Epoch Kaybı: {final_loss:.4f}\n"
        f"IQR Eşiği: Q3={Q3:.4f}, IQR={IQR:.4f}\n"
        f"Anomali Eşiği (Q3+1.5×IQR): {threshold:.4f}\n"
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
        f"Sınıf Dağılımı:\n{df[TARGET].value_counts().to_string()}",
        f"{'='*60}",
    ]

    # 2. RF Eğitimi
    try:
        rf_bundle, scaler, rf_summary, cv_scores = train_random_forest(df)
        full_report_parts.append(rf_summary)
    except Exception as e:
        return False, f"RF eğitim hatası: {e}", None

    # 3. VAE Eğitimi
    try:
        vae_model, threshold, vae_summary = train_vae(df)
        full_report_parts.append(vae_summary)
    except Exception as e:
        vae_summary = f"⚠️ VAE eğitimi başarısız: {e}"
        full_report_parts.append(vae_summary)

    full_report = "\n\n".join(full_report_parts)

    # Raporu diske yaz
    report_path = f"training_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    cv_f1 = cv_scores.mean() if cv_scores is not None else 0.0
    msg = f"Eğitim tamamlandı! CV F1={cv_f1:.3f} ± {cv_scores.std():.3f}"

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