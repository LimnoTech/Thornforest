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
# # 1 · USGS Hydrography & WaterData — Watershed Boundaries
#
# This is the **first notebook** in the Thornforest hydrology series. It builds the
# *spatial foundation* that every later notebook relies on, and then begins discovering
# what monitoring data is available.
#
# Our project focuses on **three HUC-8 subbasins** in South Texas.
# - South Laguna Madre (12110208)
# - Los Olmos (13090001)
# - Lower Rio Grande (13090002)
#
# **In this first part we will:**
#
# 1. Look up the **boundaries** of our three watersheds of interest,
# 2. Draw them on an **interactive map**,
# 3. **Discover the monitoring stations** within them, and
# 4. See **which data types** (daily, continuous, field measurements, samples) each offers.
#
# > **New to Python notebooks?** A Jupyter notebook is a list of *cells*. A cell holds
# > either explanatory text (like this one) or Python code. Run a code cell by selecting
# > it and pressing **Shift + Enter**. Run the cells **in order from top to bottom** — each
# > one builds on the ones above it.

# %% [markdown]
# ## Step 1 — Load the Python tools we need
#
# Each `import` line loads a software library (a toolbox of ready-made functions):
#
# - **`pygeohydro`** — part of the [HyRiver](https://docs.hyriver.io/) suite; its `WBD`
#   tool downloads boundaries from the USGS **W**atershed **B**oundary **D**ataset.
# - **`dataretrieval`** — the USGS package for the new **Water Data** API; its `waterdata`
#   module lists and downloads monitoring-station data.
# - **`geopandas`** — works with *geographic* tables, where each row has a shape (a
#   "geometry"); we use it to keep only the stations that fall inside our watersheds.
# - **`geoviews`** — makes interactive maps you can pan, zoom, and hover over.

# %%
from pygeohydro import WBD
from dataretrieval import waterdata

import geopandas as gpd
import geoviews as gv
import geoviews.tile_sources as gvts

# Turn on GeoViews' interactive (Bokeh) plotting. Run this once per session.
gv.extension("bokeh")

# %% [markdown]
# ## Step 2 — Name our three watersheds
#
# We store the three HUC-8 codes and their names in a **dictionary** — a lookup table that
# maps each code (the "key") to a friendly name (the "value"). We also pick a distinct
# color for each, so they are easy to tell apart on the map.

# %%
# HUC-8 code  ->  watershed name
HUC8_WATERSHEDS = {
    "12110208": "South Laguna Madre",
    "13090001": "Los Olmos",
    "13090002": "Lower Rio Grande",
}

# HUC-8 code  ->  map color (colorblind-friendly)
HUC8_COLORS = {
    "12110208": "#1b9e77",  # teal-green
    "13090001": "#d95f02",  # orange
    "13090002": "#7570b3",  # purple
}

# %% [markdown]
# ## Step 3 — Download the watershed boundaries
#
# `WBD("huc8")` connects to the USGS Watershed Boundary Dataset service for HUC-8 areas.
# Its `.byids()` method fetches specific watersheds **by their ID codes** — here, the three
# codes from our dictionary (`list(HUC8_WATERSHEDS)` gives just the codes).
#
# This makes a live request over the internet, so it may take a few seconds.

# %%
wbd = WBD("huc8")
watersheds_gdf = wbd.byids("huc8", list(HUC8_WATERSHEDS))

print(f"Downloaded {len(watersheds_gdf)} watershed boundaries.")

# %% [markdown]
# ### What did we get back?
#
# The result is a **GeoDataFrame**: a spreadsheet-like table where every row is one
# watershed, with a special `geometry` column holding its boundary shape. Let's peek at a
# few useful columns — the code, the name, and the area in square kilometers.
#
# The `.crs` ("coordinate reference system") tells us the coordinates are plain
# **longitude/latitude** (EPSG:4326), the most common geographic system.

# %%
print("Coordinate system:", watersheds_gdf.crs)

# Show just the human-readable columns (not the long geometry shapes).
watersheds_gdf[["huc8", "name", "areasqkm", "states"]]

# %% [markdown]
# ## Step 4 — Map the watersheds
#
# Now we draw the boundaries on a real-world basemap. We build the map in layers:
#
# 1. **`gvts.EsriWorldTopo`** — Esri's World Topographic Map (terrain shading, roads, and
#    place names) for geographic context.
# 2. One **`gv.Polygons`** layer per watershed, each in its own color, so we get a legend.
#
# The `*` symbol **stacks layers** on top of each other into a single combined map.
#
# > **How to explore the map:** *hover* over a watershed to see its name and area; use the
# > toolbar on the right to **zoom**, **pan**, and **reset**; click legend entries to focus.

