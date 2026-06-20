"""
MediScan AI — Medical Calculator Tool
Deterministic clinical formulas. No LLM involved — pure Python math.
"""

import math
from typing import Optional


# ─── eGFR (CKD-EPI 2021 Race-Free Creatinine Equation) ────────────────────────

def calculate_egfr(creatinine_mgdl: float, age: int, sex: str) -> dict:
    """
    CKD-EPI 2021 race-free equation.
    Returns eGFR value + interpretation.
    """
    sex = sex.lower().strip()

    kappa = 0.7 if sex == "female" else 0.9
    alpha = -0.241 if sex == "female" else -0.302
    sex_factor = 1.012 if sex == "female" else 1.0

    scr_kappa = creatinine_mgdl / kappa

    egfr = (
        142
        * (min(scr_kappa, 1.0) ** alpha)
        * (max(scr_kappa, 1.0) ** -1.200)
        * (0.9938 ** age)
        * sex_factor
    )
    egfr = round(egfr, 1)

    # Interpret CKD stage
    if egfr >= 90:
        stage = "Normal kidney function"
        severity = "normal"
    elif egfr >= 60:
        stage = "Mildly reduced (Stage 2 CKD)"
        severity = "borderline"
    elif egfr >= 30:
        stage = "Moderately reduced (Stage 3 CKD)"
        severity = "abnormal"
    elif egfr >= 15:
        stage = "Severely reduced (Stage 4 CKD)"
        severity = "abnormal"
    else:
        stage = "Kidney failure (Stage 5 CKD)"
        severity = "critical"

    return {
        "name": "eGFR",
        "value": egfr,
        "unit": "mL/min/1.73m²",
        "interpretation": stage,
        "severity": severity,
        "formula": "CKD-EPI 2021 (race-free)",
        "reference": ">= 90 mL/min/1.73m²"
    }


# ─── LDL (Friedewald Equation) ────────────────────────────────────────────────

def calculate_ldl(total_cholesterol: float, hdl: float, triglycerides: float) -> Optional[dict]:
    """
    Friedewald equation: LDL = Total - HDL - (TG/5)
    Only valid when TG < 400 mg/dL.
    """
    if triglycerides >= 400:
        return {
            "name": "LDL (Calculated)",
            "value": None,
            "unit": "mg/dL",
            "interpretation": "Cannot calculate — Triglycerides >= 400 mg/dL. Direct LDL measurement required.",
            "severity": "info",
            "formula": "Friedewald (invalid at TG >= 400)",
            "reference": "< 100 mg/dL optimal"
        }

    ldl = total_cholesterol - hdl - (triglycerides / 5)
    ldl = round(ldl, 1)

    if ldl < 100:
        interp, severity = "Optimal", "normal"
    elif ldl < 130:
        interp, severity = "Near optimal", "normal"
    elif ldl < 160:
        interp, severity = "Borderline high", "borderline"
    elif ldl < 190:
        interp, severity = "High — discuss with your doctor", "abnormal"
    else:
        interp, severity = "Very high — medical attention needed", "abnormal"

    return {
        "name": "LDL (Calculated)",
        "value": ldl,
        "unit": "mg/dL",
        "interpretation": interp,
        "severity": severity,
        "formula": "Friedewald: Total - HDL - (TG/5)",
        "reference": "< 100 mg/dL optimal"
    }


# ─── Non-HDL Cholesterol ──────────────────────────────────────────────────────

def calculate_non_hdl(total_cholesterol: float, hdl: float) -> dict:
    non_hdl = round(total_cholesterol - hdl, 1)

    if non_hdl < 130:
        interp, severity = "Optimal", "normal"
    elif non_hdl < 160:
        interp, severity = "Borderline high", "borderline"
    else:
        interp, severity = "High — includes excess LDL and VLDL", "abnormal"

    return {
        "name": "Non-HDL Cholesterol",
        "value": non_hdl,
        "unit": "mg/dL",
        "interpretation": interp,
        "severity": severity,
        "formula": "Total Cholesterol - HDL",
        "reference": "< 130 mg/dL"
    }


# ─── VLDL Cholesterol ─────────────────────────────────────────────────────────

def calculate_vldl(triglycerides: float) -> dict:
    vldl = round(triglycerides / 5, 1)
    severity = "normal" if 5 <= vldl <= 40 else "abnormal"

    return {
        "name": "VLDL (Calculated)",
        "value": vldl,
        "unit": "mg/dL",
        "interpretation": "Normal" if severity == "normal" else "Elevated VLDL",
        "severity": severity,
        "formula": "Triglycerides / 5",
        "reference": "5 - 40 mg/dL"
    }


# ─── Total Cholesterol / HDL Ratio ────────────────────────────────────────────

