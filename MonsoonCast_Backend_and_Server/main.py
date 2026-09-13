from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from providers import OpenMeteoProvider, ProviderError
from message import send_daily_messages

GRID_STEP = Decimal('0.05')
FORECAST_DAYS = 30
DISPLAY_STEP_HOURS = 3
IST = ZoneInfo('Asia/Kolkata')

@dataclass(frozen=True)
class GridCell:
    latitude: float
    longitude: float
    @property
    def key(self) -> str:
        return f'{self.latitude:.2f}_{self.longitude:.2f}'
    @property
    def filename(self) -> str:
        lat = f"{'n' if self.latitude >= 0 else 's'}{abs(self.latitude):05.2f}"
        lon = f"{'e' if self.longitude >= 0 else 'w'}{abs(self.longitude):05.2f}"
        return f'{lat}_{lon}.json'

def snap_005(value: float) -> float:
    q = (Decimal(str(value)) / GRID_STEP).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return float((q * GRID_STEP).quantize(Decimal('0.01')))

def to_cell(latitude: float, longitude: float) -> GridCell:
    return GridCell(snap_005(latitude), snap_005(longitude))

def load_cells(path: Path) -> tuple[list[GridCell], int]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    items = raw.get('locations') if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError('locations.json must contain a "locations" list.')
    unique: dict[str, GridCell] = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f'Location #{i} must be an object.')
        lat = item.get('latitude', item.get('lat'))
        lon = item.get('longitude', item.get('lon'))
        if lat is None or lon is None:
            raise ValueError(f'Location #{i} is missing latitude/longitude.')
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Location #{i} has invalid coordinates.') from exc
        if not all(map(math.isfinite, (lat, lon))):
            raise ValueError(f'Location #{i} coordinates must be finite.')
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f'Location #{i} coordinates are out of range.')
        cell = to_cell(lat, lon)
        unique.setdefault(cell.key, cell)
    return list(unique.values()), len(items)

def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(path)

def build_index(cells: list[GridCell], generated_at: str) -> dict:
    return {
        'schema_version': 3,
        'generated_at': generated_at,
        'forecast_start_date': datetime.now(IST).date().isoformat(),
        'forecast_days': FORECAST_DAYS,
        'display_interval_hours': DISPLAY_STEP_HOURS,
        'grid_step_degrees': float(GRID_STEP),
        'locations': [
            {'key': c.key, 'latitude': c.latitude, 'longitude': c.longitude, 'file': f'locations/{c.filename}'}
            for c in cells
        ],
    }

def generate(locations_path: Path, output_dir: Path) -> bool:
    cells, raw_count = load_cells(locations_path)
    print(f'Input coordinate requests: {raw_count}')
    print(f'Unique 0.05° cells: {len(cells)}')
    print('Cells:', ', '.join(c.key for c in cells))
    provider = OpenMeteoProvider()
    today = datetime.now(IST).date()
    generated_at = datetime.now(IST).isoformat()
    success = True
    successful_cells = []
    for i, cell in enumerate(cells, 1):
        print(f'[{i}/{len(cells)}] Fetching {cell.key} ...')
        try:
            forecast = provider.build_30_day_forecast(cell.latitude, cell.longitude, today)
        except ProviderError as exc:
            print(f'  ERROR: {exc}')
            print('  Retrying with a fresh provider instance ...')
            try:
                forecast = provider.build_30_day_forecast(cell.latitude, cell.longitude, today)
            except ProviderError as exc:
                print(f'  ERROR: {exc}')
                success = False
            continue
        atomic_write(output_dir / 'locations' / cell.filename, {
            'schema_version': 3,
            'location': {
                'grid_key': cell.key,
                'latitude': cell.latitude,
                'longitude': cell.longitude,
                'grid_step_degrees': float(GRID_STEP),
            },
            'generated_at': generated_at,
            'forecast_start_date': forecast['forecast_start_date'],
            'forecast_end_date': forecast['forecast_end_date'],
            'display_interval_hours': DISPLAY_STEP_HOURS,
            'source': forecast['source'],
            'source_intervals': forecast['source_intervals'],
            'days': forecast['days'],
            'warning': 'Raw model guidance only; SIH ML/downscaling should later produce localized probabilistic predictions.',
        })
        successful_cells.append(cell)
    atomic_write(output_dir / 'index.json', build_index(successful_cells, generated_at))
    print(f'Index written to {output_dir / "index.json"}')

    if successful_cells:
        # Expensive work is deliberately done during the daily refresh, not when
        # a farmer opens the app. Both scripts consume the freshly written cache so even better.
        # and messages are also sent just after calculitaing everything.
        from calculate_outlook import calculate_outlooks
        from make_map import make_map

        outlook_ok = calculate_outlooks(output_dir)
        map_ok = make_map(output_dir) if outlook_ok else False
        success = success and outlook_ok and map_ok

        if success:
            print("Dispatching daily advisories to subscribers...")
            send_daily_messages(output_dir)

    return success

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--locations', type=Path, default=Path('locations.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('data'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    cells, raw_count = load_cells(args.locations)
    print(f'Input coordinate requests: {raw_count}')
    print(f'Unique 0.05° cells: {len(cells)}')
    print('Cells:', ', '.join(c.key for c in cells))
    if args.dry_run:
        return
    if not generate(args.locations, args.output_dir):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
