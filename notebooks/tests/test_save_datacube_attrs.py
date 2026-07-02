import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import save_datacube


def test_save_datacube_preserves_variable_attrs(tmp_path):
    ds = xr.Dataset(
        {"PREC_ACC_NC": (("time", "y", "x"), np.ones((2, 2, 2)))},
        coords={"time": [0, 1], "y": [0, 1], "x": [0, 1]},
    )
    ds["PREC_ACC_NC"].attrs = {"long_name": "ACCUMULATED TOTAL GRID SCALE PRECIPITATION", "units": "mm"}

    out = save_datacube(ds, tmp_path / "cube.zarr")

    back = xr.open_zarr(out, consolidated=False)
    assert back["PREC_ACC_NC"].attrs["long_name"] == "ACCUMULATED TOTAL GRID SCALE PRECIPITATION"
    assert back["PREC_ACC_NC"].attrs["units"] == "mm"