def calculate_chol_hdl_ratio(total_cholesterol: float, hdl: float) -> dict:
    ratio = round(total_cholesterol / hdl, 2) if hdl > 0 else None

    if ratio is None:
        return {"name": "Cholesterol/HDL Ratio", "value": None, "unit": "", "interpretation": "Cannot calculate", "severity": "info", "formula": "Total / HDL", "reference": "< 4.0"}

    if ratio < 4.0:
        interp, severity = "Low risk", "normal"
    elif ratio <= 5.0:
        interp, severity = "Moderate risk", "borderline"
    else:
        interp, severity = "High cardiovascular risk", "abnormal"

    return {
        "name": "Total Cholesterol / HDL Ratio",
        "value": ratio,
        "unit": "",
        "interpretation": interp,
        "severity": severity,
        "formula": "Total Cholesterol / HDL",
        "reference": "< 4.0 (lower is better)"
    }


# ─── BMI ─────────────────────────────────────────────────────────────────────

def calculate_bmi(weight_kg: float, height_cm: float) -> dict:
    height_m = height_cm / 100
    bmi = round(weight_kg / (height_m ** 2), 1)

    # Asian-specific cutoffs (WHO recommendation for South Asians)
    if bmi < 18.5:
        interp, severity = "Underweight", "borderline"
    elif bmi < 23.0:
        interp, severity = "Normal weight (Asian standard)", "normal"
    elif bmi < 25.0:
        interp, severity = "Overweight (Asian standard)", "borderline"
    else:
        interp, severity = "Obese — increased health risk", "abnormal"

    return {
        "name": "BMI",
        "value": bmi,
        "unit": "kg/m²",
        "interpretation": interp,
        "severity": severity,
        "formula": "Weight(kg) / Height(m)²",
        "reference": "18.5 - 22.9 kg/m² (Asian standard)"
    }


# ─── BUN/Creatinine Ratio ────────────────────────────────────────────────────

def calculate_bun_creatinine_ratio(bun: float, creatinine: float) -> dict:
    ratio = round(bun / creatinine, 1) if creatinine > 0 else None

    if ratio is None:
        return {"name": "BUN/Creatinine Ratio", "value": None, "unit": "", "interpretation": "Cannot calculate", "severity": "info", "formula": "BUN / Creatinine", "reference": "10:1 - 20:1"}

    if 10 <= ratio <= 20:
        interp, severity = "Normal ratio", "normal"
    elif ratio > 20:
        interp, severity = "High — possible dehydration, GI bleeding, or high protein diet", "borderline"
    else:
        interp, severity = "Low — possible liver disease or malnutrition", "borderline"

    return {
        "name": "BUN / Creatinine Ratio",
        "value": ratio,
        "unit": "",
        "interpretation": interp,
        "severity": severity,
        "formula": "BUN / Creatinine",
        "reference": "10:1 to 20:1"
    }


# ─── Unit Converters ─────────────────────────────────────────────────────────

def glucose_mmol_to_mgdl(mmol: float) -> float:
    return round(mmol * 18.0182, 1)

def glucose_mgdl_to_mmol(mgdl: float) -> float:
    return round(mgdl / 18.0182, 2)

def cholesterol_mmol_to_mgdl(mmol: float) -> float:
    return round(mmol * 38.67, 1)

def creatinine_umol_to_mgdl(umol: float) -> float:
    return round(umol / 88.42, 3)

def hba1c_mmolmol_to_percent(mmol_mol: float) -> float:
    return round((mmol_mol / 10.929) + 2.15, 1)


# ─── Master Calculator — called by the Calculator Node ────────────────────────

def run_calculations(extracted_tests: list, patient_age: int, patient_sex: str) -> list:
    """
    Scans extracted tests and runs all applicable formulas.
    Returns list of calculated metric dicts.
    """
    metrics = []

    # Build lookup: test_name_lower → value (as float)
    test_lookup = {}
    for t in extracted_tests:
        try:
            name_key = t.get("test_name", "").lower().replace(" ", "_").replace("/", "_")
            val = float(str(t.get("value", "0")).replace("<", "").replace(">", "").strip())
            test_lookup[name_key] = val
            # Also store common aliases
            raw_name = t.get("test_name", "").lower()
            test_lookup[raw_name] = val
        except (ValueError, TypeError):
            continue

    def get(aliases):
        for alias in aliases:
            if alias in test_lookup:
                return test_lookup[alias]
        return None

    # eGFR from Creatinine
    creatinine = get(["creatinine", "serum creatinine", "s. creatinine", "s.creatinine", "creatinine (serum)"])
    if creatinine and patient_age and patient_sex:
        metrics.append(calculate_egfr(creatinine, patient_age, patient_sex))

    # LDL from lipid profile
    total_chol = get(["total cholesterol", "cholesterol", "cholesterol, total"])
    hdl = get(["hdl", "hdl cholesterol", "hdl-c", "hdl-cholesterol"])
    tg = get(["triglycerides", "triglyceride", "tg"])
    if total_chol and hdl and tg:
        result = calculate_ldl(total_chol, hdl, tg)
        if result:
            metrics.append(result)
        metrics.append(calculate_non_hdl(total_chol, hdl))
        metrics.append(calculate_vldl(tg))
        metrics.append(calculate_chol_hdl_ratio(total_chol, hdl))

    # BUN/Creatinine ratio
    bun = get(["bun", "blood urea nitrogen", "urea nitrogen"])
    if bun and creatinine:
        metrics.append(calculate_bun_creatinine_ratio(bun, creatinine))

    return metrics
