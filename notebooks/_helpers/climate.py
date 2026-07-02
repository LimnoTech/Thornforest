"""CONUS404 climate helpers: load the monthly gridded datacube (clipped to the watersheds),
compute area-weighted per-watershed zonal means, and per-grid-cell trends."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .analysis import mk_sen_trend
from .io import save_datacube

if TYPE_CHECKING:
    import geopandas as gpd
    import pandas as pd
    import xarray as xr

# --- CONUS404 climate (NB3) ---------------------------------------------------
# Heavy imports (xarray/pyproj/xvec/pymannkendall) are done lazily inside the
# functions so NB1/NB2, which never call these, don't pay the import cost.
# Storage convention: the gridded cube is an xarray datacube saved to ZARR;
# tabular summaries derived from it are saved to parquet (in the notebook).

CONUS404_MONTHLY_ZARR = "s3://hytest/conus404/conus404_monthly.zarr"
CONUS404_ENDPOINT = "https://usgs.osn.mghpcc.org"

# 11 variables for a (near-)closed land-surface water balance + forcing.
# Monthly AC* values are MONTHLY accumulations (mm). SMOIS is 4-D (soil layers)
# — the surface layer is taken as a representative state.
CONUS404_VARS = [
    "PREC_ACC_NC", "ACETLSM", "ACRUNSB", "ACRUNSF", "RECH",  # fluxes (mm/month)
    "SMOIS", "SNOW", "CANWAT",                                # storage states
    "T2", "TD2", "Q2",                                        # forcing
]


def conus404_monthly_grid(
    watersheds: gpd.GeoDataFrame,
    zarr_path: Path | str,
    variables=None,
    verbose: bool = True,
) -> xr.Dataset:
    """Monthly CONUS404 datacube clipped to the watersheds' bounding box.

    Load-if-exists: if `zarr_path` already holds the cube it is opened and returned
    (fast); otherwise the monthly Zarr is opened from the USGS OSN pod, the
    watersheds are reprojected to the grid CRS, the 11 variables are sliced to the
    bbox, the SMOIS soil-layer dim is collapsed to the surface layer, the grid
    mapping (`crs`) is retained, and the result is **saved as a zarr datacube**
    (the storage convention for raster/xarray data — never parquet).

    `watersheds` is a GeoDataFrame with geometry. Returns an `xr.Dataset` with dims
    (time, y, x) in raw CONUS404 units (fluxes mm/month; T2/TD2 K; SMOIS m³/m³)."""
    import xarray as xr

    zarr_path = Path(zarr_path)
    if zarr_path.exists():
        cached = xr.open_zarr(zarr_path, consolidated=False)
        if verbose:  # note the cached var set — a changed `variables` arg is ignored on a cache hit
            cached_vars = [v for v in cached.data_vars if v != "crs"]
            print(f"loading cached datacube ({len(cached_vars)} vars) → {zarr_path.name}")
        return cached

    import pyproj
    import xvec  # noqa: F401  (registers .xvec; ensures the accessor is importable downstream)

    variables = list(variables) if variables is not None else CONUS404_VARS
    if verbose:
        print(f"fetching CONUS404 monthly cube ({len(variables)} vars) from OSN…")

    ds = xr.open_zarr(
        CONUS404_MONTHLY_ZARR, consolidated=True,
        storage_options={"anon": True, "client_kwargs": {"endpoint_url": CONUS404_ENDPOINT}},
    )
    crs = pyproj.CRS.from_cf(ds["crs"].attrs)
    ws = watersheds.to_crs(crs)
    xmin, ymin, xmax, ymax = ws.total_bounds
    ysl = slice(ymin, ymax) if float(ds.y[0]) < float(ds.y[-1]) else slice(ymax, ymin)

    sub = ds[variables].sel(x=slice(xmin, xmax), y=ysl)
    for v in variables:  # collapse any non-(time,x,y) dim (e.g. SMOIS soil layers) to surface
        for d in [dim for dim in sub[v].dims if dim not in ("time", "x", "y")]:
            sub[v] = sub[v].isel({d: 0})
    sub["crs"] = ds["crs"]  # retain the grid mapping for reprojection / zonal stats

    sub = sub.load()
    save_datacube(sub, zarr_path)  # zarr v3 + Zstd (storage convention for datacubes)
    if verbose:
        print(f"saved datacube {dict(sub.sizes)} → {zarr_path.name}")
    return sub


def zonal_by_huc8(
    grid_ds: xr.Dataset, watersheds: gpd.GeoDataFrame, variables=None
) -> pd.DataFrame:
    """Area-weighted (fractional-coverage) zonal mean of a CONUS404 datacube over
    each HUC-8 polygon. Returns a tidy DataFrame: date × huc8 × name × variables.
    Uses `xvec`/`exactextract`; `watersheds` needs `huc8`, `name`, geometry."""
    import pyproj
    import xvec  # noqa: F401

    variables = list(variables) if variables is not None else CONUS404_VARS
    crs = pyproj.CRS.from_cf(grid_ds["crs"].attrs)
    ws = watersheds.to_crs(crs)
    za = grid_ds[variables].xvec.zonal_stats(
        ws.geometry, x_coords="x", y_coords="y", stats="mean", method="exactextract"
    ).load()
    za = (za.assign_coords(huc8=("geometry", ws["huc8"].values),
                           name=("geometry", ws["name"].values))
            .swap_dims({"geometry": "huc8"}).drop_vars("geometry"))
    df = za.to_dataframe().reset_index()
    df = df.drop(columns=[c for c in ("index_right", "spatial_ref") if c in df.columns])
    return df.rename(columns={"time": "date"}).sort_values(["huc8", "date"]).reset_index(drop=True)


def pixel_trend(annual_da: xr.DataArray, dim: str = "water_year") -> xr.Dataset:
    """Per-cell Mann–Kendall trend + Sen's slope along `dim` (e.g. a water-year
    DataArray with dims (water_year, y, x)). Returns an `xr.Dataset` with `slope`
    (per year) and `p` (Mann–Kendall p-value) grids over the remaining dims."""
    import numpy as np
    import xarray as xr

    def _slope_p(series):
        r = mk_sen_trend(series)
        return np.array([r["slope"], r["p"]], dtype=float)

    out = xr.apply_ufunc(
        _slope_p, annual_da,
        input_core_dims=[[dim]], output_core_dims=[["stat"]],
        exclude_dims={dim}, vectorize=True,
        dask="parallelized", output_dtypes=[float],
        dask_gufunc_kwargs={"output_sizes": {"stat": 2}},
    )
    out = out.assign_coords(stat=["slope", "p"])
    return out.to_dataset(dim="stat")
