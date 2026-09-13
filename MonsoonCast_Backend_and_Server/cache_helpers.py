from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from climate_indices import ClimateIndexError, ClimateIndexProvider
from main import GRID_STEP, GridCell, atomic_write, to_cell
from ml_model.predict_outlook import OutlookPredictor
from providers import OpenMeteoProvider, ProviderError

DEFAULT_DATA_DIR = Path('data')
DEFAULT_LOCATIONS_PATH = Path('locations.json')
DEFAULT_MODELS_DIR = Path('models')


class CacheGenerationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def _read_locations(locations_path: Path) -> list[dict[str, Any]]:
    if not locations_path.exists():
        return []
    raw = _read_json(locations_path)
    items = raw.get('locations') if isinstance(raw, dict) else raw
    return items if isinstance(items, list) else []


def add_cell_to_locations_json(
    cell: GridCell,
    locations_path: Path = DEFAULT_LOCATIONS_PATH,
) -> bool:
    """Persist the canonical 0.05° cell in locations.json exactly once."""
    items = _read_locations(locations_path)
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        lat = item.get('latitude', item.get('lat'))
        lon = item.get('longitude', item.get('lon'))
        if lat is None or lon is None:
            continue
        try:
            seen.add(to_cell(float(lat), float(lon)).key)
        except (TypeError, ValueError):
            continue

    if cell.key in seen:
        return False

    items.append({'latitude': cell.latitude, 'longitude': cell.longitude})
    atomic_write(locations_path, {'locations': items})
    return True


def rebuild_forecast_index(
    data_dir: Path = DEFAULT_DATA_DIR,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Rebuild index.json from actual cached forecast files."""
    location_dir = data_dir / 'locations'
    entries: list[dict[str, Any]] = []
    for path in sorted(location_dir.glob('*.json')):
        try:
            payload = _read_json(path)
            location = payload.get('location', {})
            key = location['grid_key']
            entries.append({
                'key': key,
                'latitude': location['latitude'],
                'longitude': location['longitude'],
                'file': f'locations/{path.name}',
            })
        except (OSError, json.JSONDecodeError, KeyError):
            continue

    now = datetime.now().astimezone()
    index = {
        'schema_version': 4,
        'generated_at': generated_at or now.isoformat(),
        'forecast_start_date': now.date().isoformat(),
        'forecast_days': 30,
        'display_interval_hours': 3,
        'grid_step_degrees': float(GRID_STEP),
        'locations': entries,
    }
    atomic_write(data_dir / 'index.json', index)
    return index


def new_forecast(
    latitude, 
    longitude,
    data_dir: Path = DEFAULT_DATA_DIR,
    locations_path: Path = DEFAULT_LOCATIONS_PATH,
    provider: OpenMeteoProvider | None = None,
) -> dict[str, Any]:
    """
    Create and persist a forecast for a previously unseen 0.05° cell.

    THings it does:
      1. Canonical cell is appended to locations.json if absent.
      2. Real 30-day forecast is fetched.
      3. data/locations/<cell>.json is atomically written.
      4. data/index.json is updated.

    Returns the freshly-created forecast JSON.
    and because the locations.json now has the cords it will be now calculated at night alongside other locations every night.
    """
    cell = to_cell(latitude, longitude)
    output_path = data_dir / 'locations' / cell.filename

    if output_path.exists():
        try:
            return _read_json(output_path)
        except (OSError, json.JSONDecodeError):
            pass

    provider = provider or OpenMeteoProvider()
    today = datetime.now().astimezone().date()
    generated_at = datetime.now().astimezone().isoformat()

    try:
        forecast = provider.build_30_day_forecast(cell.latitude, cell.longitude, today)
    except ProviderError as exc:
        raise CacheGenerationError(f'Could not create forecast for {cell.key}: {exc}') from exc

    add_cell_to_locations_json(cell, locations_path)

    payload = {
        'schema_version': 4,
        'location': {
            'grid_key': cell.key,
            'latitude': cell.latitude,
            'longitude': cell.longitude,
            'grid_step_degrees': float(GRID_STEP),
        },
        'generated_at': generated_at,
        'forecast_start_date': forecast['forecast_start_date'],
        'forecast_end_date': forecast['forecast_end_date'],
        'display_interval_hours': 3,
        'source': forecast['source'],
        'source_intervals': forecast['source_intervals'],
        'days': forecast['days'],
        'warning': 'Raw model guidance; SIH ML/downscaling produces localized probabilistic outlooks separately.',
    }

    atomic_write(output_path, payload)
    rebuild_forecast_index(data_dir, generated_at=generated_at)
    return payload


def new_outlook(
    latitude, 
    longitude,
    data_dir: Path = DEFAULT_DATA_DIR,
    locations_path: Path = DEFAULT_LOCATIONS_PATH,
    models_dir: Path = DEFAULT_MODELS_DIR,
    climatology_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Create and persist a missing outlook for a cell.

    If forecast cache is missing, new_forecast() creates it first. Then the
    current ENSO/IOD/MJO state and local forecast are scored and the result is
    persisted in data/outlooks/<cell>.json.
    """
    cell = to_cell(latitude, longitude)
    output_path = data_dir / 'outlooks' / cell.filename
    if output_path.exists():
        try:
            return _read_json(output_path)
        except (OSError, json.JSONDecodeError):
            pass

    forecast_path = data_dir / 'locations' / cell.filename
    if forecast_path.exists():
        try:
            cell_forecast = _read_json(forecast_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise CacheGenerationError(f'Forecast cache is unreadable for {cell.key}.') from exc
    else:
        cell_forecast = new_forecast(
            latitude,
            longitude,
            data_dir=data_dir,
            locations_path=locations_path,
        )

    try:
        climate_state = ClimateIndexProvider().current_state().as_dict()
    except ClimateIndexError as exc:
        raise CacheGenerationError(f'Could not fetch current climate indices: {exc}') from exc

    predictor = OutlookPredictor(models_dir)
    try:
        result = predictor.score_cell(cell_forecast, climate_state, climatology_dir)
    except (KeyError, ValueError, OSError) as exc:
        raise CacheGenerationError(f'Could not calculate outlook for {cell.key}: {exc}') from exc

    result['generated_at'] = datetime.now().astimezone().isoformat()
    result['forecast_generated_at'] = cell_forecast.get('generated_at')

    atomic_write(output_path, result)
    rebuild_outlook_index(data_dir, generated_at=result['generated_at'], climate_state=climate_state)
    return result


def rebuild_outlook_index(
    data_dir: Path = DEFAULT_DATA_DIR,
    generated_at: str | None = None,
    climate_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outlook_dir = data_dir / 'outlooks'
    entries = []
    for path in sorted(outlook_dir.glob('*.json')):
        try:
            payload = _read_json(path)
            key = payload['grid_key']
            entries.append({'key': key, 'file': f'outlooks/{path.name}'})
        except (OSError, json.JSONDecodeError, KeyError):
            continue

    index = {
        'schema_version': 2,
        'generated_at': generated_at or datetime.now().astimezone().isoformat(),
        'forecast_start_date': datetime.now().astimezone().date().isoformat(),
        'location_count': len(entries),
        'climate_state': climate_state,
        'locations': entries,
    }
    atomic_write(data_dir / 'outlooks_index.json', index)
    return index
