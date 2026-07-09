import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import _helpers from notebooks/
from _helpers import load_dataframe, save_dataframe


def test_save_dataframe_plain_dataframe(tmp_path):
    df = pd.DataFrame({"station": ["A", "B"], "value": [1.0, 2.0]})
    out = tmp_path / "sub" / "table.parquet"

    assert save_dataframe(df, out) is None  # side-effect helper returns nothing
    assert out.exists()
    assert out.with_suffix(".csv").exists()
    pd.testing.assert_frame_equal(pd.read_parquet(out), df)


def test_save_dataframe_geodataframe_moves_geometry_last_and_writes_wkt(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Point

    # geometry FIRST so the reorder-to-last is genuinely exercised.
    gdf = gpd.GeoDataFrame(
        {"geometry": [Point(0, 0), Point(1, 1)], "id": ["a", "b"], "value": [1, 2]},
        crs="EPSG:4326",
    )
    out = tmp_path / "geo.parquet"
    save_dataframe(gdf, out)

    back = gpd.read_parquet(out)
    assert list(back.columns)[-1] == "geometry"  # geometry moved last
    assert list(back.columns)[:2] == ["id", "value"]  # non-geometry order preserved

    csv = pd.read_csv(out.with_suffix(".csv"))
    assert list(csv.columns)[-1] == "geometry"
    assert str(csv["geometry"].iloc[0]).upper().startswith("POINT")  # geometry -> WKT


def test_load_dataframe_returns_none_if_missing(tmp_path):
    assert load_dataframe(tmp_path / "does_not_exist.parquet") is None


def test_load_dataframe_round_trips_plain_dataframe(tmp_path):
    df = pd.DataFrame({"station": ["A", "B"], "value": [1.0, 2.0]})
    out = tmp_path / "table.parquet"
    save_dataframe(df, out)

    loaded = load_dataframe(out)
    # load_dataframe reads back with dtype_backend="pyarrow" (better type inference than plain
    # NumPy dtypes) — values match but the exact pyarrow string subtype (string vs large_string)
    # depends on the parquet round-trip, not just an in-memory conversion, so don't over-assert it.
    assert str(loaded["station"].dtype).endswith("string[pyarrow]")
    assert str(loaded["value"].dtype) == "double[pyarrow]"
    pd.testing.assert_frame_equal(loaded, df, check_dtype=False)


def test_load_dataframe_round_trips_geodataframe(tmp_path):
    import geopandas as gpd
    import geopandas.testing
    from shapely.geometry import Point

    gdf = gpd.GeoDataFrame(
        {"id": ["a", "b"], "geometry": [Point(0, 0), Point(1, 1)]}, crs="EPSG:4326"
    )
    out = tmp_path / "geo.parquet"
    save_dataframe(gdf, out)

    loaded = load_dataframe(out)
    assert isinstance(loaded, gpd.GeoDataFrame)
    assert loaded.crs == gdf.crs
    gpd.testing.assert_geodataframe_equal(loaded, gdf)


def test_load_dataframe_respects_max_age_days(tmp_path):
    df = pd.DataFrame({"value": [1, 2]})
    out = tmp_path / "table.parquet"
    save_dataframe(df, out)

    # Back-date the file's mtime to 10 days ago.
    old_time = time.time() - 10 * 86400
    os.utime(out, (old_time, old_time))

    assert load_dataframe(out, max_age_days=7) is None  # too old -> caller should re-fetch
    assert load_dataframe(out, max_age_days=30) is not None  # within window -> use cache
    assert load_dataframe(out) is not None  # no max_age_days -> always fresh enough
