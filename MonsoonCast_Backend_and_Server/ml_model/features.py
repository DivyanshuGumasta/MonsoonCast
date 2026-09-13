"""
ml_model/features.py

Builds the feature vector the downscaling model consumes, for one grid cell,
for one lead-time bucket (7/14/21/30 days).

Two feature groups, matching the hybrid-model design in DATASETS_AND_MODEL.md:

  1. LOCAL / NWP features   -- derived from the cell's cached 30-day forecast
     JSON that main.py + providers.py already produce (data/locations/*.json)
  2. GLOBAL / teleconnection features -- from climate_indices.py

Kept dependency-free (just stdlib) so it can run in the same environment as
the rest of the backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

LEAD_BUCKETS = {'7d': 7, '14d': 14, '21d': 21, '30d': 30}
DRY_DAY_MM_THRESHOLD = 2.5   # a day with < 2.5mm total is "dry" for spell counting
WET_DAY_MM_THRESHOLD = 2.5


@dataclass
class CellFeatureRow:
    grid_key: str
    lead_bucket: str
    forecast_start_date: str
    total_rain_mm: float
    wet_day_fraction: float
    max_daily_rain_mm: float
    longest_dry_spell_days: int
    mean_rain_probability: float
    climatology_anomaly_pct: float | None
    oni: float | None
    dmi: float | None
    mjo_phase: int | None
    mjo_amplitude: float | None
    mjo_active: bool

    def to_feature_dict(self) -> dict[str, float]:
        # Numeric-only view for feeding a scikit-learn/XGBoost model.
        return {
            'total_rain_mm': self.total_rain_mm,
            'wet_day_fraction': self.wet_day_fraction,
            'max_daily_rain_mm': self.max_daily_rain_mm,
            'longest_dry_spell_days': float(self.longest_dry_spell_days),
            'mean_rain_probability': self.mean_rain_probability,
            'climatology_anomaly_pct': self.climatology_anomaly_pct if self.climatology_anomaly_pct is not None else 0.0,
            'oni': self.oni if self.oni is not None else 0.0,
            'dmi': self.dmi if self.dmi is not None else 0.0,
            'mjo_phase': float(self.mjo_phase or 0),
            'mjo_amplitude': self.mjo_amplitude if self.mjo_amplitude is not None else 0.0,
            'mjo_active': 1.0 if self.mjo_active else 0.0,
        }


def _longest_dry_spell(daily_rain_mm: list[float]) -> int:
    longest = current = 0
    for mm in daily_rain_mm:
        if mm < DRY_DAY_MM_THRESHOLD:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def load_cell_climatology(climatology_dir: Path, grid_key: str) -> dict[str, float] | None:
    path = climatology_dir / f'{grid_key}.json'
    if not path.exists():
        return None
    import json
    return json.loads(path.read_text(encoding='utf-8'))

def build_features_for_cell(
    cell_forecast: dict[str, Any],
    climate_state: dict[str, Any],
    climatology_dir: Path | None = None,
) -> list[CellFeatureRow]:
    """
    cell_forecast: the parsed JSON already written by main.py to
                   data/locations/<cell>.json  (has 'days': [...])
    climate_state: ClimateState.as_dict() from climate_indices.py
    """
    days = cell_forecast['days']
    grid_key = cell_forecast['location']['grid_key']
    start = date.fromisoformat(cell_forecast['forecast_start_date'])
    climatology = load_cell_climatology(climatology_dir, grid_key) if climatology_dir else None

    rows = []
    for bucket_name, n_days in LEAD_BUCKETS.items():
        window = days[:n_days]
        if not window:
            continue
        daily_rain = [d['rain_mm'] for d in window]
        probs = [d['rain_probability_max'] for d in window if d.get('rain_probability_max') is not None]
        total_rain = sum(daily_rain)
        wet_days = sum(1 for mm in daily_rain if mm >= WET_DAY_MM_THRESHOLD)

        anomaly_pct = None
        if climatology:
            doy_keys = [str((start.timetuple().tm_yday + i - 1) % 366 + 1) for i in range(n_days)]
            expected = sum(climatology.get('doy_mean_mm', {}).get(k, 0.0) for k in doy_keys)
            if expected > 0:
                anomaly_pct = round((total_rain - expected) / expected * 100.0, 1)

        rows.append(CellFeatureRow(
            grid_key=grid_key,
            lead_bucket=bucket_name,
            forecast_start_date=start.isoformat(),
            total_rain_mm=round(total_rain, 2),
            wet_day_fraction=round(wet_days / len(window), 3),
            max_daily_rain_mm=round(max(daily_rain, default=0.0), 2),
            longest_dry_spell_days=_longest_dry_spell(daily_rain),
            mean_rain_probability=round(sum(probs) / len(probs), 3) if probs else 0.0,
            climatology_anomaly_pct=anomaly_pct,
            oni=climate_state.get('oni'),
            dmi=climate_state.get('dmi'),
            mjo_phase=climate_state.get('mjo_phase'),
            mjo_amplitude=climate_state.get('mjo_amplitude'),
            mjo_active=bool(climate_state.get('mjo_active')),
        ))
    return rows
