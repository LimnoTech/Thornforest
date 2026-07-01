"""Shared helpers for the Thornforest notebooks.

Small, project-agnostic utilities reused across notebooks — kept here so each notebook
imports them rather than redefining them. The leading underscore means Quarto ignores this
file when rendering the site. (Candidate to grow into a shareable cross-project package.)

Usage in a notebook (run with the kernel's working directory at ``notebooks/``):

    from _helpers import find_repo_root, save_outputs, show
"""

import os
from dataclasses import dataclass
from pathlib import Path

import colorcet as cc
from dotenv import load_dotenv
from IPython.display import HTML


def find_repo_root(marker="pyproject.toml", start=None):
    """Walk up from `start` (default: the working directory) to the repo root, i.e. the first
    parent directory that contains `marker`. Lets notebooks build absolute paths to repo-level
    folders (data/, cache/, .env) regardless of where the kernel's working directory is."""
    start = Path(start) if start is not None else Path.cwd()
    for folder in [start, *start.parents]:
        if (folder / marker).exists():
            return folder
    return start


def save_outputs(df, parquet_path):
    """Save a (Geo)DataFrame two ways for transparency: parquet (compact, typed) + a CSV copy.

    - GeoDataFrame: GeoParquet + CSV with geometry written as WKT, geometry column moved to the
      end so the table reads cleanly in any software.
    - Plain pandas DataFrame (no geometry): a standard (non-Geo) parquet + CSV, columns unchanged.

    Side-effect helper — prints a confirmation and returns nothing (so it never accidentally
    renders a table when it is the last line of a notebook cell)."""
    has_geometry = getattr(df, "_geometry_column_name", None) is not None
    if has_geometry:
        name = df.geometry.name
        ordered = df[[c for c in df.columns if c != name] + [name]]
    else:
        ordered = df

    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_parquet(parquet_path)
    ordered.to_csv(parquet_path.with_suffix(".csv"), index=False)  # geometry -> WKT when GeoDataFrame

    try:
        shown = parquet_path.relative_to(find_repo_root())
    except ValueError:
        shown = parquet_path
    print(f"saved {len(ordered)} rows → {shown} (+ .csv)")


def show(df, height=360):
    """Display the *full* table in a fixed-height, **scrollable** box with a sticky header —
    renders the same in JupyterLab and in the exported HTML site (`to_html` emits every row)."""
    return HTML(
        "<style>.scroll-df thead th{position:sticky;top:0;background:#fff;"
        "box-shadow:inset 0 -1px 0 #ccc;}</style>"
        f'<div class="scroll-df" style="max-height:{height}px;overflow:auto;'
        'border:1px solid #ddd;border-radius:4px;">'
        f"{df.to_html()}</div>"
    )


# --- Session setup (shared by every notebook) ---------------------------------

@dataclass(frozen=True)
class Session:
    """Resolved per-notebook configuration returned by init_session()."""
    repo_root: Path
    data_dir: Path
    cache_file: str
    cache_expire_seconds: int
    api_key: str | None
    api_headers: dict


# --- Plot display defaults (shared by every notebook) -------------------------

PLOT_WIDTH = 600  # frame width (px) tuned to fit the Quarto cosmo content column incl. toolbar;
                  # see Task 3 verification — lower it (or widen body-width) if any page side-scrolls.


def set_plot_defaults(width=PLOT_WIDTH):
    """Project-wide HoloViews/Bokeh display defaults: a content-fitting frame width (so pages do
    not scroll sideways) and **scroll-zoom OFF by default** — pan is the active drag tool and
    wheel_zoom stays in the toolbar but inactive. Call AFTER the bokeh extension is loaded
    (e.g. gv.extension('bokeh'))."""
    import holoviews as hv

    hv.opts.defaults(
        hv.opts.Overlay(frame_width=width, active_tools=["pan"]),
        hv.opts.Points(frame_width=width, active_tools=["pan"]),
        hv.opts.Path(frame_width=width, active_tools=["pan"]),
        hv.opts.Polygons(frame_width=width, active_tools=["pan"]),
        hv.opts.Curve(frame_width=width, active_tools=["pan"]),
        hv.opts.QuadMesh(frame_width=width, active_tools=["pan"]),
        hv.opts.Image(frame_width=width, active_tools=["pan"]),
        hv.opts.HeatMap(frame_width=width, active_tools=["pan"]),
    )


