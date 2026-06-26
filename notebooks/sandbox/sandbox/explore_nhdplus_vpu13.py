# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Explore NHDPlus V2.1 — Rio Grande (VPU 13) flowlines from EPA's S3
#
# **Goal:** evaluate the EPA NHDPlus V2.1 *Rio Grande* Vector Processing Unit (**VPU 13**) as
# the source for our stream network — specifically whether it can give us flowlines on **both
# sides** of the Rio Grande (US **and** Mexico) for the binational study area.
#
# Method mirrors `data-engine/sandbox/explore_nhd.py`: pull the regional `.7z` archives from
# the anonymous EPA S3 bucket, extract with `libarchive`, and read the file geodatabase with
# `pyogrio`.
#
# - Source page: <https://www.epa.gov/waterdata/nhdplus-rio-grande-data-vector-processing-unit-13>
# - National data index: <https://www.epa.gov/waterdata/nhdplus-national-data>
# - S3 bucket: `s3://dmap-data-commons-ow/NHDPlusV21/` (browse at
#   <https://dmap-data-commons-ow.s3.amazonaws.com/index.html#NHDPlusV21/>)

# %% [markdown]
# ## Imports

# %%
import os
from pathlib import Path

import s3fs
import pyogrio
import pyarrow as pa
import pandas as pd
import geopandas as gpd
import libarchive

import geoviews as gv
import geoviews.tile_sources as gvts

gv.extension("bokeh")

# %% [markdown]
# ## Paths
#
# Raw source archives are scratch data, so they go in the git-ignored `data_temp/` at the
# repo root (not the curated `data/` directory).

# %%
project_path = Path.cwd().parent  # this notebook lives in sandbox/
data_path = project_path / "data_temp" / "EPA_NHDplus21" / "RG_13"
data_path.mkdir(parents=True, exist_ok=True)
data_path

# %% [markdown]
# ## Browse the Rio Grande (VPU 13) files on S3
#
# The EPA stages NHDPlus by *drainage area*; the Rio Grande area is `NHDPlusRG`. We use
# [`s3fs`](https://s3fs.readthedocs.io/) with `anon=True` (no credentials needed).

# %%
s3 = s3fs.S3FileSystem(anon=True, client_kwargs=dict(region_name="us-east-1"))
rg_s3 = "dmap-data-commons-ow/NHDPlusV21/Data/NHDPlusRG"

# The two components we need: the hydrography snapshot (geometry) and the value-added
# attributes (which hold stream order).
for f in s3.ls(rg_s3):
    name = f.split("/")[-1]
    if "NHDSnapshotFGDB" in name or "NHDPlusAttributes" in name:
        print(f"{name:48s} {s3.info(f)['size'] / 1e6:6.1f} MB")

# %% [markdown]
# ## Download the two components (cached)
#
# - **`NHDSnapshotFGDB`** — a file geodatabase with the `NHDFlowline` features (the geometry).
# - **`NHDPlusAttributes`** — value-added tables; `PlusFlowlineVAA` holds `StreamOrde`,
#   `TotDASqKM`, etc., joined to flowlines by **COMID**.

# %%
components = {
    "snapshot": "NHDPlusV21_RG_13_NHDSnapshotFGDB_05.7z",
    "attributes": "NHDPlusV21_RG_13_NHDPlusAttributes_07.7z",
}

for label, fname in components.items():
    local = data_path / fname
    if local.exists():
        print(f"{label}: already downloaded ({local.name})")
    else:
        print(f"{label}: downloading {fname} ...")
        s3.get(f"{rg_s3}/{fname}", str(local))
        print(f"   done ({local.stat().st_size / 1e6:.1f} MB)")

# %% [markdown]
# ## Extract the archives
#
# GDAL *can* read some archives directly, but reading `.7z` reliably needs a GDAL built
# against `libarchive`; the simplest robust path is to extract once with the
# [`libarchive`](https://github.com/Changaco/python-libarchive-c) Python bindings.
# `libarchive.extract_file()` extracts into the *current* directory, so we `chdir` first.

