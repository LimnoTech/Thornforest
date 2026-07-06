import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _helpers import classify_parameter


def test_classify_by_parameter_code_zero_pads():
    assert classify_parameter(parameter_code="60") == "discharge"      # 00060, zero-padded
    assert classify_parameter(parameter_code="00010") == "temperature"


def test_classify_by_characteristic_substring():
    assert classify_parameter(characteristic="Dissolved oxygen (DO)") == "dissolved_oxygen"
    assert classify_parameter(characteristic="Turbidity, FNU") == "turbidity"


def test_ph_matches_exactly_not_as_substring():
    assert classify_parameter(characteristic="pH") == "pH"
    assert classify_parameter(characteristic="Phosphorus as P") == "phosphorus"  # not pH


def test_unknown_returns_none():
    assert classify_parameter(parameter_code="99999") is None
    assert classify_parameter(characteristic="Fecal coliform") is None
    assert classify_parameter() is None
