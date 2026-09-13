"""
ml_model/predict_outlook.py

Loads the trained per-bucket classifiers and scores the CURRENT cached
forecast cells (data/locations/*.json + live climate indices) to produce a
farmer-facing outlook:

    {
      "grid_key": "21.15_81.85",
      "generated_at": "...",
      "outlook": {
        "7d":  {"onset": 0.12, "active": 0.55, "break": 0.10, "revival": 0.05, "normal": 0.18},
        "14d": {...}, "21d": {...}, "30d": {...}
      }
    }

If no trained model exists yet for a bucket (models/model_7d.joblib missing),
falls back to a transparent RULE-BASED heuristic derived straight from the
NWP features -- so the API never returns nothing while the ML model is being
trained. This fallback is intentionally simple as if the model were to change
it will happen over night as well so there wasn't a need to make something else.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib

from ml_model.features import CellFeatureRow, build_features_for_cell, LEAD_BUCKETS

LABELS = ['onset', 'active', 'break', 'revival', 'normal']


def _rule_based_fallback(row: CellFeatureRow) -> dict[str, float]:
    #Transparent heuristic used only when a trained model isn't available yet.
    scores = {label: 0.0 for label in LABELS}
    if row.longest_dry_spell_days >= 7:
        scores['break'] = 0.6
        scores['normal'] = 0.25
    elif row.wet_day_fraction >= 0.6:
        scores['active'] = 0.55
        scores['normal'] = 0.25
    elif row.longest_dry_spell_days >= 4 and row.wet_day_fraction < 0.3:
        scores['break'] = 0.35
        scores['normal'] = 0.45
    else:
        scores['normal'] = 0.6
    scores['onset'] = 0.15 if row.total_rain_mm > 0 else 0.05
    remainder = max(0.0, 1.0 - sum(scores.values()))
    scores['revival'] = round(remainder, 3)
    total = sum(scores.values()) or 1.0
    return {k: round(v / total, 3) for k, v in scores.items()}


class OutlookPredictor:
    def __init__(self, models_dir: Path = Path('models')) -> None:
        self.models_dir = models_dir
        self._cache: dict[str, Any] = {}

    def _load_bucket_model(self, bucket: str):
        if bucket in self._cache:
            return self._cache[bucket]
        path = self.models_dir / f'model_{bucket}.joblib'
        model_bundle = joblib.load(path) if path.exists() else None
        self._cache[bucket] = model_bundle
        return model_bundle

    def score_row(self, row: CellFeatureRow) -> dict[str, float]:
        bundle = self._load_bucket_model(row.lead_bucket)
        if bundle is None:
            return _rule_based_fallback(row)
        model, encoder = bundle['model'], bundle['encoder']
        features = [row.to_feature_dict()[c] for c in bundle['feature_columns']]
        proba = model.predict_proba([features])[0]
        return {label: round(float(p), 3) for label, p in zip(encoder.classes_, proba)}

    def score_cell(self, cell_forecast: dict[str, Any], climate_state: dict[str, Any],
                    climatology_dir: Path | None = None) -> dict[str, Any]:
        rows = build_features_for_cell(cell_forecast, climate_state, climatology_dir)
        outlook = {row.lead_bucket: self.score_row(row) for row in rows}
        return {
            'grid_key': cell_forecast['location']['grid_key'],
            'latitude': cell_forecast['location']['latitude'],
            'longitude': cell_forecast['location']['longitude'],
            'climate_state': climate_state,
            'outlook': outlook,
            'model_source': {
                bucket: ('trained_classifier' if self._load_bucket_model(bucket) else 'rule_based_fallback')
                for bucket in LEAD_BUCKETS
            },
        }


def score_all_cells(data_dir: Path, climate_state: dict[str, Any], models_dir: Path = Path('models'),
                     climatology_dir: Path | None = None) -> list[dict[str, Any]]:
    predictor = OutlookPredictor(models_dir)
    results = []
    for path in sorted((data_dir / 'locations').glob('*.json')):
        cell_forecast = json.loads(path.read_text(encoding='utf-8'))
        results.append(predictor.score_cell(cell_forecast, climate_state, climatology_dir))
    return results


if __name__ == '__main__':
    import argparse
    from climate_indices import ClimateIndexProvider

    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--models-dir', type=Path, default=Path('models'))
    args = parser.parse_args()

    state = ClimateIndexProvider().current_state().as_dict()
    outlooks = score_all_cells(args.data_dir, state, args.models_dir)
    print(json.dumps(outlooks, indent=2))