# %%
# Build one colored layer per watershed (a loop avoids repeating the same code 3 times).
watershed_layers = []
for code, name in HUC8_WATERSHEDS.items():
    one_watershed = watersheds_gdf[watersheds_gdf["huc8"] == code]
    layer = gv.Polygons(
        one_watershed,
        vdims=["name", "huc8", "areasqkm"],  # columns shown in the hover tooltip
        label=name,                           # text shown in the legend
    ).opts(
        color=HUC8_COLORS[code],
        line_color=HUC8_COLORS[code],
        alpha=0.45,        # fill transparency, so the basemap shows through
        line_width=2,
        tools=["hover"],
    )
    watershed_layers.append(layer)

# Stack the basemap and all watershed layers into one map.
watersheds_map = gvts.EsriWorldTopo
for layer in watershed_layers:
    watersheds_map = watersheds_map * layer

# Final styling. We set the map *width* and lock `data_aspect=1` so that the height is
# computed automatically to match the watersheds' true geographic proportions. This keeps
# map pixels square — otherwise the basemap tiles get stretched and look blurry.
watersheds_map = watersheds_map.opts(
    frame_width=850,
    data_aspect=1,
    title="Three HUC-8 Watersheds — Thornforest Study Area (South Texas)",
    legend_position="top_left",
    active_tools=["wheel_zoom"],
)

watersheds_map

# %% [markdown]
# ## Step 5 — Discover monitoring stations
#
# With the study area defined, we can ask **what monitoring data exists** there. We use the
# new USGS **Water Data** API (the modern replacement for the legacy NWIS) through the
# `dataretrieval.waterdata` module. Its `get_monitoring_locations()` function lists stations
# — stream gauges, wells, water-quality sites, and more.
#
# The API filters by a rectangular **bounding box**, so we do this in two steps:
#
# 1. ask for every station in the box around our watersheds, then
# 2. keep only those that fall **inside** the actual (irregular) watershed boundaries, using
#    a *spatial join* (`geopandas.sjoin`).
#
# (No API key is required; one only raises rate limits — see the README.)

# %%
# 1. Fetch all monitoring locations in the bounding box of our watersheds.
#    total_bounds gives [min_lon, min_lat, max_lon, max_lat].
bbox = list(watersheds_gdf.total_bounds)
stations_gdf, _metadata = waterdata.get_monitoring_locations(bbox=bbox)
stations_gdf = stations_gdf.set_crs(4326)  # the API returns longitude/latitude

# 2. Keep only the stations that fall within the three watershed polygons.
stations_in_area = gpd.sjoin(
    stations_gdf,
    watersheds_gdf[["huc8", "name", "geometry"]],
    predicate="within",
    how="inner",
)

print(
    f"{len(stations_gdf)} stations in the bounding box; "
    f"{len(stations_in_area)} fall within the watersheds."
)

# %% [markdown]
# ### What kinds of stations are there?
#
# Each station has a **`site_type`** (Stream, Well, Estuary, …). Here is the mix within our
# watersheds, and how the stations split across the three subbasins (the `name` column comes
# from the watershed we joined them to).

# %%
print("By site type:")
print(stations_in_area["site_type"].value_counts().to_string())
print("\nBy watershed:")
print(stations_in_area["name"].value_counts().to_string())

stations_in_area[
    ["monitoring_location_id", "monitoring_location_name", "site_type", "name"]
].head(10)

# %% [markdown]
# ## Step 6 — Which data endpoints does each station offer?
#
# The Water Data API serves several **kinds** of records. The four we care about — each with
# its own download function for later notebooks — are:
#
# | Data type | Endpoint | What it is |
# |-----------|----------|------------|
# | **Daily** | `get_daily()` | daily summary values (min / mean / max) |
# | **Continuous** | `get_continuous()` | high-frequency instantaneous readings |
# | **Field measurements** | `get_field_measurements()` | manual field readings (e.g. discharge measurements) |
# | **Samples** | `get_samples()` | discrete water-quality sample results |
#
# Before fetching any actual data, it helps to know **which stations have which types**. We
# read that from the matching *metadata* services:
#
# - **Daily** and **Continuous** both come from `get_time_series_metadata()`; its
#   `computation_period_identifier` column tells them apart (`"Daily"` vs `"Points"`).
# - **Field measurements** come from `get_field_measurements_metadata()`.
# - **Samples** are checked per station with `get_samples_summary()` — one quick request each.
#   (This is the slowest cell, because it loops over every station; the area-wide samples
#   service times out, so a per-station check is the reliable way.)

