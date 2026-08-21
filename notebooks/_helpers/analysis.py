"""Generic, source-agnostic analysis utilities (water-year labeling, trend tests, coverage
summaries) shared across notebooks. These take data as arguments and hold no project- or
source-specific constants."""

from __future__ import annotations

import pandas as pd


def _warn_missing_huc8(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Warn (don't silently drop) if the huc8 join produced NaN — signals a station-id mismatch."""
    missing = df["huc8"].isna()
    if missing.any():
        ids = sorted(df.loc[missing, "monitoring_location_id"].unique())[:10]
        print(f"WARNING: {int(missing.sum())} {label} rows had no huc8 match; unmatched ids: {ids}")
    return df


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
        return {
            "trend": "insufficient",
            "p": float("nan"),
            "slope": float("nan"),
            "intercept": float("nan"),
            "n": int(len(s)),
        }
    import pymannkendall as mk

    r = mk.original_test(s)
    return {
        "trend": r.trend,
        "p": float(r.p),
        "slope": float(r.slope),
        "intercept": float(r.intercept),
        "n": int(len(s)),
    }


def trend_by_group(
    df: pd.DataFrame,
    group_cols: list[str],
    time_col: str,
    value_col: str,
    agg: str = "median",
) -> pd.DataFrame:
    """Resample value_col to one value per calendar year within each group_cols combo
    (coercing to numeric first), then run mk_sen_trend on the annual series. Returns
    one row per group with trend/p/slope/intercept/n alongside the group_cols."""
    empty_columns = [*group_cols, "trend", "p", "slope", "intercept", "n"]
    if df.empty:
        return pd.DataFrame(columns=empty_columns)

    rows = []
    for keys, g in df.groupby(group_cols):
        keys = keys if isinstance(keys, tuple) else (keys,)
        annual = (
            g.assign(
                _year=pd.to_datetime(g[time_col]).dt.year,
                _value=pd.to_numeric(g[value_col], errors="coerce"),
            )
            .groupby("_year")["_value"]
            .agg(agg)
        )
        r = mk_sen_trend(annual.to_numpy())
        rows.append({**dict(zip(group_cols, keys)), **r})
    return pd.DataFrame(rows, columns=empty_columns)


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
