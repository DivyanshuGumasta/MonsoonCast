"""
ml_model/build_training_table.py

Turns:
  - data/climate_history/chirps_daily_rain.csv   (date, grid_key, rain_mm)
  - data/climate_history/oni_history.csv          (year, month, oni)
  - data/climate_history/dmi_history.csv          (year, month, dmi)
  - data/climate_history/rmm_history.csv          (date, rmm_phase, rmm_amplitude)

into training_data.csv, matching the exact schema ml_model/train_model.py expects.

METHODOLOGY (perfect-prognosis approach -- standard in seasonal statistical
downscaling): decades of archived past NWP forecasts don't exist to be downloaded
by public, so the window features (total_rain_mm, wet_day_fraction, etc.) 
are computed from CHIRPS *actual* rainfall in the lead window, not a forecast of it. 
The model learns "given the climate index state today, what does the next N days' rainfall
actually look like" -- then at INFERENCE time (predict_outlook.py) the same
feature slots are filled from the live Open-Meteo/EC46 *forecast* instead.

Label derivation (do this when building the CSV from raw rainfall):
  - onset:    first date the 5-day running rainfall crosses the IMD onset
              threshold for that subdivision, having not yet occurred that year
  - break:    a spell of >= 7 consecutive days within monsoon season with
              < 2.5mm/day, occurring AFTER onset
  - revival:  first day with >= 2 consecutive wet days (>=2.5mm) immediately
              following a break spell
  - active:   wet_day_fraction over the window >= 0.6 and not a revival day
  - normal:   none of the above

This mirrors IMD's own operational active/break definitions from
(2015/2017) "Break-monsoon conditions over India".

A window is labeled by priority: onset > break > revival > active > normal
(i.e. if the onset date falls inside the window, that wins regardless of
what else the window contains -- onset is the single most decision-relevant
event for a farmer).

Usage:
    python -m ml_model.build_training_table \\
        --chirps data/climate_history/chirps_daily_rain.csv \\
        --climate-dir data/climate_history \\
        --out training_data.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

WET_MM = 2.5
DRY_SPELL_MIN_DAYS = 7
ONSET_WINDOW = ('05-01', '07-31')
SEASON_END = '09-30'
LEAD_BUCKETS = {'7d': 7, '14d': 14, '21d': 21, '30d': 30}


def find_onset_dates(cell_df: pd.DataFrame) -> dict[int, pd.Timestamp]:
    # One onset date per calendar year for this cell, or no entry if none found.
    cell_df = cell_df.set_index('date').sort_index()
    onsets = {}
    for year in sorted(cell_df.index.year.unique()):
        start = pd.Timestamp(f'{year}-{ONSET_WINDOW[0]}')
        end = pd.Timestamp(f'{year}-{ONSET_WINDOW[1]}')
        window = cell_df.loc[start:end, 'rain_mm']
        if window.empty:
            continue
        rolling5 = window.rolling(5, min_periods=5).sum()
        hit = rolling5[rolling5 >= 50.0]
        if not hit.empty:
            onsets[year] = hit.index[0]
    return onsets

def find_break_and_revival_dates(cell_df: pd.DataFrame, onsets: dict[int, pd.Timestamp]) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    # Returns (break_start_dates, revival_dates) across all seasons for this cell.
    cell_df = cell_df.set_index('date').sort_index()
    break_starts, revivals = [], []
    for year, onset_date in onsets.items():
        season_end = pd.Timestamp(f'{year}-{SEASON_END}')
        season = cell_df.loc[onset_date:season_end, 'rain_mm']
        if season.empty:
            continue
        is_dry = (season < WET_MM).astype(int)
        run_id = (is_dry != is_dry.shift(fill_value=0)).cumsum()
        for _, group in is_dry.groupby(run_id):
            if group.iloc[0] == 1 and len(group) >= DRY_SPELL_MIN_DAYS:
                spell_start = group.index[0]
                spell_end = group.index[-1]
                break_starts.append(spell_start)
                after = season.loc[spell_end:].iloc[1:]  # days strictly after the spell
                wet_after = after[after >= WET_MM]
                if not wet_after.empty:
                    revivals.append(wet_after.index[0])
    return break_starts, revivals

def label_window(window_dates: pd.DatetimeIndex, window_rain: pd.Series, onset_date: pd.Timestamp | None,
                  break_starts: list[pd.Timestamp], revivals: list[pd.Timestamp]) -> str:
    if onset_date is not None and window_dates[0] <= onset_date <= window_dates[-1]:
        return 'onset'
    if any(window_dates[0] <= b <= window_dates[-1] for b in break_starts):
        return 'break'
    if any(window_dates[0] <= r <= window_dates[-1] for r in revivals):
        return 'revival'
    wet_fraction = (window_rain >= WET_MM).mean()
    if wet_fraction >= 0.6:
        return 'active'
    return 'normal'


def climatology_features(cell_df: pd.DataFrame) -> dict[int, float]:
    # Mean total rainfall per day-of-year across all years, for the anomaly feature.
    cell_df = cell_df.copy()
    cell_df['doy'] = cell_df['date'].dt.dayofyear
    return cell_df.groupby('doy')['rain_mm'].mean().to_dict()


def build_table(chirps_csv: Path, climate_dir: Path) -> pd.DataFrame:
    rain = pd.read_csv(chirps_csv, parse_dates=['date'])
    oni = pd.read_csv(climate_dir / 'oni_history.csv')
    dmi = pd.read_csv(climate_dir / 'dmi_history.csv')
    rmm = pd.read_csv(climate_dir / 'rmm_history.csv', parse_dates=['date'])
    rmm = rmm.set_index('date')

    rows = []
    for grid_key, cell_df in rain.groupby('grid_key'):
        cell_df = cell_df[['date', 'rain_mm']].sort_values('date').reset_index(drop=True)
        onsets = find_onset_dates(cell_df)
        break_starts, revivals = find_break_and_revival_dates(cell_df, onsets)
        doy_mean = climatology_features(cell_df)
        indexed = cell_df.set_index('date')['rain_mm']

        onset_by_year = onsets  # {year: date}
        all_dates = cell_df['date']
        print(f'{grid_key}: {len(onsets)} onset years, {len(break_starts)} break spells, {len(revivals)} revivals')

        for current_date in all_dates:
            year = current_date.year
            onset_date = onset_by_year.get(year)
            for bucket_name, n_days in LEAD_BUCKETS.items():
                window_end = current_date + pd.Timedelta(days=n_days - 1)
                window = indexed.loc[current_date:window_end]
                if len(window) < n_days:
                    continue  # ran off the end of available data

                label = label_window(window.index, window, onset_date, break_starts, revivals)

                total_rain = float(window.sum())
                wet_fraction = float((window >= WET_MM).mean())
                max_daily = float(window.max())
                is_dry = (window < WET_MM).astype(int)
                run_id = (is_dry != is_dry.shift(fill_value=0)).cumsum()
                longest_dry = int(is_dry.groupby(run_id).sum().max()) if not is_dry.empty else 0

                doy_keys = [(d.dayofyear) for d in window.index]
                expected = sum(doy_mean.get(k, 0.0) for k in doy_keys)
                anomaly_pct = round((total_rain - expected) / expected * 100.0, 1) if expected > 0 else 0.0

                month_key = (year, current_date.month)
                oni_val = oni[(oni.year == month_key[0]) & (oni.month == month_key[1])]['oni']
                dmi_val = dmi[(dmi.year == month_key[0]) & (dmi.month == month_key[1])]['dmi']
                rmm_row = rmm.reindex([current_date], method='nearest', tolerance=pd.Timedelta(days=3))

                rows.append({
                    'grid_key': grid_key, 'date': current_date.date().isoformat(), 'lead_bucket': bucket_name,
                    'total_rain_mm': round(total_rain, 2), 'wet_day_fraction': round(wet_fraction, 3),
                    'max_daily_rain_mm': round(max_daily, 2), 'longest_dry_spell_days': longest_dry,
                    'mean_rain_probability': round(wet_fraction, 3),  # no obs-based probability; wet-day fraction proxy
                    'climatology_anomaly_pct': anomaly_pct,
                    'oni': float(oni_val.iloc[0]) if len(oni_val) else np.nan,
                    'dmi': float(dmi_val.iloc[0]) if len(dmi_val) else np.nan,
                    'mjo_phase': float(rmm_row['rmm_phase'].iloc[0]) if not rmm_row.empty and not pd.isna(rmm_row['rmm_phase'].iloc[0]) else np.nan,
                    'mjo_amplitude': float(rmm_row['rmm_amplitude'].iloc[0]) if not rmm_row.empty and not pd.isna(rmm_row['rmm_amplitude'].iloc[0]) else np.nan,
                    'mjo_active': bool(rmm_row['rmm_amplitude'].iloc[0] >= 1.0) if not rmm_row.empty and not pd.isna(rmm_row['rmm_amplitude'].iloc[0]) else False,
                    'label': label,
                })
    return pd.DataFrame(rows)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--chirps', type=Path, default=Path('data/climate_history/chirps_daily_rain.csv'))
    parser.add_argument('--climate-dir', type=Path, default=Path('data/climate_history'))
    parser.add_argument('--out', type=Path, default=Path('training_data.csv'))
    args = parser.parse_args()

    df = build_table(args.chirps, args.climate_dir)
    df.to_csv(args.out, index=False)
    print(f'\nWrote {len(df)} training rows -> {args.out}')
    print('\nLabel distribution:')
    print(df['label'].value_counts())

if __name__ == '__main__':
    main()