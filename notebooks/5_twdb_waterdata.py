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
# # 5 · TWDB Groundwater — Well Inventory, Water Levels & Quality
#
# Reads the watershed boundaries from notebook 1, discovers **TWDB Groundwater Database (GWDB)**
# wells inside them via the TWDB ArcGIS FeatureServer, then fetches their water-level and
# water-quality **measurements** from TWDB's nightly full-state bulk file — the FeatureServer only
# carries well *inventory* (location, aquifer, flags), not the actual time series. Primary source:
# <https://www.twdb.texas.gov/groundwater/data/index.asp>.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
import geopandas as gpd
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames — used by the trend chart)
import pandas as pd

import geoviews as gv
import geoviews.tile_sources as gvts

from _helpers import (
    init_session,
    save_dataframe,
    show,
    categorical_colors,
    make_legend_clickable,
    fetch_gwdb_wells,
    fetch_gwdb_zip,
    fetch_gwdb_members,
    tidy_gwdb_water_levels,
    tidy_gwdb_water_quality,
    coverage,
    trend_by_group,
)
from _helpers.twdb import WATER_LEVEL_MEMBERS, WATER_LEVEL_USECOLS, WATER_QUALITY_MEMBERS, WATER_QUALITY_USECOLS

gv.extension("bokeh")
S = init_session()

# %% [markdown]
# ## Step 2 — Discover wells
#
# Queries the GWDB well-inventory ArcGIS FeatureServer within the watersheds' bounding box, then
# keeps only wells **within** the watershed polygons — same bbox-then-spatial-join pattern as
# notebooks 3-4.

# %%
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)
bbox = list(watersheds_gdf.total_bounds)  # [min_lon, min_lat, max_lon, max_lat]; reused below

wells_gdf = fetch_gwdb_wells(bbox)
wells_in_area = gpd.sjoin(
    wells_gdf,
    watersheds_gdf[["huc8", "name", "geometry"]],
    predicate="within",
    how="inner",
)
print(f"{len(wells_gdf)} GWDB wells in the bounding box; {len(wells_in_area)} within the watersheds.")
save_dataframe(wells_in_area, S.data_dir / "twdb_waterdata" / "twdb_wells.parquet")
show(wells_in_area[["StateWellNumber", "CountyName", "WaterLevelObservationType", "WaterQualityAvailable", "name"]])

# %% [markdown]
# ## Step 3 — Download the nightly GWDB bulk file
#
# The ArcGIS layer above is inventory-only; the actual water-level/quality measurements live in a
# nightly full-state zip, cached locally for a week (like this project's other request caches) so
# re-running the notebook doesn't re-download ~81 MB every time.

# %%
zip_path = fetch_gwdb_zip(S.repo_root / "data_temp" / "gwdb_download.zip")
well_ids = set(wells_in_area["StateWellNumber"].dropna())
huc8_by_well = dict(zip(wells_in_area["StateWellNumber"], wells_in_area["huc8"]))
print(f"{zip_path} ({zip_path.stat().st_size:,} bytes); {len(well_ids)} wells to filter for")

# %% [markdown]
# ## Step 4 — Water levels
#
# Filters the four Major/Minor/Combination/OtherUnassigned water-level files down to our wells,
# streamed in chunks (the files are large statewide extracts).

# %%
water_levels_raw = fetch_gwdb_members(zip_path, WATER_LEVEL_MEMBERS, WATER_LEVEL_USECOLS, well_ids)
show(water_levels_raw.head())  # peek at the raw GWDB file shape before we tidy it

# %%
twdb_water_levels = tidy_gwdb_water_levels(water_levels_raw, huc8_by_well)
show(twdb_water_levels.head())
save_dataframe(twdb_water_levels, S.data_dir / "twdb_waterdata" / "twdb_water_levels.parquet")

# %% [markdown]
# ## Step 5 — Water quality
#
# Same filtering approach for the water-quality files; classification reuses `classify_parameter`
# on GWDB's `ParameterCode` (confirmed in the sandbox exploration to reuse USGS-style codes).

