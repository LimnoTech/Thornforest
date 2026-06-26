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


def find_repo_root(marker="pixi.toml", start=None):
    """Walk up from `start` (default: the working directory) to the repo root, i.e. the first
    parent directory that contains `marker`. Lets notebooks build absolute paths to repo-level
    folders (data/, cache/, .env) regardless of where the kernel's working directory is."""
    start = Path(start) if start is not None else Path.cwd()
    for folder in [start, *start.parents]:
        if (folder / marker).exists():
            return folder
    return start


def save_outputs(gdf, parquet_path):
    """Save a GeoDataFrame two ways: as GeoParquet (compact, typed) and as a CSV copy
    (human-readable, geometry written as WKT) for transparency. The (often long) geometry
    column is moved to the **end** so the table is easier to read in any software. This is a
    side-effect helper — it prints a confirmation and returns nothing (so it never accidentally
    renders a table when it is the last line of a notebook cell)."""
    geometry_col = gdf.geometry.name
    ordered = gdf[[c for c in gdf.columns if c != geometry_col] + [geometry_col]]

    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_parquet(parquet_path)
    ordered.to_csv(parquet_path.with_suffix(".csv"), index=False)  # geometry -> WKT

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
