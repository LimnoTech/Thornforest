"""Compiling saved tables into a single downloadable Excel workbook: one sheet per table,
first row + first column frozen, autofilter on the header row."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .session import find_repo_root

if TYPE_CHECKING:
    import pandas as pd


def _is_tz_aware(dtype) -> bool:
    """True for both pandas' native tz-aware dtype and pyarrow-backed timestamp-with-tz dtype
    (e.g. load_dataframe's dtype_backend="pyarrow" reads produce the latter, which
    select_dtypes(include=["datetimetz"]) does not recognize)."""
    import pandas as pd

    if isinstance(dtype, pd.DatetimeTZDtype):
        return True
    pyarrow_dtype = getattr(dtype, "pyarrow_dtype", None)
    return pyarrow_dtype is not None and getattr(pyarrow_dtype, "tz", None) is not None


def _unique_sheet_name(name: str, used: set[str]) -> str:
    """Excel sheet names must be <=31 characters and unique within the workbook. Truncate to 31
    characters, then shrink further and append a numeric suffix on collision."""
    candidate = name[:31]
    n = 1
    while candidate in used:
        suffix = f"_{n}"
        candidate = name[: 31 - len(suffix)] + suffix
        n += 1
    return candidate


def save_workbook(sheets: dict[str, "pd.DataFrame"], xlsx_path: Path | str) -> None:
    """Compile named (Geo)DataFrames into one .xlsx workbook, one sheet per entry (dict order
    preserved), each with the first row and first column frozen and autofilter enabled on the
    header row. Written directly from the in-memory frames (not re-read from CSV) so numeric/date
    dtypes survive intact. GeoDataFrame geometry columns are converted to WKT text first (Excel
    has no native geometry type), matching save_dataframe's CSV output. Timezone-aware datetime
    columns have their timezone stripped (Excel has no tz-aware datetime type; the wall-clock
    value is preserved, only the offset is dropped). Side-effect helper; prints a confirmation and
    returns nothing."""
    import geopandas as gpd
    import pandas as pd

    xlsx_path = Path(xlsx_path)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            if isinstance(df, gpd.GeoDataFrame) and df.active_geometry_name is not None:
                geometry_col = df.geometry.name
                wkt = df.geometry.to_wkt()
                df = pd.DataFrame(df)  # drop GeoDataFrame-ness so to_excel treats it plainly
                df[geometry_col] = wkt

            tz_aware_columns = [c for c in df.columns if _is_tz_aware(df[c].dtype)]
            if tz_aware_columns:
                df = df.copy()
                for col in tz_aware_columns:
                    df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)

            sheet_name = _unique_sheet_name(name, used_names)
            used_names.add(sheet_name)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "B2"
            worksheet.auto_filter.ref = worksheet.dimensions

    try:
        shown = xlsx_path.relative_to(find_repo_root())
    except ValueError:
        shown = xlsx_path
    print(f"saved {len(sheets)} sheet(s) → {shown}")
