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
# # 3 · CONUS404 Climate — Spatial Patterns & Water-Balance Trends
#
# This notebook builds a long-term **climate and water-balance** record for the three South-Texas
# HUC-8 watersheds from **CONUS404** — a 4-km hourly reanalysis of the conterminous US (NCAR/USGS,
# WRF model), here used at its **monthly** aggregation. CONUS404 gives a *physically consistent,
# closed* land-surface water budget on a single grid that covers all three watersheds —
# **including the Mexican portion** of the Lower Rio Grande that US-only stream/water-quality
# products miss.
#
# The pipeline is:
#
# 1. read the watershed boundaries from notebook 1;
# 2. open the CONUS404 **monthly** Zarr store (anonymous, cloud-hosted) and clip it to our area as
#    a **gridded datacube** (saved to zarr — the storage format for raster data);
# 3. summarize **per watershed**: water-year totals/means and a simple water balance (P − ET − Q),
#    with long-term **trends** (Mann–Kendall + Sen's slope);
# 4. summarize **per grid cell**: climatology and per-cell trends, to see **spatial patterns and
#    how they change over time**;
# 5. map and chart the results interactively.
#
# > **Storage convention.** Gridded data (datacubes) are saved as **zarr**; tabular summaries are
# > saved as **parquet** (+ CSV). The ~80 MB raw monthly cube is *git-ignored and regenerated*
# > from the cloud; the small derived products (climatology/trend grids, per-watershed tables) are
# > committed.

# %% [markdown]
# ## Step 1 — Imports and setup

# %%
import geopandas as gpd
import pyproj
import xarray as xr
import rioxarray  # noqa: F401  (registers the .rio accessor for reprojection)

import holoviews as hv
import hvplot.pandas  # noqa: F401  (registers .hvplot on DataFrames)
import hvplot.xarray  # noqa: F401  (registers .hvplot on DataArrays)
import geoviews as gv

from _helpers import (
    init_session,
    show,
    save_datacube,
    categorical_colors,
    make_legend_clickable,
    conus404_monthly_grid,
    zonal_by_huc8,
    water_year,
    mk_sen_trend,
    pixel_trend,
)

gv.extension("bokeh")
S = init_session()

# Stable watershed order + consistent data colors across all figures.
WATERSHED_ORDER = ["South Laguna Madre", "Los Olmos", "Lower Rio Grande"]
WATERSHED_COLORS = categorical_colors(WATERSHED_ORDER)

# %% [markdown]
# ## Step 2 — Watersheds and the CONUS404 variables
#
# We reuse the HUC-8 boundaries saved by notebook 1. The table lists the 11 CONUS404 variables we
# aggregate — the fluxes that make up the water balance, the storage states, and the
# temperature/humidity forcing. Monthly flux variables are **monthly totals** (mm).

# %%
boundaries_path = S.data_dir / "hydrography" / "huc8_watersheds.parquet"
if not boundaries_path.exists():
    raise FileNotFoundError(
        f"{boundaries_path} not found — run notebook 1 (1_usgs_hydrography) first."
    )
watersheds_gdf = gpd.read_parquet(boundaries_path)

import pandas as pd  # noqa: E402  (kept local to this descriptive cell)

conus404_variables = pd.DataFrame(
    [
        ("PREC_ACC_NC", "Precipitation", "mm/month", "flux"),
        ("ACETLSM", "Total evapotranspiration", "mm/month", "flux"),
        ("ACRUNSB", "Surface runoff", "mm/month", "flux"),
        ("ACRUNSF", "Subsurface runoff", "mm/month", "flux"),
        ("RECH", "Water-table recharge", "mm/month", "flux"),
        ("SMOIS", "Soil moisture (surface layer)", "m³/m³", "storage"),
        ("SNOW", "Snow water equivalent", "mm", "storage"),
        ("CANWAT", "Canopy water", "mm", "storage"),
        ("T2", "Air temperature (2 m)", "K", "forcing"),
        ("TD2", "Dewpoint (2 m)", "K", "forcing"),
        ("Q2", "Water-vapor mixing ratio (2 m)", "kg/kg", "forcing"),
    ],
    columns=["variable", "description", "units", "role"],
)
show(conus404_variables, height=320)

