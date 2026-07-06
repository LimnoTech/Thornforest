"""Display and figure helpers: scrollable full-height tables, project-wide HoloViews/Bokeh
display defaults, categorical data colors, and a click-to-toggle legend hook."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import colorcet as cc
from IPython.display import HTML

from .config import PLOT_WIDTH

if TYPE_CHECKING:
    import pandas as pd


def show(df: pd.DataFrame, height: int = 360) -> HTML:
    """Display the *full* table in a fixed-height, **scrollable** box with a sticky header —
    renders the same in JupyterLab and in the exported HTML site (`to_html` emits every row)."""
    return HTML(
        "<style>.scroll-df thead th{position:sticky;top:0;background:#fff;"
        "box-shadow:inset 0 -1px 0 #ccc;}</style>"
        f'<div class="scroll-df" style="max-height:{height}px;overflow:auto;'
        'border:1px solid #ddd;border-radius:4px;">'
        f"{df.to_html()}</div>"
    )


def set_plot_defaults(width: int = PLOT_WIDTH) -> None:
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


# --- Colors for *data* in figures (colorcet, NOT the LimnoTech brand) ----------

CATEGORICAL = cc.b_glasbey_category10  # distinct, colorblind-aware categorical hex list (Bokeh hex strings)


def categorical_colors(keys: Iterable, palette: list[str] = CATEGORICAL) -> dict:
    """Map an ordered list of category keys -> hex colors, cycling the palette.
    Returns a dict {key: hex} for use as per-category colors in GeoViews layers."""
    keys = list(keys)
    return {key: palette[i % len(palette)] for i, key in enumerate(keys)}


# --- GeoViews/Bokeh helpers ---------------------------------------------------

def make_legend_clickable(plot, element) -> None:
    """Bokeh hook: clicking a legend entry hides/shows that layer (click_policy='hide')."""
    plot.state.legend.click_policy = "hide"
