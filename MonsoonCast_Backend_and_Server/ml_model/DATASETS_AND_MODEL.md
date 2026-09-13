# Datasets & Modeling Plan — SIH Monsoon Advisory

NOTE: This Readme was made during starting stage of planning and creation of Models so it is not up to date, but this readme is correct about modals and dataset because they were completed earliest. but for other info you should go to the README.md at the MonsoonCast_Backend_and_server directory.

## 1. Why the current pipeline isn't enough

(this part is talking about the time when the entire pipeline was created to atleast see if everything is working together so everyone could start work together, that time model was not created and the direct forecast was being shown to the frontend, hence the titel. and at the end of this file the model creation was completed.)

`providers.py` gives **numerical model output** (Open-Meteo Forecast API for days 1–16,
ECMWF EC46 for days 17–30). That is weather, not monsoon behavior (big difference). The problem statement asks for:

- probability of **onset** (has the monsoon "arrived" at this block yet)
- probability of a **break/dry spell** (≥N consecutive dry days ahead)
- probability of a **revival / active spell** (heavy rain returning)
- all of this **downscaled using global teleconnections** (ENSO, IOD, MJO)

NWP models like EC46 already encode teleconnection effects implicitly, but not in a form a farmer
or an expert-system can act on. You need a **second-stage model** that sits on top of the raw
forecast and reclassifies it into onset/break/revival probabilities, calibrated against how local
rainfall has historically behaved when ENSO/IOD/MJO were in similar states.

before going to 2 know the reason this model needs to exist above please rohan

## 2. Datasets to use

| Data | Purpose | Source | Format |
|---|---|---|---|
| **IMD Gridded Rainfall (0.25°), 1901–present** | Ground truth for training: historical daily rainfall per grid cell → derive actual onset/break dates | IMD Pune / IITM (`https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html`) | NetCDF |
| **NOAA ONI (Oceanic Niño Index)** | ENSO state, monthly, 1950–present | NOAA CPC (`https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php`) | plain text table |
| **DMI (Dipole Mode Index) for IOD** | IOD state, daily/weekly | NOAA PSL (`https://psl.noaa.gov/gcos_wgsp/Timeseries/DMI/`) | plain text table |
| **RMM Index (MJO)** | MJO phase (1–8) and amplitude, daily | BOM Australia (`http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt`) | plain text table |
| **IMD Monsoon Onset dates (subdivision-wise)** | Labels for onset-date model validation | IMD press releases / archived onset bulletins | manual/CSV |
| **Your existing Open-Meteo cells** | Real-time short + medium range forecast used as model *input features*, not ground truth | Already in `providers.py` | JSON (already built) |
| **LGD Block/Panchayat boundaries** | To aggregate/display at block & panchayat granularity | Local Government Directory (`https://lgdirectory.gov.in`) | shapefile/GeoJSON |

For the hackathon, we do **not** need to download 100 years of NetCDF (that is too much and too big like 500gb big). MY SIH approach:

- Pull **30–40 years** of IMD gridded rainfall for the districts we will be demoing (Chhattisgarh
   matching the `locations.json`).
- Pull the **full ONI/DMI/RMM time series** (small text files, decades of data, trivial to fetch).
- Derive **onset date, break spells (≥7 dry days in monsoon season), and revival events** per
  grid cell per year from the rainfall data using a standard onset definition (e.g. IMD's
  operational definition, or Pai et al. 2015 sub-division onset criteria). (as said 2015 to current is better (around 10 years))
- Train a model that says: *"given the current ENSO/IOD/MJO state + the next 30 days of raw NWP
  rainfall, Idea goes like: what's the probability this cell is in onset/active/break/revival over the next 1–4
  weeks?"*

If I didn't get IMD data before the deadline, CHIRPS (`https://data.chc.ucsb.edu/products/CHIRPS-2.0/`)
is a public, no-registration daily rainfall dataset (0.05°) that works as a substitute.

ok so change of plans, I didn't get IMD data I was expecting, I need to fallback with CHIRPS after consulting with harsh

## 3. Model architecture

```
                     ┌────────────────────────────┐
                     │  Global indices (features) │
                     │  ONI, DMI, RMM phase+amp   │
                     └─────────────┬──────────────┘
                                   │
┌──────────────────────┐           │           ┌───────────────────────────┐
│ Local NWP features   │           │           │ Historical climatology    │
│ (from your Open-Meteo│───────────┼──────────>│ (30-yr mean/std rainfall  │
│  30-day cache)       │           │           │  for this cell, this doy) │
└──────────────────────┘           │           └─────────────┬─────────────┘
                                   │                         │
                     ┌──────────────────────────────┐        │
                     │  Gradient-boosted classifier │        │
                     │  (XGBoost / RandomForest)    │        │
                     │  one model per lead bucket:  │<───────┼
                     │  7d / 14d / 21d / 30d        │
                     └─────────────┬────────────────┘
                                   │
                     P(onset) P(active) P(break) P(revival)
                                   │
                                   │
                    Rule-based expert system (advisory_engine.py)
                                   │
                                   │
                    Farmer-facing SMS/WhatsApp/web text
```

Why gradient boosting and not a deep net: MonsoonCast have a handful of features (index values + a few
NWP-derived aggregates) and limited training rows per cell (tens of years × ~150 monsoon days).
Tree ensembles are the standard, defensible, explainable choice here — and "explainable" matters
for a judging panel and for an agronomic advisory we don't want to be a black box.

for rohan: In science, computing, and engineering, a black box is a system which can be viewed in terms of its inputs and outputs, without any knowledge of its internal workings

our answer could be why in a structured way would be kinda like:
“We chose Gradient Boosting because MonsoonCast is a tabular, probabilistic classification problem. Our model combines rainfall features with climate indicators such as ENSO, IOD and MJO, and the relationships between these variables are nonlinear. Gradient Boosting can learn those nonlinear interactions effectively without requiring the huge datasets or complexity of a deep neural network. Most importantly, it provides class probabilities, so instead of saying a location simply has a ‘break’ or ‘normal’ condition, we can produce probabilities for all five monsoon states. Those probabilities are then passed to our explainable advisory engine to generate crop-specific recommendations.”

And if they ask “Why not deep learning?”, answer will be:

“Because our inputs are structured tabular features rather than raw images or very large unstructured datasets. Gradient-boosted trees are a better fit for this type of data and keep the system smaller, faster and easier to interpret.”

(remember to remind me to remove this after you guys are done reading this, or remove it yourself and we will tell those two tomorrow.)

This is genuinely a **hybrid model**: physical NWP (Open-Meteo/ECMWF) provides the raw
atmospheric signal, and the ML layer downscales/recalibrates it using teleconnection state —
which is what the problem statement asks for (our conclusion but might be different).

## 4. What is built by now

- `climate_indices.py` — fetches live ONI/DMI/RMM index values
- `ml_model/features.py` — turns the cached Open-Meteo cell JSON + climate indices into a feature vector
- `ml_model/train_model.py` — trains the classifier from historical CSVs (input the IMD/CHIRPS-derived training table — schema documented in the file)
- `ml_model/predict_outlook.py` — loads the trained model, scores the current cached cells
- `advisory_engine.py` — expert-system rules: probability → crop-specific action text, in English/Hindi/Odia
- `risk_map.py` — builds a color-coded GeoJSON risk map at block level
- `notification_gateway.py` — Twilio SMS/WhatsApp dispatcher #unused
- server route additions in `server_routes_patch.py` — wires `/outlook`, `/advisory`, `/risk-map` into the existing FastAPI app
