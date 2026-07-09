"""Shared helpers for the Thornforest notebooks, organized into focused modules.

Import from the package root — the public API is re-exported here so notebooks use
`from _helpers import save_dataframe, show, init_session, ...` regardless of which module
a helper lives in. The leading underscore makes Quarto ignore this package when rendering.

Generic modules (session, io, viz, analysis, usgs, climate) are project-agnostic and take
project constants as arguments; Thornforest-specific constants live in `config`.
"""

from . import config
from .analysis import coverage, mk_sen_trend, trend_by_group, water_year
from .climate import conus404_monthly_grid, pixel_trend, zonal_by_huc8
from .config import CONUS404_VARIABLES, PLOT_WIDTH, PRIORITY_GROUPS, PRIORITY_NAMES, WATERSHEDS
from .io import load_dataframe, save_dataframe, save_datacube
from .session import Session, find_repo_root, init_session
from .usgs import (
    build_parameter_name_lookup,
    classify_parameter,
    fetch_daily,
    fetch_field,
    fetch_samples,
    station_parameters,
    tidy_daily,
    tidy_field,
    tidy_samples,
)
from .tceq import TCEQ_COLUMNS, fetch_wqp_results, tidy_wqp_results
from .twdb import (
    GWDB_BULK_URL,
    GWDB_COLUMNS_LEVELS,
    GWDB_COLUMNS_QUALITY,
    GWDB_FEATURESERVER_URL,
    WATER_LEVEL_MEMBERS,
    WATER_LEVEL_USECOLS,
    WATER_QUALITY_MEMBERS,
    WATER_QUALITY_USECOLS,
    fetch_gwdb_members,
    fetch_gwdb_wells,
    fetch_gwdb_zip,
    tidy_gwdb_water_levels,
    tidy_gwdb_water_quality,
)
from .viz import (
    CATEGORICAL,
    categorical_colors,
    make_legend_clickable,
    set_plot_defaults,
    show,
)

__all__ = [
    "config", "CONUS404_VARIABLES", "PLOT_WIDTH", "PRIORITY_GROUPS", "PRIORITY_NAMES", "WATERSHEDS",
    "find_repo_root", "Session", "init_session",
    "save_dataframe", "load_dataframe", "save_datacube",
    "show", "set_plot_defaults", "CATEGORICAL", "categorical_colors", "make_legend_clickable",
    "water_year", "mk_sen_trend", "coverage", "trend_by_group",
    "classify_parameter", "build_parameter_name_lookup", "station_parameters",
    "fetch_daily", "fetch_samples", "fetch_field", "tidy_daily", "tidy_samples", "tidy_field",
    "TCEQ_COLUMNS", "fetch_wqp_results", "tidy_wqp_results",
    "GWDB_FEATURESERVER_URL", "GWDB_BULK_URL", "WATER_LEVEL_MEMBERS", "WATER_QUALITY_MEMBERS",
    "WATER_LEVEL_USECOLS", "WATER_QUALITY_USECOLS", "GWDB_COLUMNS_LEVELS", "GWDB_COLUMNS_QUALITY",
    "fetch_gwdb_wells", "fetch_gwdb_zip", "fetch_gwdb_members",
    "tidy_gwdb_water_levels", "tidy_gwdb_water_quality",
    "conus404_monthly_grid", "zonal_by_huc8", "pixel_trend",
]