# %% [markdown]
# ## Step 3 — Monthly gridded datacube
#
# `conus404_monthly_grid` opens the monthly Zarr store, reprojects the watersheds to the model grid,
# clips the 11 variables to our bounding box, and **saves the result as a zarr datacube**. It
# **loads the saved cube if it already exists** (fast); otherwise it fetches from the cloud (slow,
# a few minutes) and saves. The cube has dimensions (time, y, x) over 540 months (water years
# 1980–2024).

# %%
grid_path = S.data_dir / "climate" / "conus404_monthly_grid.zarr"
grid = conus404_monthly_grid(watersheds_gdf, grid_path)
grid = grid.assign_coords(water_year=("time", water_year(grid["time"].values)))
grid_crs = pyproj.CRS.from_cf(grid["crs"].attrs)
print(
    f"datacube {dict(grid.sizes)} | {str(grid.time.values[0])[:7]} → {str(grid.time.values[-1])[:7]} "
    f"| grid CRS: {grid_crs.name}"
)

# %% [markdown]
# ## Step 4 — Per-watershed water-year balance
#
# We take an **area-weighted zonal mean** of the cube over each watershed (`xvec` +
# `exactextract`, using fractional cell coverage), then aggregate to the **water year**
# (Oct 1 – Sep 30, labeled by the ending year): fluxes are **summed** to annual totals (mm/yr),
# storage/forcing are **averaged**. Total runoff `Q = surface + subsurface`; the simple balance
# **`P − ET − Q`** has a residual equal to the change in stored water (soil + recharge).

# %%
FLUX_SUM = ["PREC_ACC_NC", "ACETLSM", "ACRUNSB", "ACRUNSF", "RECH"]
STATE_MEAN = ["SMOIS", "SNOW", "CANWAT", "T2", "TD2", "Q2"]

monthly = zonal_by_huc8(grid, watersheds_gdf)
monthly["water_year"] = water_year(monthly["date"])

grouped = monthly.groupby(["huc8", "name", "water_year"])
wy = grouped[FLUX_SUM].sum().join(grouped[STATE_MEAN].mean())
wy["n_months"] = grouped.size()
wy = wy.reset_index()

complete = wy["n_months"] == 12  # keep only full water years (all do, but guard anyway)
print(f"dropping {int((~complete).sum())} incomplete water year(s)")
wy = wy[complete].copy()

wy = wy.rename(
    columns={
        "PREC_ACC_NC": "precip_mm", "ACETLSM": "et_mm",
        "ACRUNSB": "surf_runoff_mm", "ACRUNSF": "subsurf_runoff_mm", "RECH": "recharge_mm",
        "SMOIS": "soil_moisture_m3m3", "SNOW": "swe_mm", "CANWAT": "canopy_mm", "Q2": "q2_kgkg",
    }
)
wy["runoff_mm"] = wy["surf_runoff_mm"] + wy["subsurf_runoff_mm"]
wy["t2_degc"] = wy["T2"] - 273.15
wy["td2_degc"] = wy["TD2"] - 273.15
wy["balance_mm"] = wy["precip_mm"] - wy["et_mm"] - wy["runoff_mm"]
wy = wy.drop(columns=["T2", "TD2"]).sort_values(["name", "water_year"]).reset_index(drop=True)

wy = wy[[
    "huc8", "name", "water_year", "precip_mm", "et_mm", "runoff_mm",
    "surf_runoff_mm", "subsurf_runoff_mm", "recharge_mm", "balance_mm",
    "soil_moisture_m3m3", "swe_mm", "canopy_mm", "t2_degc", "td2_degc", "q2_kgkg", "n_months",
]]

wy_path = S.data_dir / "climate" / "conus404_wateryear_by_huc8.parquet"
wy_path.parent.mkdir(parents=True, exist_ok=True)
wy.to_parquet(wy_path)
wy.to_csv(wy_path.with_suffix(".csv"), index=False)
print(f"saved {len(wy)} water-year rows → {wy_path.name} (+ .csv)")
show(wy.round(3))

# %% [markdown]
# ### Long-term averages per watershed
#
# Mean annual water balance over the full record — a check that the budget is sensible
# (precipitation ≈ evapotranspiration + runoff in this semi-arid region, the small remainder going
# to soil/groundwater storage).

# %%
balance_means = (
    wy.groupby("name")[["precip_mm", "et_mm", "runoff_mm", "recharge_mm", "balance_mm", "t2_degc"]]
    .mean()
    .reindex(WATERSHED_ORDER)
    .round(1)
)
show(balance_means.reset_index())

