# Step-by-Step Manual — Getting the Model Trained & Deployed

Note this file was supposed to be for other team members but was documented so well we put it here without any changes, meaning some parts have a bit older things we changed in the endpoints but things are still solid, so we apologize in advance for the informal speech on some places and for grammer mistakes here and there. enjoy creating your own modal!

This is important so everyone could know the flow of MonsoonCast

Total realistic time: a few hours of download waiting + ~20 minutes of actual commands + 3 to 6 hours of building traning table and traning model.
(My Laptop is a BEAST absolutely ripping through my time expectations based on what google said and completing in a small amount of time)
---

## Step 0 — install requirements

Install the extra Python packages:

if you have already ran the install_requirements.sh (which if you are here I hope you did) then move forward here
```bash
pip install xarray netCDF4    # needed only for the CHIRPS extraction step below
```

---

## Step 1 — Decide how many years of CHIRPS data to pull

More years = better-calibrated model, but bigger downloads. Recommendation (based on google, stackoverflow and redit research):

- **Minimum viable (fast):** 10 years, 2015–2024
- **Good (recommended):** 20 years, 2005–2024
- Don't bother going back further than ~1990s; ENSO/IOD/MJO index data quality and monsoon
  variability regime shifts make older data less useful for a demo model anyway.

Each yearly CHIRPS global 0.05° file is ~1-1.5 GB. 20 years ≈ 30 GB. And that's too much disk space
for my happiness, use **10 years (2015–2024)**, which is entirely defensible to state
in our report as "the training window."

## Step 2 — Download CHIRPS

```bash
chmod +x download_chirps.sh
./download_chirps.sh 2015 2024 ./chirps_raw
```

This pulls one NetCDF file per year from `data.chc.ucsb.edu`. It resumes if interrupted (`wget -c`).
Let it run in the background — this is the slow step, budget an evening for it on a normal
connection.
or if you also have unlimited internet then go for it.(I certainly do)

**Sanity check when done:**
```bash
ls -lh chirps_raw/
# should show chirps-v2.0.2015.days_p05.nc ... chirps-v2.0.2024.days_p05.nc
```
the only reason being feeling good that internet part is done, it takes so long even with good internet.

## Step 3 — Extract rainfall at your grid cells

This reads every yearly NetCDF and pulls out the daily rainfall value at each of the cells in
your `locations.json` (using the exact same 0.05° snapping your live API uses, so training and
inference are on identical cells).

I know nither of you two are doing this but just FEEL like you are doing it, get it? ok, moving foreward, the command is below:

```bash
python -m ml_model.extract_chirps_points \
    --chirps-dir chirps_raw \
    --locations locations.json \
    --out data/climate_history/chirps_daily_rain.csv
```

Expect a few minutes per year of data. Output is one CSV with `date, grid_key, rain_mm` — open it
and eyeball a few rows; rain_mm should mostly be 0–40 with occasional spikes in Jun–Sep.
remember there will be a lot and don't accidently edit something like I did.

## Step 4 — Download the historical climate indices

```bash
python -m ml_model.historical_indices --out-dir data/climate_history
```

This pulls the **full** ONI, DMI, and RMM history (decades, small files, seconds to download) —
different from `climate_indices.py`, which only grabs today's value for live inference.

**Sanity check:**
```bash
wc -l data/climate_history/*.csv
# oni_history.csv: hundreds of monthly rows
# dmi_history.csv: hundreds of monthly rows
# rmm_history.csv: many thousands of daily rows (1974-present)
```

## Step 5 — Build the training table (derives onset/break/revival labels)

```bash
python -m ml_model.build_training_table \
    --chirps data/climate_history/chirps_daily_rain.csv \
    --climate-dir data/climate_history \
    --out training_data.csv
```

ok imp part on how this ML works so read carefully as it will clear 90% of ML related doubt:

This is the step that actually gets sciency (wooo): for every day, for every lead bucket (7/14/21/30
days), it computes rainfall features over that forward window and labels the window
onset/active/break/revival/normal based on what really happened in the CHIRPS record. I validated
this exact logic on synthetic data with injected onset/break/revival events and it correctly
identified all of them (see the label-distribution printout it gives you — if `break` and `onset`
show up as a small but non-trivial fraction of rows, ~5–15%, that's a healthy distribution; if
`break` is 0 rows, something's wrong with your CHIRPS extraction meaning back to re-downloading, pain again).

ok break time.

## Step 6 — Train the models

```bash
python -m ml_model.train_model --csv training_data.csv --out-dir models/
```

This trains 4 classifiers (one per lead bucket) and writes them to `models/model_7d.joblib`
through `models/model_30d.joblib`, plus `models/training_report.json` with per-class precision/
recall — **we will put the table from this JSON straight into our SIH report**, judges will ask "how do you
know the model works." and we will show them this. (but where is the ppt is the question)

## Step 7 — Point the backend at the trained models

Nothing to configure — `server_routes_patch.py` already points at `models/` by default. Just
restart the server:

```bash
python3 main.py --locations locations.json --output-dir data     # refresh the raw forecast cache
```
then either:

```bash
python3 server.py --data-dir data --host 0.0.0.0 --port 5000
```

or 

```bash
python3 server.py
```
because other stuff is default

## Step 8 — Verify it's using the trained model, not the fallback

fun part for rohan, try this:

```bash
curl "http://localhost:8000/outlook?latitude=21.13781&longitude=81.82672"
```

Look at the `"model_source"` field in the response — it should say `"trained_classifier"` for each
bucket. If it says `"rule_based_fallback"`, the server can't find your `models/` directory

Then check the other two new endpoints:

```bash
curl "http://localhost:8000/advisory?latitude=21.13781&longitude=81.82672&crops=Rice,Cotton"
curl "http://localhost:8000/risk-map?lead_bucket=7d"
```

and you will tell me what they are.
---

## Endpoints the frontend is calling

| Endpoint | Purpose | Returns |
|---|---|---|
| `GET /forecast?latitude=&longitude=` | (existing) raw 30-day NWP | rain_mm per 3h interval |
| `GET /outlook?latitude=&longitude=` | onset/active/break/revival probabilities | JSON, 4 lead buckets |
| `GET /advisory?latitude=&longitude=&crops=Rice,Cotton` | crop-specific action text | JSON, EN/HI/OR text per crop |
| `GET /risk-map?lead_bucket=7d` | color-coded map data | GeoJSON FeatureCollection |
