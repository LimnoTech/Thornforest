"""Saving curated outputs to disk: tabular (Geo)DataFrames as GeoParquet + a CSV copy, and
xarray datacubes as zarr v3."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .session import find_repo_root

if TYPE_CHECKING:
    import pandas as pd
    import xarray as xr


def save_dataframe(df: pd.DataFrame, parquet_path: Path | str) -> None:
    """Save a (Geo)DataFrame two ways for transparency: parquet (compact, typed) + a CSV copy.

    - GeoDataFrame: GeoParquet + CSV with geometry written as WKT, geometry column moved to the
      end so the table reads cleanly in any software.
    - Plain pandas DataFrame (no geometry): a standard (non-Geo) parquet + CSV, columns unchanged.

    Side-effect helper — prints a confirmation and returns nothing (so it never accidentally
    renders a table when it is the last line of a notebook cell)."""
    import geopandas as gpd

    if isinstance(df, gpd.GeoDataFrame) and df.active_geometry_name is not None:
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


def save_datacube(ds: xr.Dataset, zarr_path: Path | str, level: int = 3) -> Path:
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
