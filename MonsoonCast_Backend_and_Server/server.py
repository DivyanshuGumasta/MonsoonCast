"""
the only once that are actually used are:
GET /forecast
GET /outlook
GET /advisory
GET /risk-map
GET /health   technical monitoring
GET /meta     technical/diagnostic metadata
"""
from __future__ import annotations
import sqlite3

import argparse
import json
from pathlib import Path
from typing import Any
import time
import random
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import GRID_STEP, to_cell
from cache_helpers import new_forecast, new_outlook
from advisory_engine import generate_advisories
from notification_gateway import NotificationGateway

app = FastAPI(title='SIH Monsoon Forecast API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False,
                   allow_methods=['GET', 'HEAD', 'POST', 'OPTIONS'], allow_headers=['*'])

DATA_DIR = Path('data')
INDEX_PATH = DATA_DIR / 'index.json'
OUTLOOK_INDEX_PATH = DATA_DIR / 'outlooks_index.json'

# Loaded once when the server starts / first request.
# index on every farmer request.
CELL_FILES: dict[str, str] = {}
OUTLOOK_FILES: dict[str, str] = {}
MAP_FILES: dict[str, str] = {}

def init_db():
    conn = sqlite3.connect('subscribers.db')
    # Primary subscriber table
    conn.execute('''CREATE TABLE IF NOT EXISTS subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE, 
                    platform INTEGER, 
                    crops TEXT,
                    language TEXT, 
                    grid_key TEXT)''')
    # OTP Table (Keyed by phone number)
    conn.execute('''CREATE TABLE IF NOT EXISTS otp_tokens (
                    phone TEXT PRIMARY KEY,
                    otp TEXT,
                    expires_at INTEGER)''')
    conn.commit()
    conn.close()

class OTPRequest(BaseModel):
    phone: str

class SubscribeRequest(BaseModel):
    phone: str
    otp: str
    platform: int
    crops: list[str]
    language: str
    latitude: float
    longitude: float

@app.post('/request-otp')
def request_otp(req: OTPRequest):
    clean_phone = re.sub(r'\D', '', req.phone)
    if len(clean_phone) != 10:
        raise HTTPException(status_code=400, detail="Phone number must be exactly 10 digits.")

    # Generate 6-digit OTP code and set 5-minute expiry
    otp = f"{random.randint(100000, 999999)}"
    expires_at = int(time.time()) + 300  

    # Thread-safe database update per phone number
    conn = sqlite3.connect('subscribers.db')
    try:
        conn.execute("""
            INSERT INTO otp_tokens (phone, otp, expires_at) 
            VALUES (?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET otp=excluded.otp, expires_at=excluded.expires_at
        """, (clean_phone, otp, expires_at))
        conn.commit()
    finally:
        conn.close()

    # Dispatch OTP via whatsapp Gate (sms gate works but this is better for testing because otherwise I would need to also have my phone as a server on top of already using laptop as a server)
    try:
        gw = NotificationGateway()
        gw.send_whatsapp(clean_phone, f"Your verification code is: {otp}. Valid for 5 minutes.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to deliver OTP SMS: {str(exc)}")

    return {"status": "success", "message": "OTP dispatched."}

@app.post('/subscribe')
def subscribe(req: SubscribeRequest):
    clean_phone = re.sub(r'\D', '', req.phone)
    if len(clean_phone) != 10:
        raise HTTPException(status_code=400, detail="Phone number must be exactly 10 digits.")

    conn = sqlite3.connect('subscribers.db')
    try:
        # 1. Verify OTP validity
        row = conn.execute("SELECT otp, expires_at FROM otp_tokens WHERE phone = ?", (clean_phone,)).fetchone()
        
        if not row:
            raise HTTPException(status_code=400, detail="No OTP requested for this phone number.")
        
        saved_otp, expires_at = row
        
        if int(time.time()) > expires_at:
            raise HTTPException(status_code=400, detail="OTP code has expired. Please request a new one.")
        
        if req.otp.strip() != saved_otp:
            raise HTTPException(status_code=400, detail="Invalid OTP code.")

        # 2. OTP valid -> Clear record so it cannot be reused
        conn.execute("DELETE FROM otp_tokens WHERE phone = ?", (clean_phone,))

        # 3. Create or update subscriber profile
        cell = to_cell(req.latitude, req.longitude)
        crops_json = json.dumps(req.crops)

        existing = conn.execute("SELECT id FROM subscribers WHERE phone = ?", (clean_phone,)).fetchone()

        if existing:
            conn.execute("""
                UPDATE subscribers 
                SET platform = ?, crops = ?, language = ?, grid_key = ?
                WHERE phone = ?
            """, (req.platform, crops_json, req.language, cell.key, clean_phone))
            status_msg = "updated"
        else:
            conn.execute("""
                INSERT INTO subscribers (phone, platform, crops, language, grid_key) 
                VALUES (?, ?, ?, ?, ?)
            """, (clean_phone, req.platform, crops_json, req.language, cell.key))
            status_msg = "subscribed"

        conn.commit()
    finally:
        conn.close()

    return {"status": "success", "action": status_msg, "grid_key": cell.key}

