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
# # 1 · USGS Hydrofabric — Watershed Boundaries & HydroGeospatial Context
#
# First notebook in the Thornforest hydrology series. It builds the **spatial foundation** (the three HUC-8 watershed boundaries) that the other notebooks rely on, and maps it.
#
# Our study area is **three HUC-8 subbasins** in South Texas:
# - South Laguna Madre (12110208)
# - Los Olmos (13090001)
# - Lower Rio Grande (13090002)
#
# > **New to Python notebooks?** Run each cell in order with **Shift + Enter**.

# %% [markdown]
# ## Step 1 — Imports and setup
#
# All imports are at the top. `init_session()` (from our shared `_helpers` module) loads the
# optional USGS API key, configures the on-disk request cache, and returns the paths we use.

# %%
from pygeohydro import WBD

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import init_session, save_outputs, show, categorical_colors

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Name our three watersheds
#
# A dictionary maps each HUC-8 code to a friendly name. Colors come from a **colorcet**
# categorical palette (via `categorical_colors`) so the figure data colors are perceptually
# distinct and consistent across the project.

# %%
HUC8_WATERSHEDS = {
    "12110208": "South Laguna Madre",
    "13090001": "Los Olmos",
    "13090002": "Lower Rio Grande",
}
HUC8_COLORS = categorical_colors(HUC8_WATERSHEDS)  # huc8 code -> hex

# %% [markdown]
# ## Step 3 — Download the watershed boundaries
#
# `WBD("huc8").byids(...)` fetches the three boundaries from the USGS Watershed Boundary
# Dataset. The request is cached on disk; the result is also saved to `data/spatial/`.

# %%
watersheds_gdf = WBD("huc8").byids("huc8", list(HUC8_WATERSHEDS))
save_outputs(watersheds_gdf, S.data_dir / "spatial" / "huc8_watersheds.parquet")
print(f"{len(watersheds_gdf)} watershed boundaries.")

# %% [markdown]
# ### What did we get back?
#
# A **GeoDataFrame** (one row per watershed, with a `geometry` shape). The coordinates are
# longitude/latitude (EPSG:4326).

# %%
print("Coordinate system:", watersheds_gdf.crs)
show(watersheds_gdf[["huc8", "name", "areasqkm", "states"]])

# %% [markdown]
# ## Step 4 — Map the watersheds
#
# We layer the boundaries over an Esri World Topo basemap; `*` stacks layers. `data_aspect=1`
# keeps map pixels square so the basemap tiles aren't stretched.
#
# > **Explore:** hover for name/area; zoom/pan with the toolbar; click legend entries.

# %%
watershed_layers = []
for code, name in HUC8_WATERSHEDS.items():
    one = watersheds_gdf[watersheds_gdf["huc8"] == code]
    watershed_layers.append(
        gv.Polygons(one, vdims=["name", "huc8", "areasqkm"], label=name).opts(
            color=HUC8_COLORS[code],
            line_color=HUC8_COLORS[code],
            alpha=0.45,
            line_width=2,
            tools=["hover"],
        )
    )

watersheds_map = gvts.EsriWorldTopo
for layer in watershed_layers:
    watersheds_map = watersheds_map * layer

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
# The boundaries are saved to `data/spatial/`. Notebook **`2_usgs_waterdata`** reads them to
# discover the USGS monitoring stations inside the watersheds and the parameters they measure.
