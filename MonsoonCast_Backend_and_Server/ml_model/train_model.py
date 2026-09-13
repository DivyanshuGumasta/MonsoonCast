"""
ml_model/train_model.py

Trains one gradient-boosted classifier per lead-time bucket (7d/14d/21d/30d)
that outputs P(onset), P(active), P(break), P(revival) for a grid cell.

Use Build_traning_table.py to
Build `training_data.csv` from CHIRPS + the ONI/DMI/RMM historical series,
one row per (grid_cell, historical_date, lead_bucket). Required columns:

    grid_key, date, lead_bucket,            # identifiers
    total_rain_mm, wet_day_fraction,        # same features as features.py
    max_daily_rain_mm, longest_dry_spell_days,
    mean_rain_probability, climatology_anomaly_pct,
    oni, dmi, mjo_phase, mjo_amplitude, mjo_active,
    label                                    # one of: onset, active, break, revival, normal

Usage:
    python train_model.py --csv training_data.csv --out-dir models/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, log_loss
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib

FEATURE_COLUMNS = [
    'total_rain_mm', 'wet_day_fraction', 'max_daily_rain_mm',
    'longest_dry_spell_days', 'mean_rain_probability', 'climatology_anomaly_pct',
    'oni', 'dmi', 'mjo_phase', 'mjo_amplitude', 'mjo_active',
]
LABELS = ['onset', 'active', 'break', 'revival', 'normal']


def train_one_bucket(df: pd.DataFrame, bucket: str, out_dir: Path) -> dict:
    sub = df[df['lead_bucket'] == bucket].copy()
    if sub.empty:
        raise ValueError(f'No training rows for lead_bucket={bucket!r}')
    sub['mjo_active'] = sub['mjo_active'].astype(float)
    sub[FEATURE_COLUMNS] = sub[FEATURE_COLUMNS].fillna(0.0)

    X = sub[FEATURE_COLUMNS].values
    y_raw = sub['label'].values
    encoder = LabelEncoder().fit(LABELS)
    y = encoder.transform(y_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
    )

    model = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    report = classification_report(y_test, y_pred, target_names=encoder.classes_, output_dict=True, zero_division=0)
    try:
        loss = log_loss(y_test, y_proba, labels=list(range(len(encoder.classes_))))
    except ValueError:
        loss = None

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'encoder': encoder, 'feature_columns': FEATURE_COLUMNS}, out_dir / f'model_{bucket}.joblib')

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.round(4).tolist()))
    metrics = {'bucket': bucket, 'n_train': len(X_train), 'n_test': len(X_test), 'log_loss': loss,
               'classification_report': report, 'feature_importances': importances}
    print(f'[{bucket}] n_train={len(X_train)} n_test={len(X_test)} log_loss={loss}')
    print(f'[{bucket}] top features: {sorted(importances.items(), key=lambda x: -x[1])[:4]}')
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=Path, required=True, help='Training table, see module docstring for schema.')
    parser.add_argument('--out-dir', type=Path, default=Path('models'))
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    missing = set(FEATURE_COLUMNS + ['grid_key', 'date', 'lead_bucket', 'label']) - set(df.columns)
    if missing:
        raise SystemExit(f'training_data.csv is missing required columns: {sorted(missing)}')

    all_metrics = []
    for bucket in ['7d', '14d', '21d', '30d']:
        if bucket in df['lead_bucket'].unique():
            all_metrics.append(train_one_bucket(df, bucket, args.out_dir))
    (args.out_dir / 'training_report.json').write_text(json.dumps(all_metrics, indent=2), encoding='utf-8')
    print(f'\nModels + training_report.json written to {args.out_dir}/')


if __name__ == '__main__':
    print('=== TRAINING MODELS ===')
    main()
