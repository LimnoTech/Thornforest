"""TWDB Groundwater Database (GWDB) helpers. The ArcGIS FeatureServer only exposes a well
INVENTORY layer (location, aquifer, flags) — the actual water-level and water-quality time
series only exist in a nightly full-state bulk zip (GWDBDownload.zip), keyed by
StateWellNumber. Verified live: GWDB's water-quality ParameterCode reuses USGS-style parameter
codes, so classification reuses classify_parameter(parameter_code=...) unchanged."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .analysis import _warn_missing_huc8
from .config import PRIORITY_GROUPS
from .usgs import classify_parameter

if TYPE_CHECKING:
    import geopandas as gpd

GWDB_FEATURESERVER_URL = (
    "https://services.twdb.texas.gov/arcgis/rest/services/Public/"
    "TWDB_Groundwater_database/FeatureServer/0/query"
)
GWDB_BULK_URL = "https://www.twdb.texas.gov/groundwater/data/GWDBDownload.zip"
GWDB_PAGE_SIZE = 1000  # the FeatureServer's maxRecordCount

WATER_LEVEL_MEMBERS = [
    "GWDBDownload/WaterLevelsMajor.txt",
    "GWDBDownload/WaterLevelsMinor.txt",
    "GWDBDownload/WaterLevelsCombination.txt",
    "GWDBDownload/WaterLevelsOtherUnassigned.txt",
]
WATER_QUALITY_MEMBERS = [
    "GWDBDownload/WaterQualityMajor.txt",
    "GWDBDownload/WaterQualityMinor.txt",
    "GWDBDownload/WaterQualityCombination.txt",
    "GWDBDownload/WaterQualityOtherUnassigned.txt",
]
WATER_LEVEL_USECOLS = ["StateWellNumber", "MeasurementDate", "DepthFromLSD", "WaterElevation", "MeasuringAgency"]
WATER_QUALITY_USECOLS = ["StateWellNumber", "SampleDate", "ParameterCode", "ParameterDescription",
                         "ParameterUnitOfMeasure", "ParameterValue"]

GWDB_COLUMNS_LEVELS = ["monitoring_location_id", "datetime", "depth_from_lsd_ft", "water_elevation_ft",
                      "measuring_agency", "priority_group", "huc8"]
GWDB_COLUMNS_QUALITY = ["monitoring_location_id", "datetime", "parameter_code", "parameter_description",
                       "value", "unit", "priority_group", "huc8"]


def fetch_gwdb_wells(bbox: list[float]) -> gpd.GeoDataFrame:
    """Query the TWDB GWDB well-inventory ArcGIS FeatureServer within a bounding box, paginating
    past the server's 1,000-record page limit. Docs:
    https://www.twdb.texas.gov/mapping/data-services.asp"""
    import geopandas as gpd
    import requests

    features, offset = [], 0
    while True:
        params = {
            "geometry": ",".join(str(v) for v in bbox),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": GWDB_PAGE_SIZE,
            "resultOffset": offset,
        }
        page = requests.get(GWDB_FEATURESERVER_URL, params=params, timeout=60).json()
        page_features = page.get("features", [])
        features.extend(page_features)
        if len(page_features) < GWDB_PAGE_SIZE:
            break
        offset += GWDB_PAGE_SIZE
    return gpd.GeoDataFrame.from_features(features, crs=4326)


def fetch_gwdb_zip(dest: Path, url: str = GWDB_BULK_URL, max_age_days: int = 7) -> Path:
    """Download the nightly GWDB bulk zip (~81 MB) to `dest`, skipping the download if a cached
    copy under `max_age_days` old already exists (matches this project's week-long cache
    convention). Streamed to avoid holding the whole file in memory."""
    import time
    import requests

    if dest.exists() and (time.time() - dest.stat().st_mtime) < max_age_days * 86400:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def fetch_gwdb_members(
    zip_path: Path, members: list[str], usecols: list[str], well_ids: set[str]
) -> pd.DataFrame:
    """Stream-read and filter each pipe-delimited member in the GWDB bulk zip to `well_ids`,
    chunked to bound memory (WaterQualityMajor.txt alone is ~1 GB uncompressed). Never extracts
    the full archive or loads a whole member into memory at once.

    `encoding="latin-1"` (not the pandas default utf-8): verified live that
    WaterLevelsMajor.txt contains non-UTF-8 bytes (e.g. a Windows-1252 ellipsis, 0x85, in a
    free-text Remarks field) that raise UnicodeDecodeError under utf-8. latin-1 maps every byte
    0-255 to a character, so it never fails to decode; the only fields we keep (`usecols`) are
    numeric/ID columns unaffected by the encoding choice."""
    import zipfile

    frames = []
    with zipfile.ZipFile(zip_path) as z:
        for member in members:
            with z.open(member) as f:
                for chunk in pd.read_csv(
                    f, sep="|", usecols=usecols, dtype=str, chunksize=200_000, encoding="latin-1"
                ):
                    matched = chunk[chunk["StateWellNumber"].isin(well_ids)]
                    if len(matched):
                        frames.append(matched)
    if not frames:
        return pd.DataFrame(columns=usecols)
    return pd.concat(frames, ignore_index=True)


def tidy_gwdb_water_levels(raw: pd.DataFrame, huc8_by_well: dict[str, str]) -> pd.DataFrame:
    """Rename GWDB water-level columns -> tag priority_group ('water_level' — GWDB's water-level
    file has no other analyte) + huc8 -> select/sort. Pure; no network."""
    if raw.empty:
        return pd.DataFrame(columns=GWDB_COLUMNS_LEVELS)
    renamed = raw.rename(columns={
        "StateWellNumber": "monitoring_location_id",
        "MeasurementDate": "datetime",
        "DepthFromLSD": "depth_from_lsd_ft",
        "WaterElevation": "water_elevation_ft",
        "MeasuringAgency": "measuring_agency",
    })
    tidy = renamed.assign(
        priority_group="water_level",
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_well),
    )
    tidy = tidy[GWDB_COLUMNS_LEVELS].sort_values(
        ["monitoring_location_id", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "GWDB water levels")


def tidy_gwdb_water_quality(
    raw: pd.DataFrame,
    huc8_by_well: dict[str, str],
    groups: dict = PRIORITY_GROUPS,
) -> pd.DataFrame:
    """Rename GWDB water-quality columns -> keep rows whose ParameterCode maps to a priority group
    (GWDB reuses USGS-style parameter codes) -> tag priority_group/huc8 -> select/sort. Pure; no
    network."""
    if raw.empty:
        return pd.DataFrame(columns=GWDB_COLUMNS_QUALITY)
    renamed = raw.rename(columns={
        "StateWellNumber": "monitoring_location_id",
        "SampleDate": "datetime",
        "ParameterCode": "parameter_code",
        "ParameterDescription": "parameter_description",
        "ParameterValue": "value",
        "ParameterUnitOfMeasure": "unit",
    })
    priority = renamed["parameter_code"].map(lambda c: classify_parameter(parameter_code=c, groups=groups))
    keep = priority.notna()
    tidy = renamed.loc[keep].assign(
        priority_group=priority[keep].to_numpy(),
        huc8=lambda d: d["monitoring_location_id"].map(huc8_by_well),
    )
    tidy = tidy[GWDB_COLUMNS_QUALITY].sort_values(
        ["monitoring_location_id", "parameter_code", "datetime"]).reset_index(drop=True)
    return _warn_missing_huc8(tidy, "GWDB water quality")
