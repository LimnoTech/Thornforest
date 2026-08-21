"""TCEQ Surface Water Quality Monitoring (SWQM) helpers: fetch and tidy results from the EPA
Water Quality Portal (WQP), which TCEQ submits its SWQMIS data to under organization TCEQMAIN.
TCEQ has no public API of its own — WQP is the practical programmatic path. Docs:
https://www.waterqualitydata.us/  API reference: dataretrieval.wqp."""

from __future__ import annotations

import pandas as pd

from .analysis import _warn_missing_huc8
from .config import PRIORITY_GROUPS
from .usgs import classify_parameter

TCEQ_COLUMNS = [
    "monitoring_location_id",
    "datetime",
    "characteristic",
    "parameter_code",
    "value",
    "unit",
    "fraction",
    "detection_condition",
    "qualifier",
    "lab_name",
    "priority_group",
    "huc8",
]


def fetch_wqp_results(bbox: list[float], organization: str = "TCEQMAIN") -> pd.DataFrame:
    """Fetch every WQP result for one organization within a bounding box (raw response, no
    characteristic filter — the query is already scoped tightly enough by bbox+organization that
    an unfiltered pull is a manageable size; verified ~93k rows / ~80s for this project's study
    area). Docs: https://www.waterqualitydata.us/  (dataretrieval.wqp.get_results).

    Unlike dataretrieval.waterdata, WQP's `siteid` parameter does not reliably OR across multiple
    semicolon-joined ids (verified empirically — only the first id's rows were returned), so this
    intentionally does not filter by station id; downstream tidy_wqp_results tags huc8 per row
    from the discovered station inventory instead."""
    from dataretrieval import wqp

    raw, _ = wqp.get_results(organization=organization, bBox=",".join(str(v) for v in bbox))
    return raw


def tidy_wqp_results(
    raw: pd.DataFrame,
    huc8_by_station: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename WQP's legacy result columns -> keep rows whose characteristic maps to a priority
    group -> tag priority_group/huc8 -> select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=TCEQ_COLUMNS)
    renamed = raw.rename(
        columns={
            "MonitoringLocationIdentifier": "monitoring_location_id",
            "ActivityStartDate": "datetime",
            "CharacteristicName": "characteristic",
            "USGSPCode": "parameter_code",
            "ResultMeasureValue": "value",
            "ResultMeasure/MeasureUnitCode": "unit",
            "ResultSampleFractionText": "fraction",
            "ResultDetectionConditionText": "detection_condition",
            "MeasureQualifierCode": "qualifier",
            "LaboratoryName": "lab_name",
        }
    )
    priority = renamed["characteristic"].map(
        lambda c: classify_parameter(characteristic=c, groups=groups)
    )
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = (
        tidy[TCEQ_COLUMNS]
        .sort_values(["monitoring_location_id", "characteristic", "datetime"])
        .reset_index(drop=True)
    )
    return _warn_missing_huc8(tidy, "TCEQ WQP")
