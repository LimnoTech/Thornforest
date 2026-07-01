"""Generic, source-agnostic analysis utilities (water-year labeling, trend tests, coverage
summaries) shared across notebooks. These take data as arguments and hold no project- or
source-specific constants."""

from __future__ import annotations

import pandas as pd


def water_year(dates) -> pd.Series:
    """Map dates to the USGS water year (Oct 1 – Sep 30), labeled by the ending
    calendar year (e.g. 2020-10-15 → WY2021). Returns an int array/Series."""
    dt = pd.DatetimeIndex(pd.to_datetime(dates))
    return dt.year + (dt.month >= 10).astype(int)


def mk_sen_trend(series) -> dict:
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


def coverage(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """Record count + first/last date per station × priority group."""
    t = pd.to_datetime(df[time_col])
    out = (
        df.assign(_t=t)
        .groupby(["monitoring_location_id", "priority_group"])["_t"]
        .agg(n="size", start="min", end="max")
        .reset_index()
        .sort_values(["priority_group", "monitoring_location_id"])
    )
    return out
