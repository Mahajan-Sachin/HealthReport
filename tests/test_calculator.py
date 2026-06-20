"""
Unit tests for medical calculator — pure Python, no API calls needed.
Tests the formulas that run in Node 3 (calculate_node).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.tools.calculator import run_calculations


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_test(name, value, unit="", ref=""):
    return {"test_name": name, "value": str(value), "unit": unit,
            "reference_range": ref, "flag": ""}


def _find_metric(metrics, name_fragment):
    """Find a calculated metric by partial name match."""
    for m in metrics:
        if name_fragment.lower() in m["name"].lower():
            return m
    return None


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_egfr_male_calculated():
    """eGFR should be calculated when serum creatinine + age + sex are present."""
    tests = [_make_test("Serum Creatinine", 1.1, "mg/dL")]
    metrics = run_calculations(tests, patient_age=42, patient_sex="male")
    egfr = _find_metric(metrics, "eGFR")
    assert egfr is not None, "eGFR should be calculated"
    assert egfr["value"] is not None
    assert float(egfr["value"]) > 0


def test_egfr_stage4_high_creatinine():
    """High creatinine (3.8) in 65yr male → Stage 4 CKD (eGFR 15-29)."""
    tests = [_make_test("Serum Creatinine", 3.8, "mg/dL")]
    metrics = run_calculations(tests, patient_age=65, patient_sex="male")
    egfr = _find_metric(metrics, "eGFR")
    assert egfr is not None
    val = float(egfr["value"])
    assert val < 30, f"Expected Stage 4 CKD eGFR (<30), got {val}"
    assert egfr["severity"] in ("abnormal", "critical")


def test_ldl_friedewald_calculated():
    """LDL = Total Cholesterol - HDL - (Triglycerides / 5)."""
    tests = [
        _make_test("Total Cholesterol", 238, "mg/dL"),
        _make_test("HDL Cholesterol", 38, "mg/dL"),
        _make_test("Triglycerides", 210, "mg/dL"),
    ]
    metrics = run_calculations(tests, patient_age=42, patient_sex="male")
    ldl = _find_metric(metrics, "LDL")
    assert ldl is not None, "LDL should be calculated"
    # Friedewald: 238 - 38 - (210/5) = 238 - 38 - 42 = 158
    expected = 238 - 38 - (210 / 5)
    assert abs(float(ldl["value"]) - expected) < 1.0, \
        f"Expected LDL ~{expected}, got {ldl['value']}"


def test_ldl_not_calculated_when_tg_too_high():
    """Friedewald equation is invalid when Triglycerides > 400 mg/dL."""
    tests = [
        _make_test("Total Cholesterol", 312, "mg/dL"),
        _make_test("HDL Cholesterol", 28, "mg/dL"),
        _make_test("Triglycerides", 490, "mg/dL"),  # > 400 → invalid
    ]
    metrics = run_calculations(tests, patient_age=65, patient_sex="male")
    ldl = _find_metric(metrics, "LDL")
    # Should either not exist or have value=None (equation invalid)
    if ldl:
        assert ldl["value"] is None, \
            "LDL should be None when TG > 400 (Friedewald invalid)"


def test_non_hdl_cholesterol():
    """Non-HDL = Total Cholesterol - HDL. Needs TG present to trigger lipid block."""
    tests = [
        _make_test("Total Cholesterol", 238, "mg/dL"),
        _make_test("HDL Cholesterol", 38, "mg/dL"),
        _make_test("Triglycerides", 150, "mg/dL"),   # needed to trigger lipid calc block
    ]
    metrics = run_calculations(tests, patient_age=42, patient_sex="male")
    non_hdl = _find_metric(metrics, "Non-HDL")
    assert non_hdl is not None, "Non-HDL Cholesterol should be calculated"
    assert float(non_hdl["value"]) == 200.0  # 238 - 38 = 200


def test_bun_creatinine_ratio():
    """BUN/Creatinine ratio = BUN / Serum Creatinine."""
    tests = [
        _make_test("BUN", 18, "mg/dL"),
        _make_test("Serum Creatinine", 1.1, "mg/dL"),
    ]
    metrics = run_calculations(tests, patient_age=42, patient_sex="male")
    ratio = _find_metric(metrics, "BUN")
    assert ratio is not None
    expected = round(18 / 1.1, 1)
    assert abs(float(ratio["value"]) - expected) < 0.5


def test_no_crash_with_empty_tests():
    """Calculator should not crash on empty input."""
    metrics = run_calculations([], patient_age=30, patient_sex="female")
    assert isinstance(metrics, list)


def test_no_crash_with_non_numeric_values():
    """Calculator should handle non-numeric values gracefully."""
    tests = [_make_test("Total Cholesterol", "pending", "mg/dL")]
    metrics = run_calculations(tests, patient_age=42, patient_sex="male")
    assert isinstance(metrics, list)