# %%
water_quality_raw = fetch_gwdb_members(zip_path, WATER_QUALITY_MEMBERS, WATER_QUALITY_USECOLS, well_ids)
show(water_quality_raw.head())  # peek at the raw GWDB file shape before we tidy it

# %%
twdb_water_quality = tidy_gwdb_water_quality(water_quality_raw, huc8_by_well)
show(twdb_water_quality.head())
save_dataframe(twdb_water_quality, S.data_dir / "twdb_waterdata" / "twdb_water_quality.parquet")

print(f"Wells by data type (of {len(wells_in_area)}):")
print(pd.Series({
    "water_level": twdb_water_levels["monitoring_location_id"].nunique(),
    "water_quality": twdb_water_quality["monitoring_location_id"].nunique(),
}).to_string())

# %% [markdown]
# ## Step 6 — Map wells by data availability
#
# Wells with water-level records, water-quality records, or both, over the watershed outlines.

# %%
level_ids = set(twdb_water_levels["monitoring_location_id"])
quality_ids = set(twdb_water_quality["monitoring_location_id"])
DATA_TYPE_COLORS = categorical_colors(["water_level", "water_quality"])
watershed_outlines = gv.Path(watersheds_gdf).opts(color="black", line_width=1.5)

wells_map = gvts.EsriWorldTopo * watershed_outlines
for label, ids in [("water_level", level_ids), ("water_quality", quality_ids)]:
    subset = wells_in_area[wells_in_area["StateWellNumber"].isin(ids)]
    if len(subset) == 0:
        continue
    wells_map = wells_map * gv.Points(
        subset, vdims=["StateWellNumber", "CountyName"], label=label,
    ).opts(color=DATA_TYPE_COLORS[label], size=7, line_color="white", tools=["hover"])

wells_map = wells_map.opts(
    data_aspect=1,
    title="TWDB GWDB wells by data type (click legend to toggle)",
    legend_position="right",
    hooks=[make_legend_clickable],
)
wells_map

# %% [markdown]
# ## Step 7 — Data availability

# %%
show(coverage(twdb_water_levels, "datetime"))

# %%
show(coverage(twdb_water_quality, "datetime"))

# %% [markdown]
# ## Step 8 — Trends (Mann–Kendall + Sen's slope)
#
# Per well × priority-parameter, annual **median** — water levels and quality samples are both
# irregular series, same treatment as notebooks 3-4's water-quality trends.

# %%
level_trends = trend_by_group(
    twdb_water_levels, ["monitoring_location_id", "priority_group"], "datetime", "water_elevation_ft", agg="median"
)
quality_trends = trend_by_group(
    twdb_water_quality, ["monitoring_location_id", "priority_group"], "datetime", "value", agg="median"
)
twdb_trends = pd.concat(
    [level_trends.assign(data_type="water_level"), quality_trends.assign(data_type="water_quality")],
    ignore_index=True,
)
twdb_trends["significant"] = twdb_trends["p"] < 0.05
save_dataframe(twdb_trends, S.data_dir / "twdb_waterdata" / "twdb_trends.parquet")
show(twdb_trends.round({"p": 4, "slope": 4}))

# %%
trend_chart = twdb_trends.dropna(subset=["slope"]).hvplot.bar(
    x="priority_group", y="slope", by="data_type",
    hover_cols=["monitoring_location_id", "trend", "p", "significant"],
    frame_height=360, rot=40,
    ylabel="Sen's slope (per year)", xlabel="",
    title="TWDB well trend rates by priority parameter (Sen's slope)", legend="top_right",
).opts(active_tools=[])
trend_chart

# %% [markdown]
# ## What's next
#
# Well inventory, water levels, water quality, and trends are saved under `data/twdb_waterdata/`.
# A future shared display notebook can compare USGS/TCEQ/TWDB trends side by side, and TWDB's
# coastal surface-water data (waterdatafortexas.org, relevant to the South Laguna Madre watershed)
# remains a candidate for a later round.
