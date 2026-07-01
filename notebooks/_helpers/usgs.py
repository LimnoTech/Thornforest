"""USGS Water Data helpers: classify parameters into priority groups, look up verbatim source
names, and fetch/tidy the daily-values, discrete-samples, and field-measurement time-series."""

from __future__ import annotations

import warnings

import pandas as pd

from .config import PRIORITY_GROUPS


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


# --- Temporary stubs (Task 4 replaces these with real implementations + tests) -----

def fetch_daily(*a, **k):
    raise NotImplementedError


def fetch_samples(*a, **k):
    raise NotImplementedError


def fetch_field(*a, **k):
    raise NotImplementedError


def tidy_daily(*a, **k):
    raise NotImplementedError


def tidy_samples(*a, **k):
    raise NotImplementedError


def tidy_field(*a, **k):
    raise NotImplementedError