# %% [markdown]
# ## Step 5 — Per-watershed trends (Mann–Kendall + Sen's slope)
#
# For each watershed and water-year series we run the **Mann–Kendall** test (is there a monotonic
# trend?) and estimate **Sen's slope** (the robust per-year rate of change). Trends with *p* < 0.05
# are flagged significant.

# %%
TREND_TERMS = {
    "precip_mm": "Precipitation (mm/yr)",
    "et_mm": "Evapotranspiration (mm/yr)",
    "runoff_mm": "Runoff (mm/yr)",
    "recharge_mm": "Recharge (mm/yr)",
    "balance_mm": "P − ET − Q (mm/yr)",
    "soil_moisture_m3m3": "Surface soil moisture (m³/m³)",
    "t2_degc": "Mean temperature (°C)",
}

trend_rows = []
for (huc8, name), grp in wy.sort_values("water_year").groupby(["huc8", "name"]):
    for column, label in TREND_TERMS.items():
        r = mk_sen_trend(grp[column].values)
        trend_rows.append({
            "huc8": huc8, "name": name, "variable": label, "column": column,
            "trend": r["trend"], "p_value": r["p"],
            "slope_per_year": r["slope"], "n_years": r["n"],
        })
trends = pd.DataFrame(trend_rows)
trends["significant"] = trends["p_value"] < 0.05

trends_path = S.data_dir / "climate" / "conus404_trends_by_huc8.parquet"
trends.to_parquet(trends_path)
trends.to_csv(trends_path.with_suffix(".csv"), index=False)
print(f"saved {len(trends)} trend rows → {trends_path.name} (+ .csv)")
show(trends.round({"p_value": 4, "slope_per_year": 4}))

# %% [markdown]
# ## Step 6 — Spatial patterns: per-cell climatology and trends
#
# Now we keep the **full grid**. For each cell we build water-year series (fluxes summed, states
# averaged), take the long-term mean (**climatology**) and the per-cell **Mann–Kendall/Sen's
# slope** (**trend**). Both are saved as zarr datacubes (the small, committed derived products).

# %%
import numpy as np  # noqa: E402  (local to this analysis cell)

# Keep only complete water years (12 months) before aggregating — mirrors the per-watershed
# guard in Step 4 so the gridded climatology/trends never count a partial year as a full one.
wy_values = grid["water_year"].values
unique_wy, counts = np.unique(wy_values, return_counts=True)
complete_wy = unique_wy[counts == 12]
grid_full = grid.isel(time=np.flatnonzero(np.isin(wy_values, complete_wy)))
print(f"using {len(complete_wy)} complete water years "
      f"(dropped {len(unique_wy) - len(complete_wy)} partial)")

flux_wy = grid_full[FLUX_SUM].groupby("water_year").sum()
state_wy = grid_full[STATE_MEAN].groupby("water_year").mean()

annual = xr.Dataset({
    "precip_mm": flux_wy["PREC_ACC_NC"],
    "et_mm": flux_wy["ACETLSM"],
    "runoff_mm": flux_wy["ACRUNSB"] + flux_wy["ACRUNSF"],
    "recharge_mm": flux_wy["RECH"],
    "t2_degc": state_wy["T2"] - 273.15,
    "soil_moisture_m3m3": state_wy["SMOIS"],
}).load()

# Climatology: mean over all water years, per cell.
climatology = annual.mean("water_year")
climatology["crs"] = grid["crs"]
save_datacube(climatology, S.data_dir / "climate" / "conus404_climatology_grid.zarr")

# Per-cell trends: Sen's slope (per year) + Mann–Kendall p-value for each term.
trend_grid = xr.Dataset()
for term in annual.data_vars:
    t = pixel_trend(annual[term])
    trend_grid[f"{term}_slope"] = t["slope"]
    trend_grid[f"{term}_p"] = t["p"]
trend_grid["crs"] = grid["crs"]
save_datacube(trend_grid, S.data_dir / "climate" / "conus404_trends_grid.zarr")
print(f"climatology vars: {list(climatology.data_vars)}")
print(f"trend grid vars: {list(trend_grid.data_vars)}")


# %% [markdown]
# ## Step 7 — Maps
#
# We reproject the small grid to latitude/longitude and draw it over the watershed outlines on a
# light basemap. **Climatology** maps use sequential colors; **trend** maps use a diverging color
# scale centered on zero (so red/blue shows drying/wetting or cooling/warming).

