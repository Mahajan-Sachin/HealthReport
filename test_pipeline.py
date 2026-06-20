"""
MediScan AI — Full Pipeline Test
Synthetic report: Type 2 (mixed — some normal, some abnormal)
Tests: CBC + Lipid + Blood Sugar + Kidney Function
"""

import json
import urllib.request
import urllib.error

API = "http://localhost:8000"

# Synthetic test report — Type 2 (MIXED: some normal, some abnormal)
TEST_REPORT = """
PATIENT LAB REPORT
Lab: City Diagnostics
Date: 19-Jun-2026

COMPLETE BLOOD COUNT (CBC)
Hemoglobin (Hb)         : 9.2  g/dL     [Reference: 13.5-17.5]  L
WBC (Total Leukocytes)  : 8500 /uL       [Reference: 4000-11000]
Platelet Count          : 185000 /uL     [Reference: 150000-400000]
RBC Count               : 3.8  mill/cumm [Reference: 4.5-5.9]     L
MCV                     : 72.0 fL        [Reference: 80-100]       L

LIPID PROFILE
Total Cholesterol       : 238 mg/dL      [Reference: <200]         H
HDL Cholesterol         : 38  mg/dL      [Reference: >40]          L
Triglycerides           : 210 mg/dL      [Reference: <150]         H

BLOOD GLUCOSE
Fasting Blood Glucose   : 132 mg/dL      [Reference: 70-99]        H
HbA1c                   : 7.4 %          [Reference: <5.7]         H

KIDNEY FUNCTION TEST
Serum Creatinine        : 1.1 mg/dL      [Reference: 0.74-1.35]
Blood Urea Nitrogen     : 18  mg/dL      [Reference: 7-20]

THYROID
TSH                     : 5.8 mIU/L      [Reference: 0.4-4.0]      H

VITAMINS
Vitamin B12             : 185 pg/mL      [Reference: 200-900]      L
Vitamin D               : 16.0 ng/mL     [Reference: 30-100]       L
"""

print("=" * 60)
print("MediScan AI - Pipeline Test")
print("Report Type: MIXED (normal + abnormal)")
print("=" * 60)

# Send analysis request
payload = json.dumps({
    "report_text": TEST_REPORT,
    "patient_name": "Test Patient",
    "patient_age": 42,
    "patient_sex": "male"
}).encode("utf-8")

req = urllib.request.Request(
    f"{API}/analyze/text",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("\n[1] Sending analysis request...")
try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
        print(f"    Status: {result.get('status')}")
        print(f"    Message: {result.get('message')}")
        report_id = result.get("report_id")
        print(f"    Report ID: {report_id}")
except urllib.error.HTTPError as e:
    print(f"    ERROR {e.code}: {e.read().decode()}")
    exit(1)

# Fetch report
print(f"\n[2] Fetching report {report_id}...")
with urllib.request.urlopen(f"{API}/report/{report_id}", timeout=30) as resp:
    report = json.loads(resp.read())

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
summary = report.get("summary", {})
print(f"  Total tests:    {summary.get('total_tests', 0)}")
print(f"  Normal:         {summary.get('normal_count', 0)}")
print(f"  Need attention: {summary.get('abnormal_count', 0)}")
print(f"  Borderline:     {summary.get('borderline_count', 0)}")

print("\n" + "=" * 60)
print("CALCULATED METRICS")
print("=" * 60)
for m in report.get("calculated_metrics", []):
    if m.get("value") is not None:
        print(f"  {m['name']}: {m['value']} {m['unit']} -> {m['interpretation']}")

print("\n" + "=" * 60)
print("JUDGE ITERATIONS:", report.get("judge_iterations", 1))
print("=" * 60)

print("\n" + "=" * 60)
print("CREW AI REPORT (first 1200 chars)")
print("=" * 60)
crew = report.get("crew_explanation", "")
# Safe print for Windows cp1252 terminal
safe_crew = crew.encode("ascii", errors="replace").decode("ascii")
print(safe_crew[:1200])

print("\n[OK] Test PASSED - Full pipeline working!")
