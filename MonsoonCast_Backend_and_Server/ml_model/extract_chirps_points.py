"""
ml_model/extract_chirps_points.py

Reads the yearly CHIRPS NetCDF files downloaded through cmd command in "DATASETS_AND_MODEL.md" file and
extracts a daily rainfall time series for each of THE grid cells (same
0.05deg cells main.py already snaps farmer coordinates to -- so training
labels line up exactly with the cells the API serves).

Output: data/climate_history/chirps_daily_rain.csv
    columns: date, grid_key, rain_mm

Usage:
    python -m ml_model.extract_chirps_points \\
        --chirps-dir chirps_raw \\
        --locations locations.json \\
        --out data/climate_history/chirps_daily_rain.csv

Requires: pip install xarray netCDF4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from main import to_cell  # reuse the exact same 0.05deg snapping logic as the live API


def _find_precip_var(ds) -> str:
    for candidate in ('precip', 'precipitation', 'pr', 'chirps'):
        if candidate in ds.data_vars:
            return candidate
    raise ValueError(f'Could not find a precipitation variable in dataset. Available: {list(ds.data_vars)}')


def extract(chirps_dir: Path, locations_path: Path, out_path: Path) -> None:
    import xarray as xr  # imported here so the rest of the addon doesn't require xarray

    raw = json.loads(locations_path.read_text(encoding='utf-8'))
    items = raw.get('locations') if isinstance(raw, dict) else raw
    cells = {}
    for item in items:
        lat = item.get('latitude', item.get('lat'))
        lon = item.get('longitude', item.get('lon'))
        cell = to_cell(float(lat), float(lon))
        cells[cell.key] = (cell.latitude, cell.longitude)
    print(f'Extracting rainfall for {len(cells)} unique grid cells: {list(cells)}')

    nc_files = sorted(chirps_dir.glob('chirps-v2.0.*.days_p05.nc'))
    if not nc_files:
        raise SystemExit(f'No CHIRPS files found in {chirps_dir}. Run download_chirps.sh first.')

    all_rows = []
    for nc_file in nc_files:
        print(f'Reading {nc_file.name} ...')
        ds = xr.open_dataset(nc_file)
        var = _find_precip_var(ds)
        lat_name = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_name = 'longitude' if 'longitude' in ds.coords else 'lon'
        for grid_key, (lat, lon) in cells.items():
            point = ds[var].sel({lat_name: lat, lon_name: lon}, method='nearest')
            series = point.to_series()
            for date, rain in series.items():
                if pd.isna(rain):
                    continue
                all_rows.append({'date': pd.Timestamp(date).date().isoformat(), 'grid_key': grid_key, 'rain_mm': max(0.0, float(rain))})
        ds.close()

    df = pd.DataFrame(all_rows).sort_values(['grid_key', 'date'])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f'Wrote {len(df)} rows -> {out_path}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--chirps-dir', type=Path, required=True)
    parser.add_argument('--locations', type=Path, default=Path('locations.json'))
    parser.add_argument('--out', type=Path, default=Path('data/climate_history/chirps_daily_rain.csv'))
    args = parser.parse_args()
    extract(args.chirps_dir, args.locations, args.out)


if __name__ == '__main__':
    main()
