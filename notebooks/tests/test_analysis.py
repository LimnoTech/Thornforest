import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import coverage, mk_sen_trend, trend_by_group, water_year


def test_water_year_october_boundary():
    wy = water_year(pd.to_datetime(["2020-09-30", "2020-10-01", "2021-01-15"]))
    assert list(wy) == [2020, 2021, 2021]


def test_mk_sen_trend_insufficient_under_four_points():
    assert mk_sen_trend([1, 2, 3])["trend"] == "insufficient"


def test_mk_sen_trend_detects_increase():
    r = mk_sen_trend([1, 2, 3, 4, 5, 6])
    assert r["trend"] == "increasing"
    assert r["slope"] > 0


def test_coverage_counts_and_span_per_group():
    df = pd.DataFrame({
        "monitoring_location_id": ["A", "A", "A"],
        "priority_group": ["discharge", "discharge", "discharge"],
        "date": pd.to_datetime(["2001-01-01", "2002-01-01", "2003-01-01"]),
    })
    out = coverage(df, "date")
    row = out.iloc[0]
    assert row["n"] == 3
    assert row["start"].year == 2001 and row["end"].year == 2003


def test_trend_by_group_one_row_per_group_with_correct_trend():
    df = pd.DataFrame({
        "station": ["A"] * 6 + ["B"] * 3,
        "date": pd.to_datetime(
            ["2001-01-01", "2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01", "2006-01-01"]
            + ["2001-01-01", "2002-01-01", "2003-01-01"]
        ),
        "value": [1, 2, 3, 4, 5, 6, 10, 10, 10],
    })
    out = trend_by_group(df, ["station"], "date", "value")
    assert set(out.columns) == {"station", "trend", "p", "slope", "intercept", "n"}
    a = out[out["station"] == "A"].iloc[0]
    b = out[out["station"] == "B"].iloc[0]
    assert a["trend"] == "increasing"
    assert a["n"] == 6
    assert b["trend"] == "insufficient"  # only 3 points, below mk_sen_trend's minimum of 4


def test_trend_by_group_agg_choice_changes_intercept():
    # Three readings in 2001 (1, 1, 100) make mean (34) and median (1) diverge sharply.
    df = pd.DataFrame({
        "station": ["A"] * 7,
        "date": pd.to_datetime([
            "2001-01-01", "2001-04-01", "2001-08-01",
            "2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01",
        ]),
        "value": [1.0, 1.0, 100.0, 2.0, 3.0, 4.0, 5.0],
    })
    median_out = trend_by_group(df, ["station"], "date", "value", agg="median")
    mean_out = trend_by_group(df, ["station"], "date", "value", agg="mean")
    # Sen's slope (median-of-pairwise-slopes) is robust to this single outlier, so both
    # aggregations land on the same slope — but the intercept still shifts with it.
    assert median_out.iloc[0]["intercept"] != mean_out.iloc[0]["intercept"]


def test_trend_by_group_agg_choice_changes_slope():
    # Opposite-signed outliers bracket the series: an extreme low reading alongside the
    # 2001 cluster, and an extreme high reading alongside the 2006 cluster. The clean
    # median series (6, 4, 2, 1) trends down; the outlier-skewed mean series
    # (~-220.5, 4, 2, ~225.75) trends up instead — Sen's slope itself must diverge.
    df = pd.DataFrame({
        "station": ["A"] * 9,
        "date": pd.to_datetime([
            "2001-01-01", "2001-04-01", "2001-08-01", "2001-11-01",
            "2003-01-01",
            "2005-01-01",
            "2006-01-01", "2006-04-01", "2006-08-01",
        ]),
        "value": [6.0, 6.0, 6.0, -900.0,
                  4.0,
                  2.0,
                  1.0, 1.0, 900.0],
    })
    median_out = trend_by_group(df, ["station"], "date", "value", agg="median")
    mean_out = trend_by_group(df, ["station"], "date", "value", agg="mean")
    assert median_out.iloc[0]["slope"] != mean_out.iloc[0]["slope"]


def test_trend_by_group_coerces_non_numeric_value_column():
    df = pd.DataFrame({
        "station": ["A"] * 5,
        "date": pd.to_datetime(["2001-01-01", "2002-01-01", "2003-01-01", "2004-01-01", "2005-01-01"]),
        "value": ["1", "2", "3", "4", "5"],  # strings, like tidy_samples' `value` column
    })
    out = trend_by_group(df, ["station"], "date", "value")
    assert out.iloc[0]["trend"] == "increasing"


def test_trend_by_group_multiple_group_cols():
    df = pd.DataFrame({
        "station": ["A", "A", "A", "A", "B", "B", "B", "B"],
        "priority_group": ["discharge"] * 4 + ["ph"] * 4,
        "date": pd.to_datetime(["2001-01-01", "2002-01-01", "2003-01-01", "2004-01-01"] * 2),
        "value": [1, 2, 3, 4, 4, 3, 2, 1],
    })
    out = trend_by_group(df, ["station", "priority_group"], "date", "value")
    assert len(out) == 2
    assert set(out.columns) == {"station", "priority_group", "trend", "p", "slope", "intercept", "n"}


def test_trend_by_group_empty_input_returns_typed_empty():
    df = pd.DataFrame(columns=["station", "date", "value"])
    out = trend_by_group(df, ["station"], "date", "value")
    assert list(out.columns) == ["station", "trend", "p", "slope", "intercept", "n"]
    assert len(out) == 0
