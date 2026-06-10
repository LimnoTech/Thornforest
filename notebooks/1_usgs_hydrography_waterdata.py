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
# 1. Look up the **boundaries** of our three watersheds of interest, and
# 2. Draw them on an **interactive map**.
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
# - **`geopandas`** — works with *geographic* tables, where each row has a shape
#   (a "geometry") in addition to ordinary columns. We only import it indirectly here.
# - **`geoviews`** — makes interactive maps you can pan, zoom, and hover over.

# %%
from pygeohydro import WBD

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
# ## What's next
#
# We now have the three watershed boundaries loaded and mapped. In the next parts of this
# notebook we will:
#
# - **save** the boundaries to `data/spatial/` so the other notebooks can reuse them, then
# - **discover monitoring stations** using the new USGS `dataretrieval.waterdata` tools.