def init_session(cache_expire_seconds: int = 7 * 24 * 3600) -> Session:
    """Load the optional USGS API key from .env, point HyRiver's request cache at the
    git-ignored cache/ folder, and return the resolved paths/headers as a Session.
    Safe to call without a .env (falls back to anonymous rate limits)."""
    repo_root = find_repo_root()
    load_dotenv(repo_root / ".env")
    api_key = os.getenv("API_USGS_PAT")
    api_headers = {"X-Api-Key": api_key} if api_key else {}
    cache_file = str(repo_root / "cache" / "aiohttp_cache.sqlite")
    os.environ.setdefault("HYRIVER_CACHE_NAME", cache_file)
    os.environ.setdefault("HYRIVER_CACHE_EXPIRE", str(cache_expire_seconds))
    print(
        "USGS API key loaded."
        if api_key
        else "No API key — using anonymous (lower) rate limits."
    )
    set_plot_defaults()
    return Session(
        repo_root=repo_root,
        data_dir=repo_root / "data",
        cache_file=cache_file,
        cache_expire_seconds=cache_expire_seconds,
        api_key=api_key,
        api_headers=api_headers,
    )


# --- Colors for *data* in figures (colorcet, NOT the LimnoTech brand) ----------

CATEGORICAL = cc.b_glasbey_category10  # distinct, colorblind-aware categorical hex list (Bokeh hex strings)


def categorical_colors(keys, palette=CATEGORICAL):
    """Map an ordered list of category keys -> hex colors, cycling the palette.
    Returns a dict {key: hex} for use as per-category colors in GeoViews layers."""
    keys = list(keys)
    return {key: palette[i % len(palette)] for i, key in enumerate(keys)}


# --- GeoViews/Bokeh helpers ---------------------------------------------------

def make_legend_clickable(plot, element):
    """Bokeh hook: clicking a legend entry hides/shows that layer (click_policy='hide')."""
    plot.state.legend.click_policy = "hide"


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


def save_datacube(ds, zarr_path, level=3):
    """Save an xarray datacube to **zarr v3** with an explicit Zstd compressor — the
    storage format for raster/gridded data (never parquet). Zarr v3 is required for
    Icechunk. Any inherited (zarr-v2 numcodecs) codecs are cleared first so the v3
    writer accepts the encoding. Returns the path."""
    import zarr

    zarr_path = Path(zarr_path)
    ds = ds.copy()
    for var in ds.variables:
        ds[var].encoding.clear()
    compressor = zarr.codecs.ZstdCodec(level=level)
    encoding = {v: {"compressors": (compressor,)} for v in ds.data_vars if ds[v].ndim > 0}
    zarr_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_zarr(zarr_path, mode="w", consolidated=True, encoding=encoding, zarr_format=3)
    return zarr_path


def water_year(dates):
    """Map dates to the USGS water year (Oct 1 – Sep 30), labeled by the ending
    calendar year (e.g. 2020-10-15 → WY2021). Returns an int array/Series."""
    import pandas as pd

    dt = pd.DatetimeIndex(pd.to_datetime(dates))
    return dt.year + (dt.month >= 10).astype(int)


def mk_sen_trend(series):
    """Mann–Kendall trend test + Sen's slope for a 1-D series (e.g. one water-year
    series). Returns {trend, p, slope, intercept, n}; slope is per time step
    (per year when the input is annual). NaNs are dropped; <4 points → 'insufficient'."""
    import numpy as np

    s = np.asarray(series, dtype=float)
    s = s[~np.isnan(s)]
    if len(s) < 4:
        return {"trend": "insufficient", "p": float("nan"),
                "slope": float("nan"), "intercept": float("nan"), "n": int(len(s))}
    import pymannkendall as mk

    r = mk.original_test(s)
    return {"trend": r.trend, "p": float(r.p), "slope": float(r.slope),
            "intercept": float(r.intercept), "n": int(len(s))}


def conus404_monthly_grid(watersheds, zarr_path, variables=None, verbose=True):
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
        cached = xr.open_zarr(zarr_path)
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


def zonal_by_huc8(grid_ds, watersheds, variables=None):
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


def pixel_trend(annual_da, dim="water_year"):
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
