import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import tidy_daily, tidy_field, tidy_samples

HUC8 = {"S1": "13090001"}
NAMES = {"00060": "Discharge, cubic feet per second"}


def test_tidy_daily_tags_and_orders():
    raw = pd.DataFrame({
        "monitoring_location_id": ["S1", "S1"],
        "time": ["2001-01-02", "2001-01-01"],
        "parameter_code": ["00060", "99999"],  # second row not a priority code -> dropped
        "statistic_id": ["00003", "00003"],
        "value": [10.0, 1.0],
        "unit_of_measure": ["ft3/s", "x"],
        "approval_status": ["Approved", "Approved"],
        "qualifier": [None, None],
    })
    out = tidy_daily(raw, HUC8, NAMES)
    assert list(out.columns) == [
        "monitoring_location_id", "date", "parameter_code", "parameter_name", "statistic",
        "value", "unit", "approval_status", "qualifier", "priority_group", "huc8"]
    assert len(out) == 1  # non-priority row dropped
    assert out.iloc[0]["priority_group"] == "discharge"
    assert out.iloc[0]["parameter_name"] == "Discharge, cubic feet per second"
    assert out.iloc[0]["huc8"] == "13090001"


def test_tidy_samples_keeps_priority_characteristics_only():
    raw = pd.DataFrame({
        "Location_Identifier": ["S1", "S1"],
        "Activity_StartDateTime": ["2001-01-01", "2001-01-02"],
        "Result_Characteristic": ["Turbidity", "Fecal coliform"],  # 2nd -> no group -> dropped
        "USGSpcode": ["00076", "31625"],
        "Result_Measure": ["5", "10"],
        "Result_MeasureUnit": ["NTU", "cfu"],
        "Result_SampleFraction": [None, None],
        "Result_ResultDetectionCondition": [None, None],
        "Result_MeasureQualifierCode": [None, None],
        "Result_CharacteristicGroup": ["Physical", "Biological"],
        "LabInfo_Name": [None, None],
    })
    out = tidy_samples(raw, HUC8)
    assert len(out) == 1
    assert out.iloc[0]["priority_group"] == "turbidity"
    assert out.iloc[0]["huc8"] == "13090001"
    assert list(out.columns)[-2:] == ["priority_group", "huc8"]


def test_tidy_empty_returns_typed_empty():
    assert list(tidy_field(pd.DataFrame(), HUC8, NAMES).columns)[0] == "monitoring_location_id"
    assert len(tidy_field(pd.DataFrame(), HUC8, NAMES)) == 0
