import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import _helpers from notebooks/
from _helpers import save_dataframe


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