class LocationRequest(BaseModel):
    latitude: float
    longitude: float


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise HTTPException(503, f'Cache file missing: {path}') from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(503, f'Cache file is invalid: {path}') from exc


def _load_manifests() -> None:
    global CELL_FILES, OUTLOOK_FILES, MAP_FILES
    if not INDEX_PATH.exists():
        raise HTTPException(503, 'Forecast index is not available yet.')
    index = _read_json(INDEX_PATH)
    CELL_FILES = {item['key']: item['file'] for item in index.get('locations', [])}

    if OUTLOOK_INDEX_PATH.exists():
        oi = _read_json(OUTLOOK_INDEX_PATH)
        OUTLOOK_FILES = {item['key']: item['file'] for item in oi.get('locations', [])}
    else:
        OUTLOOK_FILES = {}

    MAP_FILES = {
        bucket: f'map/risk_{bucket}.geojson'
        for bucket in ('7d', '14d', '21d', '30d')
        if (DATA_DIR / 'map' / f'risk_{bucket}.geojson').exists()
    }


def _ensure_loaded() -> None:
    if not CELL_FILES:
        _load_manifests()


def forecast_file(latitude, longitude) -> Path:
    cell = to_cell(latitude, longitude)
    path = DATA_DIR / 'locations' / cell.filename
    if not path.exists():
        return new_forecast(latitude,longitude)
    return path


def outlook_file(latitude, longitude) -> Path:
    cell = to_cell(latitude, longitude)
    path = DATA_DIR / 'outlooks' / cell.filename
    if not path.exists():
        return new_outlook(latitude,longitude)
    return path

@app.get('/health')
def health() -> dict:
    _ensure_loaded()
    return {'ok': bool(CELL_FILES), 'cells': len(CELL_FILES), 'outlooks': len(OUTLOOK_FILES), 'map_buckets': len(MAP_FILES)}

@app.get('/meta')
def meta() -> dict:
    _ensure_loaded()
    return _read_json(INDEX_PATH)

@app.get('/forecast')
def get_forecast(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180)) -> dict:
    result = forecast_file(latitude, longitude)

    if isinstance(result, dict):
        return result

    return _read_json(result)

@app.get('/forecast/{latitude}/{longitude}')
def get_forecast_path(latitude: float, longitude: float) -> dict:
    return get_forecast(latitude, longitude)

@app.get('/outlook')
def get_outlook(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180)) -> dict:
    result = outlook_file(latitude, longitude)

    if isinstance(result, dict):
        return result

    return _read_json(result)

@app.get('/advisory')
def get_advisory(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180),
                crops: str = Query('Rice,Cotton,Soybean')) -> dict:
    outlook_response = get_outlook(latitude, longitude)
    crop_list = [c.strip() for c in crops.split(',') if c.strip()]
    return {
        'grid_key': outlook_response['grid_key'],
        'climate_state': outlook_response['climate_state'],
        'advisories': generate_advisories(outlook_response['outlook'], crop_list),
    }

@app.get('/risk-map')
def get_risk_map(lead_bucket: str = Query('7d', pattern='^(7d|14d|21d|30d)$')) -> dict:
    _ensure_loaded()
    rel = MAP_FILES.get(lead_bucket)
    if not rel:
        raise HTTPException(404, f'No cached risk map for {lead_bucket}; run make_map.py first.')
    return _read_json(DATA_DIR / rel)

@app.post('/resolve-location')
def resolve_location(request: LocationRequest) -> dict:
    cell = to_cell(request.latitude, request.longitude)
    _ensure_loaded()
    return {
        'requested': {'latitude': request.latitude, 'longitude': request.longitude},
        'grid': {'key': cell.key, 'latitude': cell.latitude, 'longitude': cell.longitude, 'grid_step_degrees': float(GRID_STEP)},
        'forecast_available': cell.key in CELL_FILES,
        'outlook_available': cell.key in OUTLOOK_FILES,
    }

def reload_cache_manifests() -> None:
    """Call from an admin/refresh process after replacing daily cache files."""
    global CELL_FILES, OUTLOOK_FILES, MAP_FILES
    CELL_FILES = {}
    OUTLOOK_FILES = {}
    MAP_FILES = {}
    _load_manifests()

def main() -> None:
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    init_db()
    global DATA_DIR, INDEX_PATH, OUTLOOK_INDEX_PATH
    DATA_DIR = args.data_dir
    INDEX_PATH = DATA_DIR / 'index.json'
    OUTLOOK_INDEX_PATH = DATA_DIR / 'outlooks_index.json'
    _load_manifests()
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == '__main__':
    main()
