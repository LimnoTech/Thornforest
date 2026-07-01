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
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames — used by the availability plots)
import pandas as pd
import async_retriever as ar
from dataretrieval import waterdata

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import (
    init_session,
    save_dataframe,
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
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
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
save_dataframe(
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
# The README prioritizes these water-quality parameters, plus water-quantity (flow & level). For
# each we list the USGS `parameter_code`s (used by the time-series & field-measurement services) and
# the Water Quality characteristic-name patterns (used by the discrete-samples service).
# `classify_parameter` maps any measured parameter code / characteristic to its priority group (or `None`).

# %%
# group -> {"parameter_codes": set[str], "characteristics": list[str] (lowercase substrings)}
PRIORITY_GROUPS = {
    "conductivity": {"parameter_codes": {"00095", "90095"}, "characteristics": ["specific conductance", "conductivity"]},
    "temperature": {"parameter_codes": {"00010"}, "characteristics": ["temperature, water"]},
    "dissolved_oxygen": {"parameter_codes": {"00300", "00301"}, "characteristics": ["dissolved oxygen"]},
    "dissolved_solids": {"parameter_codes": {"70300", "00515"}, "characteristics": ["total dissolved solids"]},
    "chlorophyll": {"parameter_codes": {"32209", "32210", "32211", "70953"}, "characteristics": ["chlorophyll", "algae"]},
    "pH": {"parameter_codes": {"00400"}, "characteristics": ["ph"]},  # pH matched EXACTLY (see classifier)
    "nitrogen": {
        "parameter_codes": {"00600", "00605", "00608", "00613", "00615", "00618", "00620", "00625", "00630"},
        "characteristics": ["nitrogen", "nitrate", "nitrite", "ammonia", "kjeldahl"],
    },
    "phosphorus": {"parameter_codes": {"00650", "00665", "00666", "00671"}, "characteristics": ["phosphorus", "orthophosphate"]},
    "turbidity": {"parameter_codes": {"00076", "63675", "63676", "63680"}, "characteristics": ["turbidity"]},
    # Water quantity (flow & level), added Round 1.1
    "discharge": {
        "parameter_codes": {"00060", "00061", "00055", "70232", "30208", "30209"},  # discharge + velocity
        "characteristics": ["discharge", "stream flow", "streamflow"],
    },
    "water_level": {
        "parameter_codes": {"00065", "00062", "00054", "62611", "62614", "62615", "63160", "72019", "72020", "72148", "72150", "72170"},  # gage height / stage / depth / elevation
        "characteristics": ["gage height", "stream stage", "water level", "water-surface elevation"],
    },
}
PRIORITY_NAMES = list(PRIORITY_GROUPS)


def classify_parameter(parameter_code=None, characteristic=None):
    """Return the priority group for a USGS parameter_code or a WQ characteristic name, else None."""
    if parameter_code is not None:
        parameter_code = str(parameter_code).strip().zfill(5)
        for group, spec in PRIORITY_GROUPS.items():
            if parameter_code in spec["parameter_codes"]:
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

# Time-series metadata (daily & continuous), split by computation period; carries parameter_codes.
ts_meta, _ = waterdata.get_time_series_metadata(bbox=bbox, skip_geometry=True)
period = ts_meta["computation_period_identifier"]
daily_ids = set(ts_meta.loc[period == "Daily", "monitoring_location_id"])
continuous_ids = set(ts_meta.loc[period == "Points", "monitoring_location_id"])

# Field-measurement metadata; carries parameter_codes.
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
# parameter_code -> readable name, from the USGS reference table (for the `parameters` list).
parameter_codes_table, _ = waterdata.get_reference_table("parameter-codes")
parameter_name_by_code = dict(
    zip(parameter_codes_table["parameter_code"].astype(str), parameter_codes_table["parameter_name"])
)

# Build, per station: the set of measured parameter_codes/characteristics, the priority groups they
# hit, and a sorted human-readable parameter list.
ts_parameter_codes_by_site = ts_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()
fm_parameter_codes_by_site = fm_meta.groupby("monitoring_location_id")["parameter_code"].agg(set).to_dict()


def station_parameters(sid):
    """Return (priority_groups: set[str], parameter_names: sorted list[str]) for one station."""
    groups, names = set(), set()
    for parameter_code in ts_parameter_codes_by_site.get(sid, set()) | fm_parameter_codes_by_site.get(sid, set()):
        parameter_code = str(parameter_code)
        names.add(
            parameter_name_by_code.get(
                parameter_code.zfill(5), parameter_name_by_code.get(parameter_code, parameter_code)
            )
        )
        g = classify_parameter(parameter_code=parameter_code)
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

save_dataframe(
    stations_in_area,
    S.data_dir / "usgs_waterdata" / "usgs_monitoring_locations_parameters.parquet",
)

# %% [markdown]
# ### How many stations measure each priority parameter?
#
# The audit below lists any measured parameter codes / characteristics that did NOT map to a priority
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
# ## Step 7 — Fetch the time-series records
#
# For the stations that actually have data, fetch the **full available record** of the **priority
# parameters** from three USGS Water Data services and save one tidy (long-format) table per data
# type. Daily values and field measurements filter by USGS `parameter_code`; discrete samples are
# keyed by characteristic name, so we fetch all and keep rows whose characteristic maps to a
# priority group. (Analysis later subsets to the 25-year study window — we keep everything.)

# %%
# All priority parameter codes, flattened, for the code-keyed services (daily, field).
PRIORITY_CODES = sorted({c for spec in PRIORITY_GROUPS.values() for c in spec["parameter_codes"]})

# Reusable lookups (built from the inventory in Step 6).
huc8_by_station = dict(zip(stations_in_area["monitoring_location_id"], stations_in_area["huc8"]))


def _parameter_name(code):
    code = str(code)
    return parameter_name_by_code.get(code.zfill(5), parameter_name_by_code.get(code, code))

# %% [markdown]
# ### Daily values
#
# Daily statistics (mostly discharge & water level) for the stations flagged `daily`.

# %%
daily_station_ids = stations_in_area.loc[stations_in_area["daily"], "monitoring_location_id"].tolist()
daily_raw, _ = waterdata.get_daily(
    monitoring_location_id=daily_station_ids,
    parameter_code=PRIORITY_CODES,
    skip_geometry=True,
)
daily = daily_raw.rename(columns={"time": "date", "statistic_id": "statistic", "unit_of_measure": "unit"})
daily["parameter_name"] = daily["parameter_code"].map(_parameter_name)
daily["priority_group"] = daily["parameter_code"].map(lambda c: classify_parameter(parameter_code=c))
daily = daily[daily["priority_group"].notna()].copy()
daily["huc8"] = daily["monitoring_location_id"].map(huc8_by_station)
daily = (
    daily[
        ["monitoring_location_id", "date", "parameter_code", "parameter_name", "statistic",
         "value", "unit", "approval_status", "qualifier", "priority_group", "huc8"]
    ]
    .sort_values(["monitoring_location_id", "parameter_code", "date"])
    .reset_index(drop=True)
)
save_dataframe(daily, S.data_dir / "usgs_waterdata" / "usgs_daily_values.parquet")

# %% [markdown]
# ### Discrete water-quality samples
#
# Lab samples for the stations flagged `samples`. The samples service is keyed by characteristic
# **name**, so we fetch all results per station and keep those whose characteristic maps to one of
# our priority groups via `classify_parameter`.

# %%
samples_station_ids = stations_in_area.loc[stations_in_area["samples"], "monitoring_location_id"].tolist()
samples_raw, _ = waterdata.get_samples(monitoring_location_id=samples_station_ids)
samples = samples_raw.rename(columns={
    "Location_Identifier": "monitoring_location_id",
    "Activity_StartDateTime": "datetime",
    "Result_Characteristic": "characteristic",
    "USGSpcode": "parameter_code",
    "Result_Measure": "value",  # NOTE: value is str (includes non-detect/text results); cast with pd.to_numeric(errors="coerce") before numeric ops
    "Result_MeasureUnit": "unit",
    "Result_SampleFraction": "fraction",
    "Result_ResultDetectionCondition": "detection_condition",
    "Result_MeasureQualifierCode": "qualifier",
    "Result_CharacteristicGroup": "characteristic_group",
    "LabInfo_Name": "lab_name",
})
samples["priority_group"] = samples["characteristic"].map(lambda c: classify_parameter(characteristic=c))
samples = samples[samples["priority_group"].notna()].copy()
samples["huc8"] = samples["monitoring_location_id"].map(huc8_by_station)
samples = (
    samples[
        ["monitoring_location_id", "datetime", "characteristic", "parameter_code", "value", "unit",
         "fraction", "detection_condition", "qualifier", "characteristic_group", "lab_name",
         "priority_group", "huc8"]
    ]
    .sort_values(["monitoring_location_id", "characteristic", "datetime"])
    .reset_index(drop=True)
)
save_dataframe(samples, S.data_dir / "usgs_waterdata" / "usgs_samples.parquet")

# %% [markdown]
# ### Field measurements
#
# In-situ readings (temperature, DO, pH, conductivity, turbidity, …) for the stations flagged
# `field_measurements`.

# %%
field_station_ids = stations_in_area.loc[stations_in_area["field_measurements"], "monitoring_location_id"].tolist()
field_raw, _ = waterdata.get_field_measurements(
    monitoring_location_id=field_station_ids,
    parameter_code=PRIORITY_CODES,
    skip_geometry=True,
)
field = field_raw.rename(columns={"time": "datetime", "unit_of_measure": "unit"})
field["parameter_name"] = field["parameter_code"].map(_parameter_name)
field["priority_group"] = field["parameter_code"].map(lambda c: classify_parameter(parameter_code=c))
field = field[field["priority_group"].notna()].copy()
field["huc8"] = field["monitoring_location_id"].map(huc8_by_station)
field = (
    field[
        ["monitoring_location_id", "datetime", "parameter_code", "parameter_name", "value", "unit",
         "qualifier", "approval_status", "priority_group", "huc8"]
    ]
    .sort_values(["monitoring_location_id", "parameter_code", "datetime"])
    .reset_index(drop=True)
)
save_dataframe(field, S.data_dir / "usgs_waterdata" / "usgs_field_measurements.parquet")

# %% [markdown]
# ## Step 8 — Map stations by priority parameter
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
    data_aspect=1,
    title="Monitoring stations by priority parameter (click legend to toggle)",
    legend_position="right",
    hooks=[make_legend_clickable],
)
stations_param_map

# %% [markdown]
# ## Step 10 — Data availability & a sample series
#
# Confirm the fetch: per data type, how many records and what date span each station × priority
# group has, a quick availability heatmap, and one illustrative series. (Trend and pre/post
# analyses live in the later display notebooks.)

# %%
def coverage(df, time_col):
    """Record count + first/last date per station × priority group."""
    t = pd.to_datetime(df[time_col])
    out = (
        df.assign(_t=t)
        .groupby(["monitoring_location_id", "priority_group"])["_t"]
        .agg(n="size", start="min", end="max")
        .reset_index()
        .sort_values(["priority_group", "monitoring_location_id"])
    )
    return out


show(coverage(daily, "date"))

# %%
show(coverage(samples, "datetime"))

# %%
show(coverage(field, "datetime"))

# %%
# Daily-value availability: record count per station per year.
daily_year = daily.assign(year=pd.to_datetime(daily["date"]).dt.year)
availability = daily_year.groupby(["monitoring_location_id", "year"]).size().reset_index(name="records")
availability.hvplot.heatmap(
    x="year", y="monitoring_location_id", C="records", cmap="blues",
    title="Daily-value record availability (count per station-year)", colorbar=True, rot=45,
)

# %%
# Illustrative series: daily discharge at the station with the most discharge records.
discharge = daily[daily["priority_group"] == "discharge"].copy()
if discharge.empty:
    sample_series = None
    print("No discharge records found — skipping sample series.")
else:
    gauge = discharge.groupby("monitoring_location_id").size().idxmax()
    series = discharge[discharge["monitoring_location_id"] == gauge].assign(
        value=lambda d: pd.to_numeric(d["value"], errors="coerce")
    )
    sample_series = series.hvplot.line(
        x="date", y="value", title=f"Daily mean discharge — {gauge}", ylabel="ft³/s", xlabel="",
    )
sample_series
