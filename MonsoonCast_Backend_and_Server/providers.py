from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
import requests

class ProviderError(RuntimeError):
    pass

class OpenMeteoProvider:
    FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
    SEASONAL_URL = 'https://seasonal-api.open-meteo.com/v1/seasonal'

    def __init__(self, timeout: int = 45) -> None:
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'SIH-Monsoon-Backend/1.0'})
        self.timeout = timeout

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            response = getattr(exc, 'response', None)
            body = response.text[:500].replace('\n', ' ') if response is not None else ''
            raise ProviderError(f'HTTP request failed: {body or str(exc)}') from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError('Open-Meteo returned non-JSON data.') from exc
        if data.get('error'):
            raise ProviderError(data.get('reason', 'Open-Meteo rejected the request.'))
        return data

    @staticmethod
    def _f(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    def _short_forecast(self, lat: float, lon: float) -> list[dict[str, Any]]:
        # Do not mix forecast_days with start_date/end_date. forecast_days=16 is supported here. it's long forecast that can support up to 46 days but with abysmal accuracy. hence the creation of Monsoon Cast. I apologize if that was cringy.
        data = self._get(self.FORECAST_URL, {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'precipitation,precipitation_probability',
            'forecast_days': 16,
            'timezone': 'Asia/Kolkata',
            'timeformat': 'iso8601',
            'precipitation_unit': 'mm',
        })
        hourly = data.get('hourly') or {}
        times, rain, prob = hourly.get('time') or [], hourly.get('precipitation') or [], hourly.get('precipitation_probability') or []
        result = []
        for i, stamp in enumerate(times):
            if i >= len(rain):
                break
            result.append({
                'time': stamp,
                'rain_mm': self._f(rain[i]) or 0.0,
                'rain_probability': (round((self._f(prob[i]) or 0.0) / 100.0, 3) if i < len(prob) and prob[i] is not None else None),
                'source': 'Open-Meteo Forecast API',
            })
        return result

    def _long_forecast(self, lat: float, lon: float) -> list[dict[str, Any]]:
        data = self._get(self.SEASONAL_URL, {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'precipitation',
            'forecast_days': 30,
            'models': 'ecmwf_ec46',
            'timezone': 'Asia/Kolkata',
            'timeformat': 'iso8601',
            'precipitation_unit': 'mm',
        })
        hourly = data.get('hourly') or {}
        times = hourly.get('time') or []
        member_keys = sorted(k for k in hourly if k.startswith('precipitation_member'))
        if not member_keys:
            values = hourly.get('precipitation') or []
            if not values:
                raise ProviderError('EC46 response did not contain precipitation data.')
            return [{'time': t, 'rain_mm': self._f(values[i]) or 0.0, 'rain_probability': None, 'source': 'Open-Meteo ECMWF EC46'} for i, t in enumerate(times) if i < len(values)]
        arrays = [hourly[k] for k in member_keys]
        result = []
        for i, stamp in enumerate(times):
            members = []
            for arr in arrays:
                if i < len(arr):
                    value = self._f(arr[i])
                    if value is not None:
                        members.append(max(0.0, value))
            if not members:
                continue
            mean_mm = sum(members) / len(members)
            wet_probability = sum(m >= 0.1 for m in members) / len(members)
            result.append({'time': stamp, 'rain_mm': round(mean_mm, 2), 'rain_probability': round(wet_probability, 3), 'ensemble_members': len(members), 'source': 'Open-Meteo ECMWF EC46 ensemble'})
        return result

    @staticmethod
    def _dt(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp)

    @classmethod
    def _aggregate_3h(cls, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for p in points:
            dt = cls._dt(p['time'])
            bucket = dt.replace(hour=(dt.hour // 3) * 3, minute=0, second=0, microsecond=0)
            key = bucket.isoformat()
            item = buckets.setdefault(key, {'time': key, 'rain_mm': 0.0, 'probabilities': [], 'sources': set(), 'native_records': 0})
            item['rain_mm'] += float(p.get('rain_mm') or 0.0)
            if p.get('rain_probability') is not None:
                item['probabilities'].append(float(p['rain_probability']))
            item['sources'].add(p['source'])
            item['native_records'] += 1
        out = []
        for key in sorted(buckets):
            item = buckets[key]
            prob = None
            if item['probabilities']:
                no_rain = 1.0
                for p in item['probabilities']:
                    no_rain *= 1.0 - max(0.0, min(1.0, p))
                prob = round(1.0 - no_rain, 3)
            out.append({'time': key, 'rain_mm': round(item['rain_mm'], 2), 'rain_probability': prob, 'source': sorted(item['sources']), 'native_records': item['native_records']})
        return out

    @classmethod
    def _resample_6h_to_3h(cls, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for p in points:
            dt = cls._dt(p['time'])
            half = round(float(p['rain_mm']) / 2.0, 2)
            for offset in (0, 3):
                out.append({'time': (dt + timedelta(hours=offset)).isoformat(timespec='minutes'), 'rain_mm': half, 'rain_probability': p.get('rain_probability'), 'source': [p['source']], 'native_records': 1, 'resampled_from_hours': 6})
        return out

    @staticmethod
    def _days(points: list[dict[str, Any]], start: date) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for p in points:
            groups[p['time'][:10]].append(p)
        result = []
        for offset in range(30):
            d = start + timedelta(days=offset)
            rows = sorted(groups[d.isoformat()], key=lambda x: x['time'])
            rain = [float(r['rain_mm']) for r in rows]
            probs = [r['rain_probability'] for r in rows if r['rain_probability'] is not None]
            result.append({'date': d.isoformat(), 'rain_mm': round(sum(rain), 2), 'max_3h_rain_mm': round(max(rain, default=0.0), 2), 'rain_probability_max': max(probs, default=None), 'forecast': rows})
        return result

    def build_30_day_forecast(self, lat: float, lon: float, start: date) -> dict[str, Any]:
        short = self._short_forecast(lat, lon)
        long = self._long_forecast(lat, lon)
        cutoff = start + timedelta(days=16)
        short3 = self._aggregate_3h([p for p in short if p['time'][:10] < cutoff.isoformat()])
        long3 = self._resample_6h_to_3h([p for p in long if p['time'][:10] >= cutoff.isoformat()])
        end = start + timedelta(days=29)
        merged = sorted(short3 + long3, key=lambda x: x['time'])
        merged = [p for p in merged if start.isoformat() <= p['time'][:10] <= end.isoformat()]
        if not merged:
            raise ProviderError('No forecast records returned.')
        return {
            'forecast_start_date': start.isoformat(),
            'forecast_end_date': end.isoformat(),
            'source': ['Open-Meteo Forecast API', 'Open-Meteo ECMWF EC46'],
            'source_intervals': {'days_1_to_16': 'hourly source aggregated to 3-hour display intervals', 'days_17_to_30': '6-hour EC46 source split into 3-hour display intervals'},
            'days': self._days(merged, start),
        }
