"""
MediScan AI — PDF Report Generator
Uses fpdf2 with Arial TTF font (Unicode-capable) to avoid
the built-in Helvetica latin-1 limitation that rejects em-dashes etc.
"""

import re
from fpdf import FPDF
from datetime import datetime

# Windows system font paths (fallback to ascii mode on Linux/Mac)
_ARIAL_REGULAR = "C:/Windows/Fonts/arial.ttf"
_ARIAL_BOLD    = "C:/Windows/Fonts/arialbd.ttf"
_ARIAL_ITALIC  = "C:/Windows/Fonts/ariali.ttf"

import os
_USE_ARIAL = (
    os.path.exists(_ARIAL_REGULAR) and
    os.path.exists(_ARIAL_BOLD)
)
_FONT_NAME = "Arial" if _USE_ARIAL else "Helvetica"


class MediScanPDF(FPDF):
    """Custom PDF class with Unicode-capable Arial font."""

    def __init__(self):
        super().__init__()
        if _USE_ARIAL:
            self.add_font("Arial", style="",  fname=_ARIAL_REGULAR)
            self.add_font("Arial", style="B", fname=_ARIAL_BOLD)
            if os.path.exists(_ARIAL_ITALIC):
                self.add_font("Arial", style="I", fname=_ARIAL_ITALIC)

    def header(self):
        self.set_font(_FONT_NAME, "B", 14)
        self.set_text_color(30, 120, 180)
        self.cell(0, 10, "MediScan AI -- Health Report Summary", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_font(_FONT_NAME, "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6,
                  f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(30, 120, 180)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font(_FONT_NAME, "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()} | MediScan AI -- Not Medical Advice",
                  align="C")


def _safe(text: str) -> str:
    """
    Light sanitizer — removes truly problematic chars.
    Arial TTF handles most Unicode, so we only need a minimal cleanup.
    For Helvetica fallback, we do full ASCII encoding.
    """
    if not text:
        return ""
    text = str(text)
    # Always strip control characters (both Arial and Helvetica modes)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    if _USE_ARIAL:
        # Arial supports Unicode natively — no further conversion needed
        return text
    else:
        # Helvetica fallback — convert common Unicode to ASCII equivalents
        replacements = {
            "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "--", "\u2015": "--",
            "\u2192": "->", "\u2191": "[H]", "\u2193": "[L]",
            "\u00b2": "2", "\u00b3": "3", "\u00b0": "deg",
            "\u2022": "-", "\u2026": "...", "\u00a0": " ",
            "\u2264": "<=", "\u2265": ">=",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.encode("ascii", errors="replace").decode("ascii")


def _strip_markdown(text: str) -> str:
    """Strip markdown so PDF is plain readable text."""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    return text


def generate_pdf_report(report: dict) -> bytes:
    """
    Generates a PDF from the final_report dict.
    Returns PDF as bytes for download.
    """
    pdf = MediScanPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Patient Info
    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, f"Patient: {_safe(report.get('patient_name', 'N/A'))}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(_FONT_NAME, "", 10)
    pdf.cell(0, 6,
             f"Age: {_safe(str(report.get('patient_age', 'N/A')))}  |  "
             f"Sex: {_safe(str(report.get('patient_sex', 'N/A'))).title()}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Summary
    summary = report.get("summary", {})
    _section_header(pdf, "SUMMARY")
    pdf.set_font(_FONT_NAME, "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, f"Total Tests Analyzed: {summary.get('total_tests', 0)}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6,
             f"Normal: {summary.get('normal_count', 0)}  |  "
             f"Needs Attention: {summary.get('abnormal_count', 0)}  |  "
             f"Borderline: {summary.get('borderline_count', 0)}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # AI Report (Crew Output)
    crew_output = report.get("crew_explanation", "")
    if crew_output:
        _section_header(pdf, "DETAILED HEALTH REPORT")
        pdf.set_font(_FONT_NAME, "", 9)
        pdf.set_text_color(50, 50, 50)
        clean = _safe(_strip_markdown(crew_output))
        for line in clean.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
            if line.upper().startswith("SECTION") or line.startswith("==="):
                pdf.set_font(_FONT_NAME, "B", 10)
                pdf.set_text_color(30, 120, 180)
            elif line.startswith("-") or line.startswith("*"):
                pdf.set_font(_FONT_NAME, "", 9)
                pdf.set_text_color(60, 60, 60)
                line = "  " + line
            else:
                pdf.set_font(_FONT_NAME, "", 9)
                pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")

    # Calculated Metrics
    metrics = report.get("calculated_metrics", [])
    if metrics:
        _section_header(pdf, "CALCULATED HEALTH METRICS")
        for m in metrics:
            if m.get("value") is None:
                continue
            pdf.set_font(_FONT_NAME, "B", 9)
            _set_severity_color(pdf, m.get("severity", "normal"))
            name   = _safe(str(m.get("name", "")))
            value  = _safe(str(m.get("value", "")))
            unit   = _safe(str(m.get("unit", "")))
            interp = _safe(str(m.get("interpretation", "")))
            formula= _safe(str(m.get("formula", "")))
            ref    = _safe(str(m.get("reference", "")))
            pdf.cell(0, 6, f"{name}: {value} {unit}  ->  {interp}",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(_FONT_NAME, "I", 8)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 5, f"  Formula: {formula} | Reference: {ref}",
                     new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # Disclaimer
    pdf.add_page()
    _section_header(pdf, "IMPORTANT DISCLAIMER")
    pdf.set_font(_FONT_NAME, "", 9)
    pdf.set_text_color(180, 60, 60)
    pdf.multi_cell(0, 5, _safe(report.get("disclaimer", "")),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font(_FONT_NAME, "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5,
             f"AI Validation Iterations: {report.get('judge_iterations', 1)}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "Powered by MediScan AI | LangGraph + CrewAI + RAG",
             new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def _section_header(pdf: FPDF, title: str):
    pdf.set_font(_FONT_NAME, "B", 11)
    pdf.set_text_color(30, 120, 180)
    pdf.set_fill_color(240, 247, 255)
    pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _set_severity_color(pdf: FPDF, severity: str):
    if severity in ("abnormal", "critical"):
        pdf.set_text_color(200, 50, 50)
    elif severity == "borderline":
        pdf.set_text_color(180, 120, 0)
    else:
        pdf.set_text_color(30, 140, 60)