# %%
cwd = Path.cwd()
os.chdir(data_path)
try:
    if not list(Path(".").rglob("NHDSnapshot.gdb")):
        libarchive.extract_file(components["snapshot"])
    if not list(Path(".").rglob("PlusFlowlineVAA.dbf")):
        libarchive.extract_file(components["attributes"])
finally:
    os.chdir(cwd)

gdb_path = next(data_path.rglob("NHDSnapshot.gdb"))
vaa_path = next(data_path.rglob("PlusFlowlineVAA.dbf"))
print("geodatabase:", gdb_path.relative_to(project_path))
print("VAA table:  ", vaa_path.relative_to(project_path))

# %% [markdown]
# ## Read the flowlines
#
# We read the `NHDFlowline` layer with `pyogrio` via Arrow, which preserves data types
# better than `gpd.read_file()` (see the `data-engine` benchmarks). Note this snapshot keys
# flowlines on `Permanent_Identifier`; for NHDFlowline that value **is** the integer COMID,
# which we make explicit for the attribute join.
#
# ⚠️ **Schema gotcha:** in this file geodatabase, `FType` is stored as a **numeric NHD code**
# (e.g. `460`), *not* the string `"StreamRiver"` that the WaterData web service returns. We
# decode the codes we care about into a readable `FType_name` column.

# %%
dtype_mapping = {pa.int32(): pd.Int32Dtype()}
pa_info, pa_table = pyogrio.read_arrow(gdb_path, layer="NHDFlowline")
flowlines = gpd.GeoDataFrame.from_arrow(
    pa_table,
    to_pandas_kwargs={"strings_to_categorical": True, "types_mapper": dtype_mapping.get},
)
flowlines["COMID"] = flowlines["Permanent_Identifier"].astype("int64")

# The geodatabase stores 3D (measured/Z) geometries, which GeoViews can't draw; flatten to 2D.
flowlines["geometry"] = flowlines.geometry.force_2d()

# NHD FType codes → names (the ones that occur in this region).
FTYPE_NAMES = {
    460: "StreamRiver",
    558: "ArtificialPath",
    336: "CanalDitch",
    334: "Connector",
    566: "Coastline",
    428: "Pipeline",
    420: "UndergroundConduit",
}
flowlines["FType_name"] = (
    flowlines["FType"].map(FTYPE_NAMES).fillna(flowlines["FType"].astype("string"))
)

print(f"{len(flowlines):,} flowlines | CRS: {flowlines.crs}")
print(flowlines["FType_name"].value_counts().to_string())
flowlines[["COMID", "GNIS_Name", "FType_name", "LengthKM", "ReachCode"]].head()

# %% [markdown]
# ## Join stream order from `PlusFlowlineVAA`
#
# `StreamOrde` is the NHDPlus **Strahler stream order**. We read just the columns we need and
# merge on COMID. (Negative values such as `-9` flag coastline/non-network paths.)

# %%
vaa = pyogrio.read_dataframe(
    vaa_path, read_geometry=False, columns=["ComID", "StreamOrde", "TotDASqKM"]
)
flowlines = flowlines.merge(vaa, left_on="COMID", right_on="ComID", how="left")

print("stream-order counts:")
print(flowlines["StreamOrde"].value_counts(dropna=False).sort_index().to_string())

# %% [markdown]
# ## ⚠️ Key finding: VPU 13 is US-only — it stops at the international border
#
# The whole point of this exploration was Mexican coverage. Check the bounding box: the
# **southern** edge of the data is the latitude of the Rio Grande mouth — there are **no
# flowlines south of the river**, i.e. no Mexican tributaries.

# %%
minx, miny, maxx, maxy = flowlines.total_bounds
print(f"bounding box (lon/lat): [{minx:.3f}, {miny:.3f}, {maxx:.3f}, {maxy:.3f}]")
print(f"southern extent: {miny:.3f}°N  (≈ the Rio Grande / US–Mexico border at the mouth)")
print("→ NHDPlus VPU 13 covers only the US portion of the basin. No Mexican flowlines.")