# %%
# Daily & continuous availability — one bounding-box query, split by computation period.
ts_meta, _ = waterdata.get_time_series_metadata(bbox=bbox, skip_geometry=True)
daily_ids = set(
    ts_meta.loc[ts_meta["computation_period_identifier"] == "Daily", "monitoring_location_id"]
)
continuous_ids = set(
    ts_meta.loc[ts_meta["computation_period_identifier"] == "Points", "monitoring_location_id"]
)

# Field-measurement availability — one bounding-box query.
fm_meta, _ = waterdata.get_field_measurements_metadata(bbox=bbox, skip_geometry=True)
field_ids = set(fm_meta["monitoring_location_id"])

# Samples availability — one summary request per station (non-empty summary = has samples).
samples_ids = set()
station_ids = stations_in_area["monitoring_location_id"].tolist()
for i, station_id in enumerate(station_ids, start=1):
    try:
        summary, _ = waterdata.get_samples_summary(monitoringLocationIdentifier=station_id)
        if len(summary) > 0:
            samples_ids.add(station_id)
    except Exception:
        pass  # treat a failed lookup as "no samples"
    if i % 50 == 0:
        print(f"  checked samples for {i}/{len(station_ids)} stations…")
print(f"Done: checked samples for {len(station_ids)} stations.")

# %% [markdown]
# ### Flag each station with the data types it offers
#
# We add four True/False columns to the stations table — one per data type — by testing
# whether each station's ID appears in the sets we just built.

# %%
station_id_col = stations_in_area["monitoring_location_id"]
stations_in_area["daily"] = station_id_col.isin(daily_ids)
stations_in_area["continuous"] = station_id_col.isin(continuous_ids)
stations_in_area["field_measurements"] = station_id_col.isin(field_ids)
stations_in_area["samples"] = station_id_col.isin(samples_ids)

DATA_TYPES = ["daily", "continuous", "field_measurements", "samples"]
print(f"Stations offering each data type (of {len(stations_in_area)} total):")
print(stations_in_area[DATA_TYPES].sum().to_string())

stations_in_area[
    ["monitoring_location_id", "monitoring_location_name", *DATA_TYPES]
].head(10)

# %% [markdown]
# ## Step 7 — Map stations by available data type
#
# Finally, map the stations as **one colored layer per data type**, over the watershed
# outlines. A station that offers more than one type appears in more than one layer.
#
# > **Interactive selector:** the four data types appear in the **legend** on the right —
# > **click a legend entry to hide or show** that type, toggling each on and off individually.

# %%
DATA_TYPE_COLORS = {
    "daily": "#1b9e77",            # teal-green
    "continuous": "#d95f02",       # orange
    "field_measurements": "#7570b3",  # purple
    "samples": "#e7298a",          # magenta
}


def make_legend_clickable(plot, element):
    """Bokeh hook: clicking a legend entry hides/shows that data-type layer."""
    plot.state.legend.click_policy = "hide"


# Watershed outlines (no fill) for context.
watershed_outlines = gv.Path(watersheds_gdf).opts(color="black", line_width=1.5)

# Start from the basemap + outlines, then add one point layer per data type.
stations_map = gvts.EsriWorldTopo * watershed_outlines
for data_type, color in DATA_TYPE_COLORS.items():
    subset = stations_in_area[stations_in_area[data_type]]
    if len(subset) == 0:
        continue  # nothing to draw for this type
    points = gv.Points(
        subset,
        vdims=["monitoring_location_name", "monitoring_location_id", "site_type"],
        label=data_type,
    ).opts(color=color, size=7, line_color="white", tools=["hover"])
    stations_map = stations_map * points

stations_map = stations_map.opts(
    frame_width=850,
    data_aspect=1,
    title="Monitoring stations by available data type (click legend to toggle)",
    legend_position="right",
    active_tools=["wheel_zoom"],
    hooks=[make_legend_clickable],
)
stations_map

# %% [markdown]
# ## What's next
#
# We now have the three watershed boundaries mapped and the monitoring stations within them
# discovered. In the next notebooks we will:
#
# - **save** the boundaries and the station inventory to `data/` for reuse, then
# - **fetch the actual records** (streamflow, water quality, precipitation) for these
#   stations using the `dataretrieval.waterdata` data endpoints.
