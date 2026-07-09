# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
#   kernelspec:
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Sandbox: TWDB GWDB bulk-file exploration
#
# TWDB's Groundwater Database (GWDB) ArcGIS FeatureServer
# (`Public/TWDB_Groundwater_database/FeatureServer/0`) only exposes a well **inventory** layer
# (location, aquifer, flags for whether level/quality data exist) — no time-series query endpoint.
# The actual water-level and water-quality measurements are only published as a **nightly full-state
# bulk file**: <https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip> (~81 MB zipped, ~1.7 GB
# unzipped). This notebook prototypes: (1) paginated ArcGIS bbox queries for well inventory, (2)
# downloading + caching the bulk zip, (3) extracting only the needed member files without
# unpacking the whole archive, (4) filtering the huge `WaterQualityMajor.txt` (~1 GB uncompressed)
# by `StateWellNumber` without loading it entirely into memory, and (5) confirming TWDB's water-
# quality `ParameterCode` reuses USGS-style codes (so `classify_parameter(parameter_code=...)`
# works unchanged). Once proven here, the approach is ported into `5_twdb_waterdata.py`.

# %% [markdown]
# ## Step 1 — Well inventory via the ArcGIS FeatureServer (paginated)
#
# The server's `maxRecordCount` is 1,000; a South-Texas-scale bbox returns ~3,300 wells, so
# pagination via `resultOffset` is required to get them all.

# %%
import sys
from pathlib import Path

# Sandbox scripts live one level deeper than the numbered notebooks (notebooks/sandbox/ vs.
# notebooks/), so _helpers isn't a cwd-sibling here the way it is when a numbered notebook is
# executed (its kernel cwd is notebooks/, right alongside notebooks/_helpers/). Add notebooks/
# to sys.path so `from _helpers import ...` resolves the same way it does everywhere else.
sys.path.insert(0, str(Path.cwd().parent))

import geopandas as gpd
import geoviews as gv
import requests

from _helpers import init_session

# init_session() calls set_plot_defaults(), which requires the Bokeh extension to already be
# loaded (see notebooks/_helpers/viz.py) — same ordering the numbered notebooks use.
gv.extension("bokeh")
S = init_session()

GWDB_FEATURESERVER_URL = (
    "https://services.twdb.texas.gov/arcgis/rest/services/Public/"
    "TWDB_Groundwater_database/FeatureServer/0/query"
)
GWDB_PAGE_SIZE = 1000

bbox = [-98.5, 25.8, -97.0, 27.5]  # rough box around the 3 study HUC-8s

features, offset = [], 0
while True:
    params = {
        "geometry": ",".join(str(v) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "geojson",
        "resultRecordCount": GWDB_PAGE_SIZE,
        "resultOffset": offset,
    }
    page = requests.get(GWDB_FEATURESERVER_URL, params=params, timeout=60).json()
    page_features = page.get("features", [])
    features.extend(page_features)
    print(f"offset {offset}: +{len(page_features)} features")
    if len(page_features) < GWDB_PAGE_SIZE:
        break
    offset += GWDB_PAGE_SIZE

wells = gpd.GeoDataFrame.from_features(features, crs=4326)
print(f"{len(wells)} wells total in bbox")
wells[["StateWellNumber", "WaterLevelObservationType", "WaterQualityAvailable"]].head()

# %% [markdown]
# ## Step 2 — Download and cache the bulk zip

# %%
import time
from pathlib import Path

GWDB_BULK_URL = "https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip"
zip_path = S.repo_root / "data_temp" / "gwdb_download.zip"


def fetch_gwdb_zip(dest: Path, url: str = GWDB_BULK_URL, max_age_days: int = 7) -> Path:
    if dest.exists() and (time.time() - dest.stat().st_mtime) < max_age_days * 86400:
        print(f"using cached {dest} (< {max_age_days} days old)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url} -> {dest} ...")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


zip_path = fetch_gwdb_zip(zip_path)
print(zip_path, zip_path.stat().st_size, "bytes")

# %% [markdown]
# ## Step 3 — Inspect member files (without extracting the whole archive)

# %%
import zipfile

with zipfile.ZipFile(zip_path) as z:
    for info in z.infolist():
        if "WaterLevels" in info.filename or "WaterQuality" in info.filename or "WellMain" in info.filename:
            print(f"{info.filename}\t{info.file_size:,} bytes")

# %% [markdown]
# ## Step 4 — Chunked filter by StateWellNumber (proves the memory-bounded approach)
#
# `WaterQualityMajor.txt` alone is ~1 GB uncompressed — read it in chunks and keep only rows for
# our bbox's wells, never materializing the whole file as a DataFrame.

# %%
import pandas as pd

well_ids = set(wells["StateWellNumber"].dropna())
print(f"{len(well_ids)} candidate well ids")

matched_chunks = []
with zipfile.ZipFile(zip_path) as z:
    with z.open("GWDBDownload/WaterQualityMajor.txt") as f:
        for chunk in pd.read_csv(
            f, sep="|", dtype=str,
            usecols=["StateWellNumber", "SampleDate", "ParameterCode", "ParameterDescription",
                     "ParameterUnitOfMeasure", "ParameterValue"],
            chunksize=200_000,
        ):
            matched = chunk[chunk["StateWellNumber"].isin(well_ids)]
            if len(matched):
                matched_chunks.append(matched)

water_quality_major = pd.concat(matched_chunks, ignore_index=True) if matched_chunks else pd.DataFrame()
print(f"{len(water_quality_major)} WaterQualityMajor rows matched our wells")
water_quality_major.head()

# %% [markdown]
# ## Step 5 — Confirm parameter codes classify with the existing `classify_parameter`
#
# TWDB's `ParameterCode` values are the same 5-digit USGS-style codes already in `PRIORITY_GROUPS`
# (verified: `00010` temperature, `00300` dissolved oxygen, `00400`/`00403` pH, `00095` specific
# conductance, the `006xx`/`0066x` nitrogen/phosphorus families, plus `82079` turbidity — the last
# two required widening `PRIORITY_GROUPS`, done in a separate task group).

# %%
from _helpers import classify_parameter

water_quality_major["priority_group"] = water_quality_major["ParameterCode"].map(
    lambda c: classify_parameter(parameter_code=c)
)
print(water_quality_major["priority_group"].value_counts(dropna=False))
