# SIH Monsoon Backend — nightly precomputation + daytime cache API

## Architecture

```text
02:00–03:00 daily

locations.json
   ↓
main.py
   ↓
0.05° snapping + duplicate removal
   ↓
real weather cache: one JSON per cell
   ↓
calculate_outlook.py
   ↓
one ML outlook JSON per cell
   ↓
make_map.py
   ↓
four static risk-map GeoJSON files

DAYTIME
Cordova → FastAPI → direct file lookup → JSON
```

The expensive work is done once per day. Farmer requests do not calculate ML models or build maps.

## Output layout

```text
data/
├── index.json
├── locations/
│   ├── n21.15_e81.85.json
│   └── ...
├── outlooks_index.json
├── outlooks/
│   ├── n21.15_e81.85.json
│   └── ...
└── map/
    ├── risk_7d.geojson
    ├── risk_14d.geojson
    ├── risk_21d.geojson
    └── risk_30d.geojson
```

There is deliberately **one file per grid cell**. We do not send all ~420 cells to the farmer's phone.

## Coordinate resolution

The API snaps every GPS coordinate to the nearest 0.05° cell.

```text
21.13781, 81.82672
        ↓
21.15, 81.85
        ↓
data/locations/n21.15_e81.85.json
```

Nearby requests that land in the same cell share one forecast and one outlook.

## Complete daily refresh

```bash
./refresh_daily.sh
```
which just runs 
```bash
python3 main.py --locations locations.json --output-dir data
```
on the venv and the `main.py` runs the complete chain automatically.

## Individual stages

this is what main.py is doing automatically:

```text
1. fetch 30-day raw forecast
2. calculate_outlook.py
3. make_map.py
4. messages.py
```

## Start API

```bash
./install_requirements.sh
./refresh_daily.sh
./start_server.sh
```

Whatsapp integraton will require you to follow steps in WHATSAPP_INTEGRATION.md in wa-bridge directory. (you can still run the server even if the whatsapp integration is not done but you won't be able to use (message me) feature of the application.)

### Daytime endpoints

```text
GET /forecast?latitude=&longitude=
GET /outlook?latitude=&longitude=
GET /advisory?latitude=&longitude=&crops=Rice,Cotton
GET /risk-map?lead_bucket=7d
GET /meta                                             # loader
GET /health                                           # debug
```

`/forecast` and `/outlook` construct the deterministic cell filename directly. They do not scan the 420 cell files. `/risk-map` opens an already-built GeoJSON file.

The index is metadata rather than a routing database for individual cell files.

## Why this matters for Cordova

The intended mobile behavior is:

```text
App opens
  ↓
GPS → /forecast + /outlook + /advisory as needed
  ↓
returnes cached JSON
  ↓
screens work from returned json
  ↓
available in less than a second for viewing
```

The app does not need to download the entire country's 400+ cell forecast package. (or more which will be added later)

## ML integration

`calculate_outlook.py` calls the existing `ml_model.predict_outlook.OutlookPredictor` once per cached cell. The four lead buckets are 7d/14d/21d/30d. The cached result is then reused by the API.

`make_map.py` reads those cached outlooks and calls the existing `risk_map.build_cell_risk_geojson()` once per lead bucket. Therefore `/risk-map` no longer runs model inference for all cells during a farmer request.
thats why is faster now

`climate_indices.py` is fetched during the nightly outlook job, so normal daytime requests do not depend on live NOAA/BOM connectivity.

## Replication

To recreate the models and verify their validity, read the STEP_BY_STEP.md Readme in ml_model directory. please note that it might take a lot of time (could be more than 6 hours if your device doesn't have a dedicated GPU)

## Journey

To understand the thought process we had during the creation of this modal and architecture of the server and application please read the DATASETS_AND_MODEL.md in ml_model directory.