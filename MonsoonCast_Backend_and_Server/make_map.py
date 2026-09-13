from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from risk_map import build_cell_risk_geojson

LEAD_BUCKETS = ('7d', '14d', '21d', '30d')


def load_cached_outlooks(data_dir: Path) -> list[dict[str, Any]]:
    index_path = data_dir / 'outlooks_index.json'
    if not index_path.exists():
        raise FileNotFoundError('outlooks_index.json does not exist; run calculate_outlook.py first.')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    out = []
    for item in index.get('locations', []):
        path = data_dir / item['file']
        if not path.exists():
            continue
        out.append(json.loads(path.read_text(encoding='utf-8')))
    return out


def make_map(data_dir: Path = Path('data')) -> bool:
    """Build four static GeoJSON files from already-cached ML outlooks."""
    outlooks = load_cached_outlooks(data_dir)
    map_dir = data_dir / 'map'
    map_dir.mkdir(parents=True, exist_ok=True)

    ok = True
    for bucket in LEAD_BUCKETS:
        geojson = build_cell_risk_geojson(outlooks, bucket)
        geojson['generated_at'] = json.loads((data_dir / 'outlooks_index.json').read_text(encoding='utf-8'))['generated_at']
        output = map_dir / f'risk_{bucket}.geojson'
        tmp = output.with_suffix('.geojson.tmp')
        try:
            tmp.write_text(json.dumps(geojson, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            tmp.replace(output)
            print(f'Map cache written: {output} ({len(geojson["features"])} cells)')
        except OSError as exc:
            ok = False
            print(f'ERROR writing {output}: {exc}')

    manifest = {
        'schema_version': 1,
        'generated_at': json.loads((data_dir / 'outlooks_index.json').read_text(encoding='utf-8'))['generated_at'],
        'files': {bucket: f'map/risk_{bucket}.geojson' for bucket in LEAD_BUCKETS},
    }
    tmp = data_dir / 'map_index.json.tmp'
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(data_dir / 'map_index.json')
    return ok


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    raise SystemExit(0 if make_map(args.data_dir) else 1)
