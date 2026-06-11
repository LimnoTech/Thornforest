"""Shared helpers for the Thornforest notebooks.

Small, project-agnostic utilities reused across notebooks — kept here so each notebook
imports them rather than redefining them. The leading underscore means Quarto ignores this
file when rendering the site. (Candidate to grow into a shareable cross-project package.)

Usage in a notebook (run with the kernel's working directory at ``notebooks/``):

    from _helpers import find_repo_root, save_outputs, show
"""

from pathlib import Path

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
