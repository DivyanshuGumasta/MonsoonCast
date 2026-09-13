from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from climate_indices import ClimateIndexProvider, ClimateIndexError

from ml_model.predict_outlook import OutlookPredictor, LEAD_BUCKETS


def load_cells_from_index(data_dir: Path) -> list[dict[str, Any]]:
    index = json.loads((data_dir / 'index.json').read_text(encoding='utf-8'))
    return list(index.get('locations', []))


def calculate_outlooks(
    data_dir: Path = Path('data'),
    models_dir: Path = Path('models'),
    climatology_dir: Path | None = None,
) -> bool:
    # Score every cached forecast cell once and persist one outlook JSON per cell.
    try:
        climate_state = ClimateIndexProvider().current_state().as_dict()
    except ClimateIndexError as exc:
        print(f'ERROR: cannot get climate indices: {exc}')
        return False

    index = json.loads((data_dir / 'index.json').read_text(encoding='utf-8'))
    outlook_dir = data_dir / 'outlooks'
    outlook_dir.mkdir(parents=True, exist_ok=True)
    predictor = OutlookPredictor(models_dir)

    cells = index.get('locations', [])
    ok = True

    # Remove stale outlook files for cells no longer present.
    valid_files = {Path(item['file']).name for item in cells}
    for old in outlook_dir.glob('*.json'):
        if old.name not in valid_files:
            old.unlink()

    for i, item in enumerate(cells, 1):
        forecast_path = data_dir / item['file']
        output_path = outlook_dir / forecast_path.name
        print(f'[{i}/{len(cells)}] Scoring outlook {item["key"]} ...')
        try:
            cell_forecast = json.loads(forecast_path.read_text(encoding='utf-8'))
            result = predictor.score_cell(cell_forecast, climate_state, climatology_dir)
            result['generated_at'] = index['generated_at']
            result['forecast_generated_at'] = cell_forecast.get('generated_at')
            result['model_schema'] = {
                'lead_buckets': list(LEAD_BUCKETS.keys()),
                'model_source': result['model_source'],
            }
            tmp = output_path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            tmp.replace(output_path)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            ok = False
            print(f'  ERROR: {exc}')

    # A tiny manifest lets the API validate that outlooks belong to today's forecast run.
    manifest = {
        'schema_version': 1,
        'generated_at': index['generated_at'],
        'forecast_start_date': index.get('forecast_start_date'),
        'location_count': len(cells),
        'climate_state': climate_state,
        'models_dir': str(models_dir),
        'locations': [
            {'key': item['key'], 'file': f'outlooks/{Path(item["file"]).name}'}
            for item in cells
        ],
    }
    tmp = data_dir / 'outlooks_index.json.tmp'
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(data_dir / 'outlooks_index.json')
    print(f'Outlook cache written to {outlook_dir}')
    return ok


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--models-dir', type=Path, default=Path('models'))
    parser.add_argument('--climatology-dir', type=Path, default=None)
    args = parser.parse_args()

    raise SystemExit(0 if calculate_outlooks(args.data_dir, args.models_dir, args.climatology_dir) else 1)
