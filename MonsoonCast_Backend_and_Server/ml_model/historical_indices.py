"""
ml_model/historical_indices.py

Downloads the FULL historical time series of ONI, DMI, and RMM (same source
URLs as climate_indices.py, which only reads the latest row for live data(current condition), 
while this .py uses them to get historical data). Training needs
decades of history to align against decades of CHIRPS rainfall.

Output: three tidy CSVs in --out-dir:
    oni_history.csv   -> year, month, oni
    dmi_history.csv   -> year, month, dmi
    rmm_history.csv   -> date, rmm_phase, rmm_amplitude   (daily)

Run this ONCE, on a machine with internet i.e. laptop(like me), desktop, etc.

Usage:
    python -m ml_model.historical_indices --out-dir data/climate_history
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import requests

# NOTE: the "origin." subdomain is a CDN-origin host that is not resolvable from every
# network/ISP (it 404s or NXDOMAINs for some users even though it works for others depending on
# DNS/routing). www.cpc.ncep.noaa.gov mirrors the identical file and resolves everywhere.
# so first go to www.cpc.ncep.noaa.gov from any device on that network that you intend to use and if it loades this will work on program as well.
ONI_URL = 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/detrend.nino34.ascii.txt'
DMI_URL = 'https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data'
RMM_URL = 'http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt'


SESSION = requests.Session()
# BOM's server has been reported to behave differently (block/redirect) for the default
# `python-requests` User-Agent on this exact file, per multiple third-party scripts that fetch
# it -- a browser-like UA avoids that silently-empty-response failure mode.
# below is what I used and you can understand what to do from just reading it and change it accordingly. (as it is not sensitive info)
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) SIH-Monsoon-Backend/1.0'})


def fetch_oni_history() -> pd.DataFrame:
    """
    ONI file columns are: YR MON TOTAL ClimAdjust ANOM  (5 columns, whitespace separated).
    Take column 0 as year, column 1 as month, and the LAST column as ANOM -- using the last
    column rather than a fixed index is robust if NOAA ever adds/removes a column, which they
    have done before (the ClimAdjust column was added after the original 4-column format).
    """
    resp = SESSION.get(ONI_URL, timeout=30)
    resp.raise_for_status()
    text = resp.text
    rows = [ln.split() for ln in text.strip().splitlines()[1:] if ln.strip()]
    records = []
    for r in rows:
        if len(r) < 4:
            continue
        try:
            year, month, anom = int(r[0]), int(r[1]), float(r[-1])
        except ValueError:
            continue
        if 1 <= month <= 12:
            records.append({'year': year, 'month': month, 'oni': anom})
    df = pd.DataFrame(records).dropna()
    if df.empty:
        raise RuntimeError(f'Parsed 0 ONI rows from {ONI_URL} -- response may not be the expected file. '
                            f'First 200 chars of response: {text[:200]!r}')
    return df


def fetch_dmi_history() -> pd.DataFrame:
    """PSL format: YEAR M1 M2 ... M12 rows, -9999 = missing."""
    resp = SESSION.get(DMI_URL, timeout=30)
    resp.raise_for_status()
    text = resp.text
    records = []
    for line in text.strip().splitlines():
        parts = line.split()
        if len(parts) != 13 or not re.match(r'^\d{4}$', parts[0]):
            continue
        year = int(parts[0])
        for month, val in enumerate(parts[1:], start=1):
            try:
                v = float(val)
            except ValueError:
                continue
            if v > -999:
                records.append({'year': year, 'month': month, 'dmi': v})
    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError(f'Parsed 0 DMI rows from {DMI_URL} -- response may not be the expected file. '
                            f'First 200 chars of response: {text[:200]!r}')
    return df


def fetch_rmm_history() -> pd.DataFrame:
    """BOM format: year month day RMM1 RMM2 phase amplitude ... (whitespace separated, 2 header lines)."""
    resp = SESSION.get(RMM_URL, timeout=30)
    resp.raise_for_status()
    text = resp.text
    records = []
    for line in text.strip().splitlines():
        if not re.match(r'^\s*\d{4}\s', line):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            phase = int(float(parts[5]))
            amplitude = float(parts[6])
        except ValueError:
            continue
        try:
            date = pd.Timestamp(year=year, month=month, day=day)
        except ValueError:
            continue
        records.append({'date': date, 'rmm_phase': phase, 'rmm_amplitude': amplitude})
    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError(f'Parsed 0 RMM rows from {RMM_URL} -- response may not be the expected file '
                            f'(possible bot-blocking or format change). First 300 chars of response: {text[:300]!r}')
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', type=Path, default=Path('data/climate_history'))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    oni = fetch_oni_history()
    oni.to_csv(args.out_dir / 'oni_history.csv', index=False)
    print(f'ONI: {len(oni)} monthly rows -> {args.out_dir / "oni_history.csv"}')

    dmi = fetch_dmi_history()
    dmi.to_csv(args.out_dir / 'dmi_history.csv', index=False)
    print(f'DMI: {len(dmi)} monthly rows -> {args.out_dir / "dmi_history.csv"}')

    rmm = fetch_rmm_history()
    rmm.to_csv(args.out_dir / 'rmm_history.csv', index=False)
    print(f'RMM: {len(rmm)} daily rows -> {args.out_dir / "rmm_history.csv"}')


if __name__ == '__main__':
    main()
