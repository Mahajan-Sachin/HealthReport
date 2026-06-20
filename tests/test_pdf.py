"""
Unit tests for PDF generator — no API calls, no LLM.
Tests that PDFs are generated without crashing and return valid bytes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.utils.report_generator import generate_pdf_report, _safe, _strip_markdown


# ── Test Data ──────────────────────────────────────────────────────────────────

SAMPLE_REPORT = {
    "patient_name": "Test Patient",
    "patient_age": 42,
    "patient_sex": "male",
    "summary": {
        "total_tests": 3,
        "normal_count": 1,
        "abnormal_count": 2,
        "borderline_count": 0,
        "calculated_metrics_count": 1,
    },
    "calculated_metrics": [
        {
            "name": "eGFR",
            "value": 72.5,
            "unit": "mL/min/1.73m\u00b2",
            "interpretation": "Mild reduction",
            "severity": "borderline",
            "formula": "CKD-EPI 2021",
            "reference": ">= 90",
        }
    ],
    "crew_explanation": (
        "## SECTION 1 \u2014 SUMMARY\n"
        "Your test shows **mild anemia** with LOW \u2193 hemoglobin.\n"
        "- Hemoglobin: 9.2 g/dL [Low]\n"
        "- Creatinine: 1.1 mg/dL (normal)\n"
    ),
    "judge_iterations": 1,
    "disclaimer": "This is AI-generated. Not medical advice.",
    "performance": {
        "node_timings_seconds": {"extract": 1.5, "crew": 12.3},
        "total_pipeline_seconds": 13.8,
    },
}


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_pdf_generates_without_crash():
    """PDF generation should complete without raising any exception."""
    pdf_bytes = generate_pdf_report(SAMPLE_REPORT)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 0


def test_pdf_is_valid_pdf_bytes():
    """Output bytes should start with the PDF magic header %%PDF."""
    pdf_bytes = generate_pdf_report(SAMPLE_REPORT)
    assert pdf_bytes[:4] == b"%PDF", "Output should be a valid PDF file"


def test_pdf_handles_em_dash():
    """Em-dash in crew output should not crash the PDF generator."""
    report = dict(SAMPLE_REPORT)
    report["crew_explanation"] = "SECTION 1 \u2014 SUMMARY\nHigh cholesterol \u2014 needs attention."
    pdf_bytes = generate_pdf_report(report)
    assert len(pdf_bytes) > 0


def test_pdf_handles_arrows():
    """Arrow characters (Unicode) should not crash the PDF generator."""
    report = dict(SAMPLE_REPORT)
    report["crew_explanation"] = "Hemoglobin \u2191 HIGH \u2192 iron deficiency likely."
    pdf_bytes = generate_pdf_report(report)
    assert len(pdf_bytes) > 0


def test_pdf_handles_empty_crew_output():
    """PDF should generate even with no crew explanation."""
    report = dict(SAMPLE_REPORT)
    report["crew_explanation"] = ""
    pdf_bytes = generate_pdf_report(report)
    assert len(pdf_bytes) > 0


def test_safe_strips_control_characters():
    """_safe() should remove non-printable control characters."""
    result = _safe("Hello\x00World\x1fTest")
    assert "\x00" not in result
    assert "\x1f" not in result
    assert "Hello" in result


def test_strip_markdown_removes_headings():
    """_strip_markdown should remove ## heading markers."""
    result = _strip_markdown("## SECTION 1\nSome text.")
    assert "##" not in result
    assert "SECTION 1" in result


def test_strip_markdown_removes_bold():
    """_strip_markdown should remove ** bold markers."""
    result = _strip_markdown("This is **important** text.")
    assert "**" not in result
    assert "important" in result
