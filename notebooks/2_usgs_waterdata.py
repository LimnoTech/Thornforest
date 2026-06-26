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
#     display_name: default
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 2 · USGS WaterData — Monitoring Stations & Parameters
#
# Reads the watershed boundaries from notebook 1, discovers the USGS monitoring stations
# inside them via the new USGS **Water Data** API, and records **which priority parameters**
# each station measured.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
from io import StringIO
from urllib.parse import quote

import geopandas as gpd
import pandas as pd
import async_retriever as ar
from dataretrieval import waterdata

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import (
    init_session,
    save_outputs,
    show,
    categorical_colors,
    make_legend_clickable,
)

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 5 — Discover monitoring stations
#
# We load the watershed boundaries saved by notebook 1, ask the Water Data API for every
# station in their bounding box, then keep only those that fall **within** the watershed
# polygons (a spatial join).

# %%
boundaries_path = S.data_dir / "spatial" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrofabric) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)
bbox = list(watersheds_gdf.total_bounds)  # [min_lon, min_lat, max_lon, max_lat]; reused below

stations_gdf, _ = waterdata.get_monitoring_locations(bbox=bbox)
stations_gdf = stations_gdf.set_crs(4326)
stations_in_area = gpd.sjoin(
    stations_gdf,
    watersheds_gdf[["huc8", "name", "geometry"]],
    predicate="within",
    how="inner",
)
print(
    f"{len(stations_gdf)} stations in the bounding box; "
    f"{len(stations_in_area)} within the watersheds."
)
save_outputs(
    stations_in_area, S.data_dir / "usgs_waterdata" / "usgs_monitoring_locations.parquet"
)

# %% [markdown]
# ### What kinds of stations are there?

# %%
print("By site type:")
print(stations_in_area["site_type"].value_counts().to_string())
print("\nBy watershed:")
print(stations_in_area["name"].value_counts().to_string())
show(stations_in_area[["monitoring_location_id", "monitoring_location_name", "site_type", "name"]])

# %% [markdown]
# ## Step 6 — Which priority parameters does each station measure?
#
# The README prioritizes these water-quality parameters. For each we list the USGS parameter
# codes (`pcodes`, used by the time-series & field-measurement services) and the Water Quality
# characteristic-name patterns (used by the discrete-samples service). `classify_parameter`
# maps any measured pcode/characteristic to its priority group (or `None`).

# %%
# group -> {"pcodes": set[str], "characteristics": list[str] (lowercase substrings)}
PRIORITY_GROUPS = {
    "conductivity": {"pcodes": {"00095", "90095"}, "characteristics": ["specific conductance", "conductivity"]},
    "temperature": {"pcodes": {"00010"}, "characteristics": ["temperature, water"]},
    "dissolved_oxygen": {"pcodes": {"00300", "00301"}, "characteristics": ["dissolved oxygen"]},
    "dissolved_solids": {"pcodes": {"70300", "00515"}, "characteristics": ["total dissolved solids"]},
    "chlorophyll": {"pcodes": {"32209", "32210", "32211", "70953"}, "characteristics": ["chlorophyll", "algae"]},
    "pH": {"pcodes": {"00400"}, "characteristics": ["ph"]},  # pH matched EXACTLY (see classifier)
    "nitrogen": {
        "pcodes": {"00600", "00605", "00608", "00613", "00615", "00618", "00620", "00625", "00630"},
        "characteristics": ["nitrogen", "nitrate", "nitrite", "ammonia", "kjeldahl"],
    },
    "phosphorus": {"pcodes": {"00650", "00665", "00666", "00671"}, "characteristics": ["phosphorus", "orthophosphate"]},
    "turbidity": {"pcodes": {"00076", "63675", "63676", "63680"}, "characteristics": ["turbidity"]},
}
PRIORITY_NAMES = list(PRIORITY_GROUPS)


def classify_parameter(pcode=None, characteristic=None):
    """Return the priority group for a USGS pcode or a WQ characteristic name, else None."""
    if pcode is not None:
        code = str(pcode).strip().zfill(5)
        for group, spec in PRIORITY_GROUPS.items():
            if code in spec["pcodes"]:
                return group
    if characteristic is not None:
        name = str(characteristic).strip().lower()
        if name == "ph":
            return "pH"
        for group, spec in PRIORITY_GROUPS.items():
            if group == "pH":
                continue  # pH only via exact match above (avoid 'ph' substring false positives)
            if any(pat in name for pat in spec["characteristics"]):
                return group
    return None

# %%
SAMPLES_SUMMARY_URL = "https://api.waterdata.usgs.gov/samples-data/summary"

# Time-series metadata (daily & continuous), split by computation period; carries pcodes.
ts_meta, _ = waterdata.get_time_series_metadata(bbox=bbox, skip_geometry=True)
period = ts_meta["computation_period_identifier"]
daily_ids = set(ts_meta.loc[period == "Daily", "monitoring_location_id"])
continuous_ids = set(ts_meta.loc[period == "Points", "monitoring_location_id"])

# Field-measurement metadata; carries pcodes.
fm_meta, _ = waterdata.get_field_measurements_metadata(bbox=bbox, skip_geometry=True)
field_ids = set(fm_meta["monitoring_location_id"])

