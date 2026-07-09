import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import tidy_wqp_results

HUC8 = {"TCEQMAIN-12336": "13090002"}


def test_tidy_wqp_results_tags_and_orders():
    raw = pd.DataFrame({
        "MonitoringLocationIdentifier": ["TCEQMAIN-12336", "TCEQMAIN-12336"],
        # ActivityStartDate, not ActivityStartDateTime — verified live against the real WQP legacy
        # API that ActivityStartDateTime is 100% null for TCEQMAIN (0/93,436 rows in a bbox pull),
        # so ActivityStartDate is the only reliably-populated start-date field for this source.
        "ActivityStartDate": ["2020-01-02", "2020-01-01"],
        "CharacteristicName": ["Oxygen", "Fecal coliform"],  # 2nd -> no group -> dropped
        "USGSPCode": [None, None],
        "ResultMeasureValue": ["8.1", "10"],
        "ResultMeasure/MeasureUnitCode": ["mg/L", "cfu"],
        "ResultSampleFractionText": [None, None],
        "ResultDetectionConditionText": [None, None],
        "MeasureQualifierCode": [None, None],
        "LaboratoryName": [None, None],
    })
    out = tidy_wqp_results(raw, HUC8)
    assert list(out.columns) == [
        "monitoring_location_id", "datetime", "characteristic", "parameter_code",
        "value", "unit", "fraction", "detection_condition", "qualifier", "lab_name",
        "priority_group", "huc8"]
    assert len(out) == 1  # non-priority row dropped
    assert out.iloc[0]["priority_group"] == "dissolved_oxygen"  # widened "oxygen" substring
    assert out.iloc[0]["huc8"] == "13090002"
    assert out.iloc[0]["datetime"] == "2020-01-02"  # populated, not null/NaT


def test_tidy_wqp_results_activitystartdatetime_absent_does_not_break_datetime():
    # Regression guard: an earlier version renamed the WQP column ActivityStartDateTime (which is
    # unreliable/all-null for this source) instead of ActivityStartDate, silently producing an
    # all-NaT datetime column and making every downstream trend calculation "insufficient".
    raw = pd.DataFrame({
        "MonitoringLocationIdentifier": ["TCEQMAIN-12336"],
        "ActivityStartDate": ["2020-01-02"],
        "ActivityStartDateTime": [pd.NaT],  # present but null, as in the real API response
        "CharacteristicName": ["Oxygen"],
        "USGSPCode": [None],
        "ResultMeasureValue": ["8.1"],
        "ResultMeasure/MeasureUnitCode": ["mg/L"],
        "ResultSampleFractionText": [None],
        "ResultDetectionConditionText": [None],
        "MeasureQualifierCode": [None],
        "LaboratoryName": [None],
    })
    out = tidy_wqp_results(raw, HUC8)
    assert pd.notna(out.iloc[0]["datetime"])
    assert out.iloc[0]["datetime"] == "2020-01-02"


def test_tidy_wqp_results_empty_returns_typed_empty():
    out = tidy_wqp_results(pd.DataFrame(), HUC8)
    assert len(out) == 0
    assert list(out.columns)[0] == "monitoring_location_id"
