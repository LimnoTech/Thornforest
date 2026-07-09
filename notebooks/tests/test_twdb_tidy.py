import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import tidy_gwdb_water_levels, tidy_gwdb_water_quality

HUC8 = {"0140901": "13090002"}


def test_tidy_gwdb_water_levels_tags_and_orders():
    raw = pd.DataFrame({
        "StateWellNumber": ["0140901", "0140901"],
        "MeasurementDate": ["1958-04-16", "1960-01-01"],
        "DepthFromLSD": ["73", "80"],
        "WaterElevation": ["4596", "4589"],
        "MeasuringAgency": ["Other or Source of Measurement Unknown", "TWDB"],
    })
    out = tidy_gwdb_water_levels(raw, HUC8)
    assert list(out.columns) == [
        "monitoring_location_id", "datetime", "depth_from_lsd_ft", "water_elevation_ft",
        "measuring_agency", "priority_group", "huc8"]
    assert len(out) == 2
    assert (out["priority_group"] == "water_level").all()
    assert out.iloc[0]["huc8"] == "13090002"


def test_tidy_gwdb_water_quality_keeps_priority_codes_only():
    raw = pd.DataFrame({
        "StateWellNumber": ["0140901", "0140901"],
        "SampleDate": ["1992-09-18", "1992-09-18"],
        "ParameterCode": ["00300", "39086"],  # 2nd (alkalinity) -> no group -> dropped
        "ParameterDescription": ["OXYGEN, DISSOLVED (MG/L)", "ALKALINITY FIELD DISSOLVED AS CACO3"],
        "ParameterUnitOfMeasure": ["MG/L", "MG/L AS CACO3"],
        "ParameterValue": ["6.2", "186"],
    })
    out = tidy_gwdb_water_quality(raw, HUC8)
    assert len(out) == 1
    assert out.iloc[0]["priority_group"] == "dissolved_oxygen"
    assert out.iloc[0]["huc8"] == "13090002"
    assert list(out.columns)[-2:] == ["priority_group", "huc8"]


def test_tidy_gwdb_empty_returns_typed_empty():
    assert list(tidy_gwdb_water_levels(pd.DataFrame(), HUC8).columns)[0] == "monitoring_location_id"
    assert len(tidy_gwdb_water_quality(pd.DataFrame(), HUC8)) == 0