# Per-station discrete-samples summaries, fetched concurrently (and cached) via async-retriever.
station_ids = stations_in_area["monitoring_location_id"].tolist()
summary_urls = [f"{SAMPLES_SUMMARY_URL}/{quote(sid, safe='')}?mimeType=text/csv" for sid in station_ids]
summary_texts = ar.retrieve_text(
    summary_urls,
    request_kwds=[{"headers": S.api_headers}] * len(summary_urls) if S.api_headers else None,
    cache_name=S.cache_file,
    expire_after=S.cache_expire_seconds,
    limit_per_host=8,
)
samples_summaries = {  # station_id -> summary DataFrame (may be empty)
    sid: pd.read_csv(StringIO(txt)) for sid, txt in zip(station_ids, summary_texts) if txt
}
samples_ids = {sid for sid, df in samples_summaries.items() if len(df) > 0}

# %%
# Pcode -> readable name, from the USGS reference table (for the human-readable `parameters` list).
param_codes, _ = waterdata.get_reference_table("parameter-codes")
pcode_name = dict(zip(param_codes["parameter_code"].astype(str), param_codes["parameter_name"]))

# Build, per station: the set of measured pcodes/characteristics, the priority groups they hit,
# and a sorted human-readable parameter list.
ts_codes_by_site = ts_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()
fm_codes_by_site = fm_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()


def station_parameters(sid):
    """Return (priority_groups: set[str], parameter_names: sorted list[str]) for one station."""
    groups, names = set(), set()
    for code in ts_codes_by_site.get(sid, set()) | fm_codes_by_site.get(sid, set()):
        code = str(code)
        names.add(pcode_name.get(code.zfill(5), pcode_name.get(code, code)))
        g = classify_parameter(pcode=code)
        if g:
            groups.add(g)
    summary = samples_summaries.get(sid)
    if summary is not None and "characteristic" in summary.columns:
        for char in summary["characteristic"].dropna().unique():
            names.add(str(char))
            g = classify_parameter(characteristic=char)
            if g:
                groups.add(g)
    return groups, sorted(names)


groups_by_site, params_by_site = {}, {}
for sid in station_ids:
    g, names = station_parameters(sid)
    groups_by_site[sid] = g
    params_by_site[sid] = names

# Data-type flags (kept) + one boolean column per priority group + the readable parameter list.
sid_col = stations_in_area["monitoring_location_id"]
stations_in_area["daily"] = sid_col.isin(daily_ids)
stations_in_area["continuous"] = sid_col.isin(continuous_ids)
stations_in_area["field_measurements"] = sid_col.isin(field_ids)
stations_in_area["samples"] = sid_col.isin(samples_ids)
for group in PRIORITY_NAMES:
    stations_in_area[group] = sid_col.map(lambda s, g=group: g in groups_by_site.get(s, set()))
stations_in_area["parameters"] = sid_col.map(lambda s: params_by_site.get(s, []))

save_outputs(
    stations_in_area,
    S.data_dir / "usgs_waterdata" / "usgs_monitoring_locations_parameters.parquet",
)

# %% [markdown]
# ### How many stations measure each priority parameter?
#
# The audit below lists any measured pcodes/characteristics that did NOT map to a priority
# group — useful for sanity-checking and refining `PRIORITY_GROUPS`.

# %%
DATA_TYPES = ["daily", "continuous", "field_measurements", "samples"]
print("Stations by data type:")
print(stations_in_area[DATA_TYPES].sum().to_string())
print(f"\nStations by priority parameter (of {len(stations_in_area)}):")
print(stations_in_area[PRIORITY_NAMES].sum().to_string())

# Audit: characteristics seen in samples that mapped to no priority group.
unmatched = sorted({
    str(c)
    for df in samples_summaries.values()
    if "characteristic" in df.columns
    for c in df["characteristic"].dropna().unique()
    if classify_parameter(characteristic=c) is None
})
print(f"\n{len(unmatched)} unmatched sample characteristics (first 25):")
print("\n".join(unmatched[:25]))

show(stations_in_area[["monitoring_location_id", "monitoring_location_name", *PRIORITY_NAMES]])

# %% [markdown]
# ## Step 7 — Map stations by priority parameter
#
# One colored layer per priority parameter, over the watershed outlines on the topo basemap.
# A station that measures several parameters appears in several layers.
#
# > **Interactive selector:** **click a legend entry to hide/show** that parameter's layer.

# %%
PARAM_COLORS = categorical_colors(PRIORITY_NAMES)
watershed_outlines = gv.Path(watersheds_gdf).opts(color="black", line_width=1.5)

stations_param_map = gvts.EsriWorldTopo * watershed_outlines
for param in PRIORITY_NAMES:
    subset = stations_in_area[stations_in_area[param]]
    if len(subset) == 0:
        continue
    stations_param_map = stations_param_map * gv.Points(
        subset,
        vdims=["monitoring_location_name", "monitoring_location_id", "site_type"],
        label=param,
    ).opts(color=PARAM_COLORS[param], size=7, line_color="white", tools=["hover"])

stations_param_map = stations_param_map.opts(
    frame_width=800,
    data_aspect=1,
    title="Monitoring stations by priority parameter (click legend to toggle)",
    legend_position="right",
    active_tools=["wheel_zoom"],
    hooks=[make_legend_clickable],
)
stations_param_map

# %% [markdown]
# ## What's next
#
# The station inventory — with data-type flags and per-parameter columns — is saved to
# `data/usgs_waterdata/`. Later notebooks will **fetch the actual records** (daily, continuous,
# field measurements, samples) for these stations and parameters.
