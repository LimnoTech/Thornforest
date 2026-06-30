import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import _helpers from notebooks/
from _helpers import save_outputs


def test_save_outputs_plain_dataframe(tmp_path):
    df = pd.DataFrame({"station": ["A", "B"], "value": [1.0, 2.0]})
    out = tmp_path / "sub" / "table.parquet"

    save_outputs(df, out)

    assert out.exists()
    assert out.with_suffix(".csv").exists()
    back = pd.read_parquet(out)
    pd.testing.assert_frame_equal(back, df)


def test_save_outputs_geodataframe(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Point

    gdf = gpd.GeoDataFrame(
        {"id": [1, 2], "geometry": [Point(0, 0), Point(1, 1)]},
        crs="EPSG:4326",
    )
    out = tmp_path / "geo.parquet"

    save_outputs(gdf, out)

    assert out.exists()
    assert out.with_suffix(".csv").exists()
    back = gpd.read_parquet(out)
    assert back.geometry.name == "geometry"
    assert len(back) == 2
    # geometry column is moved to the END in the saved output
    assert list(back.columns)[-1] == "geometry"
