"""USGS Water Data helpers: classify parameters into priority groups, look up verbatim source
names, and fetch/tidy the daily-values, discrete-samples, and field-measurement time-series."""

from __future__ import annotations

import warnings

import pandas as pd

from .config import PRIORITY_GROUPS

DAILY_COLUMNS = ["monitoring_location_id", "date", "parameter_code", "parameter_name",
                 "statistic", "value", "unit", "approval_status", "qualifier", "priority_group", "huc8"]
SAMPLES_COLUMNS = ["monitoring_location_id", "datetime", "characteristic", "parameter_code", "value",
                   "unit", "fraction", "detection_condition", "qualifier", "characteristic_group",
                   "lab_name", "priority_group", "huc8"]
FIELD_COLUMNS = ["monitoring_location_id", "datetime", "parameter_code", "parameter_name", "value",
                 "unit", "qualifier", "approval_status", "priority_group", "huc8"]


def _warn_missing_huc8(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Warn (don't silently drop) if the huc8 join produced NaN — signals a station-id mismatch."""
    missing = df["huc8"].isna()
    if missing.any():
        ids = sorted(df.loc[missing, "monitoring_location_id"].unique())[:10]
        print(f"WARNING: {int(missing.sum())} {label} rows had no huc8 match; unmatched ids: {ids}")
    return df


def classify_parameter(
    parameter_code: str | None = None,
    characteristic: str | None = None,
    groups: dict = PRIORITY_GROUPS,
) -> str | None:
    """Return the priority group for a USGS parameter_code or a WQ characteristic name, else None.

    `groups` maps group name -> {"parameter_codes": set[str], "characteristics": [substrings]}.
    pH is matched EXACTLY on the characteristic to avoid the 'ph' substring matching e.g. 'phosphorus'.
    USGS parameter-code reference: https://help.waterdata.usgs.gov/codes-and-parameters/parameters
    """
    if parameter_code is not None:
        parameter_code = str(parameter_code).strip().zfill(5)
        for group, spec in groups.items():
            if parameter_code in spec["parameter_codes"]:
                return group
    if characteristic is not None:
        name = str(characteristic).strip().lower()
        if name == "ph":
            return "pH"
        for group, spec in groups.items():
            if group == "pH":
                continue
            if any(pat in name for pat in spec["characteristics"]):
                return group
    return None


def build_parameter_name_lookup() -> dict[str, str]:
    """parameter_code (str) -> readable name, from the USGS 'parameter-codes' reference table.
    Names are carried verbatim from the source table (source-term fidelity)."""
    from dataretrieval import waterdata

    table, _ = waterdata.get_reference_table("parameter-codes")
    return dict(zip(table["parameter_code"].astype(str), table["parameter_name"]))


def parameter_name(code: str, name_lookup: dict[str, str]) -> str:
    """Look up a code's verbatim source name, trying the 5-digit zero-padded form first.
    Falls back to the raw code (caller should audit codes that fall through)."""
    code = str(code)
    return name_lookup.get(code.zfill(5), name_lookup.get(code, code))


def station_parameters(
    sid: str,
    ts_codes_by_site: dict,
    fm_codes_by_site: dict,
    name_lookup: dict,
    samples_summaries: dict,
    groups: dict = PRIORITY_GROUPS,
) -> tuple[set, list]:
    """Return (priority_groups: set[str], parameter_names: sorted list[str]) for one station,
    combining time-series/field parameter codes with discrete-sample characteristics."""
    found_groups, names = set(), set()
    for code in ts_codes_by_site.get(sid, set()) | fm_codes_by_site.get(sid, set()):
        names.add(parameter_name(code, name_lookup))
        g = classify_parameter(parameter_code=code, groups=groups)
        if g:
            found_groups.add(g)
    summary = samples_summaries.get(sid)
    if summary is not None and "characteristic" in summary.columns:
        for char in summary["characteristic"].dropna().unique():
            names.add(str(char))
            g = classify_parameter(characteristic=char, groups=groups)
            if g:
                found_groups.add(g)
    return found_groups, sorted(names)


def fetch_daily(station_ids: list[str], parameter_codes: list[str]) -> pd.DataFrame:
    """Fetch the full daily-values record for the given stations & parameter codes (raw response).
    Docs: https://api.waterdata.usgs.gov/  (dataretrieval.waterdata.get_daily)"""
    from dataretrieval import waterdata

    if not station_ids:
        print("no daily stations — returning empty frame")
        return pd.DataFrame()
    raw, _ = waterdata.get_daily(
        monitoring_location_id=list(station_ids), parameter_code=list(parameter_codes), skip_geometry=True
    )
    return raw


def fetch_field(station_ids: list[str], parameter_codes: list[str]) -> pd.DataFrame:
    """Fetch the full field-measurements record (raw response)."""
    from dataretrieval import waterdata

    if not station_ids:
        print("no field-measurement stations — returning empty frame")
        return pd.DataFrame()
    raw, _ = waterdata.get_field_measurements(
        monitoring_location_id=list(station_ids), parameter_code=list(parameter_codes), skip_geometry=True
    )
    return raw


def fetch_samples(station_ids: list[str]) -> pd.DataFrame:
    """Fetch all discrete water-quality samples for the given stations (raw response).

    Suppresses the DtypeWarning raised *inside* dataretrieval's own pd.read_csv — the mixed-type
    columns it warns about (Activity_EndTime, Result_TimeBasis, DataQuality_PrecisionValue) are not
    ones we consume, and we cannot pass low_memory/dtype through the library call."""
    from dataretrieval import waterdata

    if not station_ids:
        print("no samples stations — returning empty frame")
        return pd.DataFrame()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)
        raw, _ = waterdata.get_samples(monitoring_location_id=list(station_ids))
    return raw


def tidy_daily(
    raw: pd.DataFrame,
    huc8_by_station: dict[str, str],
    name_lookup: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename → tag priority_group/parameter_name/huc8 → select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS)
    renamed = raw.rename(columns={"time": "date", "statistic_id": "statistic", "unit_of_measure": "unit"})
    priority = renamed["parameter_code"].map(lambda c: classify_parameter(parameter_code=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        parameter_name=lambda d: d["parameter_code"].map(lambda c: parameter_name(c, name_lookup)),
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[DAILY_COLUMNS].sort_values(
        ["monitoring_location_id", "parameter_code", "date"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "daily")


def tidy_field(
    raw: pd.DataFrame,
    huc8_by_station: dict[str, str],
    name_lookup: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename → tag → select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=FIELD_COLUMNS)
    renamed = raw.rename(columns={"time": "datetime", "unit_of_measure": "unit"})
    priority = renamed["parameter_code"].map(lambda c: classify_parameter(parameter_code=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        parameter_name=lambda d: d["parameter_code"].map(lambda c: parameter_name(c, name_lookup)),
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[FIELD_COLUMNS].sort_values(
        ["monitoring_location_id", "parameter_code", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "field")


def tidy_samples(
    raw: pd.DataFrame,
    huc8_by_station: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename → keep rows whose characteristic maps to a priority group → tag → select/sort.

    NOTE: `value` (Result_Measure) is a string (may hold non-detect/text results) — cast with
    pd.to_numeric(errors='coerce') before numeric ops. Columns are assigned in a single .assign to
    avoid the PerformanceWarning from repeatedly inserting into a wide frame. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=SAMPLES_COLUMNS)
    renamed = raw.rename(columns={
        "Location_Identifier": "monitoring_location_id", "Activity_StartDateTime": "datetime",
        "Result_Characteristic": "characteristic", "USGSpcode": "parameter_code",
        "Result_Measure": "value", "Result_MeasureUnit": "unit", "Result_SampleFraction": "fraction",
        "Result_ResultDetectionCondition": "detection_condition", "Result_MeasureQualifierCode": "qualifier",
        "Result_CharacteristicGroup": "characteristic_group", "LabInfo_Name": "lab_name",
    })
    priority = renamed["characteristic"].map(lambda c: classify_parameter(characteristic=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_station),
    )
    tidy = tidy[SAMPLES_COLUMNS].sort_values(
        ["monitoring_location_id", "characteristic", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "samples")