# %%
def spatial_map(da2d, cmap, title, clabel, diverging=False):
    """Reproject one (y, x) grid to EPSG:4326 and render a tiled quadmesh map with the
    watershed outlines on top. Diverging maps are symmetric about zero."""
    import numpy as np

    da = da2d.rio.write_crs(grid_crs).rio.reproject("EPSG:4326")
    clim = None
    if diverging:
        vmax = float(np.nanmax(np.abs(da.values)))
        clim = (-vmax, vmax)
    quad = da.hvplot.quadmesh(
        x="x", y="y", geo=True, tiles="CartoLight", cmap=cmap, clim=clim,
        data_aspect=1, clabel=clabel, title=title,
        xlabel="", ylabel="", colorbar=True,
    )
    return quad * gv.Path(watersheds_gdf).opts(color="black", line_width=1.2)


# %% [markdown]
# ### Climatology — mean annual precipitation, ET, and temperature

# %%
climatology_maps = (
    spatial_map(climatology["precip_mm"], "blues", "Mean annual precipitation", "mm/yr")
    + spatial_map(climatology["et_mm"], "YlOrBr", "Mean annual ET", "mm/yr")
    + spatial_map(climatology["t2_degc"], "plasma", "Mean annual temperature", "°C")
).cols(1)
climatology_maps

# %% [markdown]
# ### Trends — where it is getting wetter/drier and warmer
#
# Per-cell Sen's slope over water years 1980–2024.

# %%
trend_maps = (
    spatial_map(trend_grid["precip_mm_slope"], "RdBu", "Precipitation trend", "mm/yr per year",
                diverging=True)
    + spatial_map(trend_grid["t2_degc_slope"], "RdBu_r", "Temperature trend", "°C per year",
                  diverging=True)
).cols(1)
trend_maps

# %% [markdown]
# ## Step 8 — Charts
#
# ### Annual water balance per watershed
#
# Precipitation, evapotranspiration, and runoff by water year. Click a legend entry to hide/show
# a line.

# %%
BALANCE_SERIES = {"precip_mm": "Precipitation", "et_mm": "ET", "runoff_mm": "Runoff"}
SERIES_COLORS = categorical_colors(list(BALANCE_SERIES.values()))

balance_panels = []
for name in WATERSHED_ORDER:
    sub = wy[wy["name"] == name]
    overlay = hv.Overlay([
        sub.hvplot.line(x="water_year", y=col, label=label).opts(color=SERIES_COLORS[label])
        for col, label in BALANCE_SERIES.items()
    ])
    balance_panels.append(overlay.opts(title=name, ylabel="mm / water year", xlabel="water year"))

balance_fig = hv.Layout(balance_panels).cols(1).opts(
    hv.opts.Overlay(frame_height=210, legend_position="right",
                    active_tools=["pan"], hooks=[make_legend_clickable]),
)
balance_fig

# %% [markdown]
# ### Warming signal — mean annual temperature

# %%
temp_fig = wy.hvplot.line(
    x="water_year", y="t2_degc", by="name",
    color=[WATERSHED_COLORS[n] for n in WATERSHED_ORDER],
    frame_height=300,
    ylabel="mean temperature (°C)", xlabel="water year",
    title="Mean annual 2 m air temperature", legend="right",
).opts(active_tools=["pan"], hooks=[make_legend_clickable])
temp_fig

# %% [markdown]
# ### Trend rates (Sen's slope) per watershed
#
# Per-year rate of change for each water-balance term. Hover for the Mann–Kendall direction and
# *p*-value; bars with *p* < 0.05 are statistically significant.

# %%
trend_fig = trends.hvplot.bar(
    x="variable", y="slope_per_year", by="name",
    color=[WATERSHED_COLORS[n] for n in WATERSHED_ORDER],
    hover_cols=["trend", "p_value", "significant"],
    frame_height=360, rot=40,
    ylabel="Sen's slope (per year)", xlabel="",
    title="Long-term trend rates by watershed (Sen's slope)", legend="top_right",
).opts(active_tools=[])
trend_fig

# %% [markdown]
# ## What's next
#
# The gridded cube (zarr), per-cell climatology/trend grids (zarr), and per-watershed water-year &
# trend tables (parquet/CSV) are saved under `data/climate/`. Next steps could compare these
# modeled balances against the USGS gauge records discovered in notebook 3, or bring in additional
# CONUS404 variables (snow processes, radiation) for a fuller energy/water budget.
