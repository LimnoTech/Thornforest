import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import coverage, mk_sen_trend, water_year


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
