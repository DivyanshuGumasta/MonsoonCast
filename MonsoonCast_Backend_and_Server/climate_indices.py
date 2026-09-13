from __future__ import annotations
import json, re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests
ONI_URL='https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/detrend.nino34.ascii.txt'
DMI_URL='https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data'
RMM_URL='http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt'
class ClimateIndexError(RuntimeError): pass
@dataclass
class ClimateState:
    fetched_at:str; oni:float|None; oni_phase:str; dmi:float|None; iod_phase:str; mjo_phase:int|None; mjo_amplitude:float|None; mjo_active:bool
    def as_dict(self)->dict[str,Any]: return asdict(self)
def _oni_phase(oni):
    if oni is None:return 'unknown'
    if oni>=1.5:return 'strong_el_nino'
    if oni>=0.5:return 'weak_moderate_el_nino'
    if oni<=-1.5:return 'strong_la_nina'
    if oni<=-0.5:return 'weak_moderate_la_nina'
    return 'neutral'
def _iod_phase(dmi):
    if dmi is None:return 'unknown'
    if dmi>=0.4:return 'positive_iod'
    if dmi<=-0.4:return 'negative_iod'
    return 'neutral'
class ClimateIndexProvider:
    def __init__(self, cache_path=Path('data/climate_indices_cache.json'), timeout=30):
        self.cache_path=cache_path; self.timeout=timeout; self.session=requests.Session(); self.session.headers.update({'User-Agent':'SIH-Monsoon-Backend/1.0'})
    def _fetch_text(self,url):
        resp=self.session.get(url,timeout=self.timeout); resp.raise_for_status(); return resp.text
    def _latest_oni(self):
        rows=[ln.split() for ln in self._fetch_text(ONI_URL).strip().splitlines()[1:] if ln.strip()]
        try:return float(rows[-1][-1]) if rows else None
        except (ValueError,IndexError):return None
    def _latest_dmi(self):
        lines=[ln.split() for ln in self._fetch_text(DMI_URL).strip().splitlines() if ln.strip()]
        rows=[r for r in lines if len(r)==13 and re.match(r'^\d{4}$',r[0])]
        for row in reversed(rows):
            valid=[float(v) for v in row[1:] if float(v)>-999]
            if valid:return valid[-1]
        return None
    def _latest_rmm(self):
        lines=[ln.strip() for ln in self._fetch_text(RMM_URL).strip().splitlines() if ln.strip()]
        data=[ln for ln in lines if re.match(r'^\d{4}\s',ln)]
        if not data:return None,None
        last=data[-1].split(',') if ',' in data[-1] else data[-1].split()
        try:return int(float(last[5])),float(last[6])
        except (ValueError,IndexError):return None,None
    def current_state(self,allow_cache_fallback=True):
        try:
            oni=self._latest_oni(); dmi=self._latest_dmi(); phase,amp=self._latest_rmm()
            state=ClimateState(datetime.now(timezone.utc).isoformat(),oni,_oni_phase(oni),dmi,_iod_phase(dmi),phase,amp,bool(amp and amp>=1.0))
            self.cache_path.parent.mkdir(parents=True,exist_ok=True); self.cache_path.write_text(json.dumps(state.as_dict()),encoding='utf-8'); return state
        except requests.RequestException as exc:
            if allow_cache_fallback and self.cache_path.exists():
                cached=json.loads(self.cache_path.read_text(encoding='utf-8')); cached.pop('stale',None); return ClimateState(**cached)
            raise ClimateIndexError(f'Could not fetch climate indices and no cache available: {exc}') from exc