# %% [markdown]
# ## Clip to our three study watersheds and choose a stream-order threshold
#
# Keep natural channels (`FType_name == "StreamRiver"`), clipped to the three HUC-8
# watersheds. (We pull the boundaries with `pygeohydro.WBD`, as in Notebook 1; reprojecting
# to EPSG:4326 aligns the NAD83 flowlines with them.)
#
# **Threshold note:** order ≥ 5 was the original idea, but these are small *coastal* basins —
# at ≥ 5 only a couple of segments remain. The distribution below shows the trade-off, so for
# this exploratory map we use **order ≥ 3** to render a meaningful network. The final
# threshold is a decision for Notebook 1.

# %%
from pygeohydro import WBD

HUC8 = ["12110208", "13090001", "13090002"]
watersheds = WBD("huc8").byids("huc8", HUC8)

flowlines_4326 = flowlines.to_crs(watersheds.crs)
streamriver = flowlines_4326[flowlines_4326["FType_name"] == "StreamRiver"]
streamriver_in_area = gpd.clip(streamriver, watersheds)

print(f"StreamRiver flowlines clipped to the 3 watersheds: {len(streamriver_in_area)}")
print("count by minimum stream order:")
for thr in [2, 3, 4, 5]:
    print(f"  order ≥ {thr}: {(streamriver_in_area['StreamOrde'] >= thr).sum()}")

MIN_STREAM_ORDER = 3  # exploratory choice (see note above); ≥5 leaves only ~2 segments here
major_in_area = streamriver_in_area[streamriver_in_area["StreamOrde"] >= MIN_STREAM_ORDER]
print(f"\nmapping {len(major_in_area)} StreamRiver flowlines with order ≥ {MIN_STREAM_ORDER}")

# %% [markdown]
# ## Quick map
#
# Streams (blue) over the watershed outlines on the Esri World Topo basemap. The blank area
# south of the Rio Grande visually confirms the missing Mexican side.

# %%
outlines = gv.Path(watersheds, label="Watersheds").opts(color="black", line_width=2)
streams = gv.Path(
    major_in_area,
    vdims=["GNIS_Name", "StreamOrde"],
    label=f"Streams (order ≥ {MIN_STREAM_ORDER})",
).opts(color="#2b6cb0", line_width=1.5, tools=["hover"])

(gvts.EsriWorldTopo * outlines * streams).opts(
    frame_width=850,
    data_aspect=1,
    title=f"NHDPlus VPU 13 — order ≥ {MIN_STREAM_ORDER} streams in the study watersheds (US side only)",
    legend_position="top_left",
    active_tools=["wheel_zoom"],
)

# %% [markdown]
# ## Findings & next steps
#
# - ✅ The EPA NHDPlus V2.1 VPU 13 download → extract → read pipeline works and gives clean
#   flowlines with a usable `StreamOrde` (joined from `PlusFlowlineVAA` by COMID).
# - ⚠️ **Schema differs from the WaterData service:** `FType` is numeric-coded (460 =
#   StreamRiver) and `StreamOrde` lives in a separate value-added table.
# - ⚠️ **`order ≥ 5` is too strict here.** These coastal basins yield only ~2 StreamRiver
#   segments at ≥ 5 (≥ 3 → ~48, ≥ 4 → ~22). Pick the threshold deliberately in Notebook 1.
# - ❌ **No Mexican coverage.** Like the WaterData (`nhdflowline_network`) and NHDPlusHR
#   services, VPU 13 ends at the international border (~25.84°N). It cannot supply the
#   south-of-the-river tributaries.
#
# To get a **binational** stream network we still need a Mexico-capable source — e.g.
# **HydroRIVERS** (global, carries a Strahler-order field), Mexico's **INEGI** Red
# Hidrográfica, or **OpenStreetMap** waterways — to combine with (or replace) the US NHDPlus
# data. That decision belongs in the main notebook, not here.
