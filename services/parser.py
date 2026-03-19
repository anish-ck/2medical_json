"""
Parser service for extracting structured data from medical report text.
Uses regex and rule-based parsing to extract patient info and test results.
"""

import re
from typing import Optional

from models.schema import (
    PatientInfo,
    TestResult,
    BloodGroup,
    Reports,
    MedicalReportResponse,
)
from services.section_splitter import ReportSections, split_into_sections
from services.pdf_extractor import PDFContent
from utils.helpers import (
    clean_text,
    parse_number,
    extract_flag,
    infer_flag_from_reference_range,
    normalize_date,
    normalize_gender,
    extract_age,
)


# Patterns for patient info extraction - ordered by specificity
PATIENT_INFO_PATTERNS = {
    "name": [
        r"Name\s*:\s*([A-Za-z\s\.]+?)(?:\s+Lab\s*Id|$|\n)",
        r"Patient\s*Name\s*[:\-]?\s*([A-Za-z\s\.]+?)(?:\n|$|Age|Gender|Sex)",
        r"(?:Mr\.|Mrs\.|Ms\.)\s+([A-Za-z\s]+?)(?:\n|$|Age)",
    ],
    "age": [
        r"(?:Sex)?/?Age\s*:\s*(?:Male|Female)?\s*/??\s*(\d+)\s*Y",
        r"Age\s*[:\-]?\s*(\d+)\s*(?:Years?|Yrs?|Y)?",
        r"/\s*(\d+)\s*Y\b",
    ],
    "gender": [
        r"Sex/?Age\s*:\s*(Male|Female)",
        r"(?:Gender|Sex)\s*[:\-]?\s*(Male|Female|M|F)",
        r"\b(Male|Female)\b",
    ],
    "lab_id": [
        r"Lab\s*Id\s*:\s*([A-Za-z0-9\-X]+)",
        r"(?:Patient\s*Id|Sample\s*Id|ID\s*No|Report\s*No|Barcode)\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        r"(?:Reg(?:istration)?\.?\s*No\.?)\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    ],
    "report_date": [
        r"(?:Collected\s*on|Collection\s*Date|Sample\s*Date)\s*[:\-]?\s*(\d{1,2}[\-\/]\w{3}[\-\/]\d{4})",
        r"(?:Approved\s*on|Report\s*Date|Date)\s*[:\-]?\s*(\d{1,2}[\-\/]\w{3}[\-\/]\d{4})",
        r"(\d{1,2}[\-\/]\w{3}[\-\/]\d{4})",
    ],
}

# Valid test name patterns - test names should start with these or similar
VALID_TEST_PATTERNS = [
    r"^[A-Z][a-zA-Z\s\(\)\-]+$",  # Starts with capital, contains letters
]

# Words that indicate a line is NOT a test result
NOISE_INDICATORS = [
    "page", "report", "authenticated", "referred", "test", "sample", "patient",
    "name", "age", "sex", "gender", "date", "client", "location", "approved",
    "printed", "collected", "registration", "passport", "lab id", "status",
    "physician", "doctor", "dr.", "process", "information", "interpretation",
    "note:", "comment", "remark", "scan", "qr code", "electronically",
    "result", "unit", "biological", "ref", "interval", "method",
    "kidney foundation", "discrepancy", "recommended", "correlation",
    "variability", "specimen", "defined", "ratio of", "history of",
    "approximately", "neuromuscular", "incidence", "associated with",
    "synthesized", "fat soluble", "exists in", "absorption", "baseline",
    "window", "peak", "possibility", "verified", "confirmatory", "declaring",
    "run number", "rack id", "analysis", "unknown", "sample id:",
]

CBC_TESTS = [
    "hemoglobin", "hb", "haemoglobin",
    "rbc", "red blood cell", "erythrocyte",
    "wbc", "white blood cell", "leucocyte", "leukocyte", "total wbc",
    "platelet", "plt", "thrombocyte",
    "hematocrit", "hct", "pcv",
    "mcv", "mean corpuscular volume",
    "mch", "mean corpuscular hemoglobin",
    "mchc",
    "rdw", "red cell distribution",
    "neutrophil", "lymphocyte", "monocyte", "eosinophil", "basophil",
    "esr", "sed rate", "erythrocyte sedimentation",
    "mpv", "mean platelet volume",
]

LIPID_TESTS = [
    "cholesterol", "total cholesterol",
    "triglyceride", "tg",
    "hdl", "high density",
    "ldl", "low density", "direct ldl",
    "vldl", "very low density",
    "non-hdl",
    "chol/hdl", "ldl/hdl", "ratio",
]

BIOCHEMISTRY_TESTS = [
    "glucose", "blood sugar", "fasting blood sugar", "fbs", "rbs", "random blood sugar",
    "urea", "bun", "blood urea nitrogen",
    "creatinine", "creat", "serum creatinine",
    "uric acid",
    "bilirubin", "total bilirubin", "direct bilirubin", "indirect bilirubin",
    "sgpt", "alt", "alanine aminotransferase",
    "sgot", "ast", "aspartate aminotransferase",
    "alkaline phosphatase", "alp",
    "ggt", "gamma gt",
    "total protein", "albumin", "globulin", "a/g ratio",
    "calcium", "serum calcium",
    "phosphorus", "phosphate",
    "sodium", "na+",
    "potassium", "k+",
    "chloride", "cl-",
    "magnesium", "mg",
    "iron", "serum iron", "ferritin", "tibc",
    "vitamin d", "25-hydroxy",
    "tsh", "thyroid",
    "t3", "t4",
    "psa", "prostate",
    "microalbumin",
]


def parse_medical_report(content: PDFContent) -> MedicalReportResponse:
    """Parse a medical report from extracted PDF content."""
    error_msg = None

    try:
        patient_info = extract_patient_info(content.text)
    except Exception as e:
        patient_info = PatientInfo()
        error_msg = f"Error parsing patient info: {e}"

    try:
        sections = split_into_sections(content.text)
        reports = extract_reports(sections, content.tables, content.text)
    except Exception as e:
        reports = Reports()
        if error_msg:
            error_msg += f"; Error parsing reports: {e}"
        else:
            error_msg = f"Error parsing reports: {e}"

    return MedicalReportResponse(
        patient_info=patient_info,
        reports=reports,
        error=error_msg,
    )


def extract_patient_info(text: str) -> PatientInfo:
    """Extract patient demographic information from report text."""
    info = {
        "name": None,
        "age": None,
        "gender": None,
        "lab_id": None,
        "report_date": None,
    }

    header_text = text[:3000] if len(text) > 3000 else text

    for field, patterns in PATIENT_INFO_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, header_text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1)
                if value:
                    value = clean_text(value)
                    if field == "age":
                        info[field] = extract_age(value)
                    elif field == "gender":
                        info[field] = normalize_gender(value)
                    elif field == "report_date":
                        info[field] = normalize_date(value)
                    elif field == "name":
                        info[field] = _clean_patient_name(value)
                    else:
                        info[field] = value
                    break

    return PatientInfo(**info)


def _clean_patient_name(name: str) -> Optional[str]:
    """Clean and validate patient name."""
    if not name:
        return None

    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"[^A-Za-z\s\.]", "", name).strip()

    # Filter out common non-name words
    skip_words = ["client", "name", "patient", "lab", "id", "sterling", "accuris", "buddy"]
    name_lower = name.lower()
    if any(word in name_lower for word in skip_words):
        # Check if it's just these words
        words = name_lower.split()
        if all(any(skip in w for skip in skip_words) for w in words):
            return None

    if len(name) < 2 or len(name) > 100:
        return None

    return name.title()


def extract_reports(sections: ReportSections, tables: list, full_text: str) -> Reports:
    """Extract all test reports from sections and tables."""
    cbc = []
    lipid_profile = []
    biochemistry = []
    hba1c = []
    blood_group = BloodGroup()

    # Parse each section
    if sections.cbc:
        cbc = _parse_test_section(sections.cbc, CBC_TESTS)

    if sections.lipid_profile:
        lipid_profile = _parse_test_section(sections.lipid_profile, LIPID_TESTS)

    if sections.biochemistry:
        biochemistry = _parse_test_section(sections.biochemistry, BIOCHEMISTRY_TESTS)

    if sections.hba1c:
        hba1c = _parse_hba1c_section(sections.hba1c)

    if sections.blood_group:
        blood_group = _parse_blood_group_section(sections.blood_group)

    # Fallback parsing for unclassified text
    if sections.unclassified or (not any([cbc, lipid_profile, biochemistry, hba1c])):
        text_to_parse = sections.unclassified or sections.raw_text
        fallback_results = _parse_fallback(text_to_parse)

        if not cbc:
            cbc = fallback_results.get("cbc", [])
        if not lipid_profile:
            lipid_profile = fallback_results.get("lipid_profile", [])
        if not biochemistry:
            biochemistry = fallback_results.get("biochemistry", [])
        if not hba1c:
            hba1c = fallback_results.get("hba1c", [])
        if not blood_group.type:
            blood_group = fallback_results.get("blood_group", BloodGroup())

    # Try to extract blood group from full text if not found
    if not blood_group.type:
        blood_group = _parse_blood_group_section(full_text)

    # Parse tables
    for table in tables:
        table_results = _parse_table(table)
        cbc.extend(table_results.get("cbc", []))
        lipid_profile.extend(table_results.get("lipid_profile", []))
        biochemistry.extend(table_results.get("biochemistry", []))

    return Reports(
        cbc=_deduplicate_results(cbc),
        lipid_profile=_deduplicate_results(lipid_profile),
        biochemistry=_filter_valid_results(_deduplicate_results(biochemistry)),
        hba1c=_deduplicate_results(hba1c),
        blood_group=blood_group,
    )


def _is_valid_test_name(name: str) -> bool:
    """Check if a string looks like a valid test name."""
    if not name or len(name) < 2:
        return False

    name_lower = name.lower()

    # Check for noise indicators
    for noise in NOISE_INDICATORS:
        if noise in name_lower:
            return False

    # Test name should not be too long (probably a sentence)
    if len(name) > 60:
        return False

    # Should not contain too many words (test names are usually 1-4 words)
    words = name.split()
    if len(words) > 6:
        return False

    return True


def _filter_valid_results(results: list[TestResult]) -> list[TestResult]:
    """Filter out results that don't look like valid test results."""
    return [r for r in results if _is_valid_test_name(r.test_name)]


def _parse_test_section(text: str, known_tests: list[str]) -> list[TestResult]:
    """Parse a test section and extract test results."""
    results = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        result = _parse_test_line(line, known_tests)
        if result and _is_valid_test_name(result.test_name):
            results.append(result)

    return results


def _parse_test_line(line: str, known_tests: list[str]) -> Optional[TestResult]:
    """Parse a single line to extract test result."""
    line_lower = line.lower()

    # Check if line contains known test
    is_known_test = any(test in line_lower for test in known_tests)
    if not is_known_test:
        return None

    # Skip lines that look like headers or noise
    if any(noise in line_lower for noise in NOISE_INDICATORS[:20]):
        return None

    # Patterns for extracting test data
    patterns = [
        # Standard: TestName Value Unit RefRange (numeric)
        r"^([A-Za-z][A-Za-z\s\(\)\-\+\/]+?)\s+([HLhl]?\s*[\d,\.]+)\s+([a-zA-Z/%µμ\^0-9\-\/\*×x]+)\s+([\d\.\-,]+\s*[-–]\s*[\d\.,]+)",
        # TestName Value Unit with text ref range (lipid format): "Cholesterol 189.0 mg/dL Desirable"
        r"^([A-Za-z][A-Za-z\s\(\)\-\+\/]+?)\s+([HLhl]?\s*[\d,\.]+)\s+(mg/dL|mmol/L|g/dL|%|U/L|mIU/L|ng/mL|pg/mL|fL|/cmm|million/cmm)\s+\w+",
        # TestName Value Unit (no ref range)
        r"^([A-Za-z][A-Za-z\s\(\)\-\+\/]+?)\s+([HLhl]?\s*[\d,\.]+)\s+([a-zA-Z/%µμ\^0-9\-\/\*×x]+)\s*$",
        # TestName Value Unit followed by anything
        r"^([A-Za-z][A-Za-z\s\(\)\-\+\/]+?)\s+([HLhl]?\s*[\d,\.]+)\s+(mg/dL|mmol/L|g/dL|%|U/L|mIU/L|ng/mL|pg/mL|fL|/cmm|million/cmm|mm/1hr)",
        # With colon separator
        r"^([A-Za-z][A-Za-z\s\(\)\-\+\/]+?)\s*[:\-]\s*([HLhl]?\s*[\d,\.]+)\s*([a-zA-Z/%µμ\^0-9\-\/\*×x]+)?",
    ]

    for pattern in patterns:
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            test_name = clean_text(match.group(1))
            raw_value = match.group(2) or ""
            unit = clean_text(match.group(3)) if len(match.groups()) >= 3 and match.group(3) else None
            ref_range = clean_text(match.group(4)) if len(match.groups()) >= 4 and match.group(4) else None

            flag, cleaned_value = extract_flag(raw_value)
            value = parse_number(cleaned_value)
            if flag is None:
                flag = infer_flag_from_reference_range(value, ref_range)

            if value is not None and _is_valid_test_name(test_name):
                return TestResult(
                    test_name=test_name,
                    value=value,
                    unit=unit,
                    reference_range=ref_range,
                    flag=flag,
                )

    return None


def _parse_hba1c_section(text: str) -> list[TestResult]:
    """Parse HbA1c section specifically."""
    results = []

    patterns = [
        r"HbA1c\s+([HLhl]?\s*[\d\.]+)\s*%?\s*([\d\.\-]+\s*[-–]\s*[\d\.]+)?",
        r"HbA1c\s*[:\-]?\s*([HLhl]?\s*[\d\.]+)\s*(%)?",
        r"Glycated\s*H[ae]moglobin\s*[:\-]?\s*([HLhl]?\s*[\d\.]+)\s*(%)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_value = match.group(1)
            ref_range = None
            if len(match.groups()) >= 2 and match.group(2):
                # Check if group 2 is a reference range or unit
                g2 = match.group(2)
                if "-" in g2 or "–" in g2:
                    ref_range = g2

            flag, cleaned_value = extract_flag(raw_value)
            value = parse_number(cleaned_value)

            if value is not None:
                # Determine flag based on value if not already set
                if flag is None:
                    flag = infer_flag_from_reference_range(value, ref_range or "4.0 - 5.6")

                results.append(
                    TestResult(
                        test_name="HbA1c",
                        value=value,
                        unit="%",
                        reference_range=ref_range or "4.0 - 5.6",
                        flag=flag,
                    )
                )
                break

    return results


def _parse_blood_group_section(text: str) -> BloodGroup:
    """Parse blood group section."""

    # Look for ABO type and Rh factor separately (common format)
    abo_match = re.search(r'ABO\s*(?:Type|Group)?\s*[:\-]?\s*["\']?([ABO]+)["\']?', text, re.IGNORECASE)
    rh_match = re.search(r'Rh\s*(?:\(D\))?\s*(?:Type|Factor)?\s*[:\-]?\s*(Positive|Negative|Pos|Neg|\+|\-)', text, re.IGNORECASE)

    if abo_match:
        blood_type = abo_match.group(1).upper()
        if rh_match:
            rh = rh_match.group(1).lower()
            if rh in ("positive", "pos", "+"):
                blood_type += "+"
            elif rh in ("negative", "neg", "-"):
                blood_type += "-"
        return BloodGroup(type=blood_type)

    # Standard patterns
    patterns = [
        r"Blood\s*(?:Group|Type)\s*[:\-]?\s*([ABO]+[+\-]?)",
        r"\b([ABO])\s*(Positive|Negative|Pos|Neg|\+|\-)",
        r"\b(A\+|A\-|B\+|B\-|AB\+|AB\-|O\+|O\-)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if len(match.groups()) > 1 and match.group(2):
                blood_type = match.group(1).upper()
                rh = match.group(2)
                if rh.lower() in ("positive", "pos", "+"):
                    blood_type += "+"
                elif rh.lower() in ("negative", "neg", "-"):
                    blood_type += "-"
            else:
                blood_type = match.group(1).upper()

            return BloodGroup(type=blood_type)

    return BloodGroup()


def _parse_fallback(text: str) -> dict:
    """Fallback parsing when section detection fails."""
    results = {
        "cbc": [],
        "lipid_profile": [],
        "biochemistry": [],
        "hba1c": [],
        "blood_group": BloodGroup(),
    }

    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        line_lower = line.lower()

        # Skip obvious non-test lines
        if any(noise in line_lower for noise in NOISE_INDICATORS[:15]):
            continue

        if any(test in line_lower for test in CBC_TESTS):
            result = _parse_test_line(line, CBC_TESTS)
            if result:
                results["cbc"].append(result)

        elif any(test in line_lower for test in LIPID_TESTS):
            result = _parse_test_line(line, LIPID_TESTS)
            if result:
                results["lipid_profile"].append(result)

        elif any(test in line_lower for test in BIOCHEMISTRY_TESTS):
            result = _parse_test_line(line, BIOCHEMISTRY_TESTS)
            if result:
                results["biochemistry"].append(result)

        elif "hba1c" in line_lower or "glycated" in line_lower:
            hba1c_results = _parse_hba1c_section(line)
            results["hba1c"].extend(hba1c_results)

        elif "blood group" in line_lower or "blood type" in line_lower or "abo" in line_lower:
            bg = _parse_blood_group_section(line)
            if bg.type:
                results["blood_group"] = bg

    return results


def _parse_table(table: list[list[str]]) -> dict:
    """Parse a table and extract test results."""
    results = {
        "cbc": [],
        "lipid_profile": [],
        "biochemistry": [],
    }

    if not table or len(table) < 2:
        return results

    header = table[0] if table else []
    header_lower = [str(h).lower() for h in header]

    name_idx = _find_column_index(header_lower, ["test", "parameter", "investigation", "name"])
    value_idx = _find_column_index(header_lower, ["result", "value", "observed"])
    unit_idx = _find_column_index(header_lower, ["unit", "units"])
    ref_idx = _find_column_index(header_lower, ["reference", "normal", "range", "ref"])

    if name_idx is None or value_idx is None:
        return results

    for row in table[1:]:
        if len(row) <= max(name_idx, value_idx):
            continue

        test_name = str(row[name_idx]).strip() if row[name_idx] else ""
        raw_value = str(row[value_idx]).strip() if row[value_idx] else ""
        unit = str(row[unit_idx]).strip() if unit_idx is not None and len(row) > unit_idx and row[unit_idx] else None
        ref_range = str(row[ref_idx]).strip() if ref_idx is not None and len(row) > ref_idx and row[ref_idx] else None

        if not test_name or not raw_value:
            continue

        if not _is_valid_test_name(test_name):
            continue

        flag, cleaned_value = extract_flag(raw_value)
        value = parse_number(cleaned_value)
        if flag is None:
            flag = infer_flag_from_reference_range(value, ref_range)

        if value is None:
            continue

        result = TestResult(
            test_name=test_name,
            value=value,
            unit=unit,
            reference_range=ref_range,
            flag=flag,
        )

        test_name_lower = test_name.lower()

        if any(t in test_name_lower for t in CBC_TESTS):
            results["cbc"].append(result)
        elif any(t in test_name_lower for t in LIPID_TESTS):
            results["lipid_profile"].append(result)
        elif any(t in test_name_lower for t in BIOCHEMISTRY_TESTS):
            results["biochemistry"].append(result)

    return results


def _find_column_index(header: list[str], keywords: list[str]) -> Optional[int]:
    """Find column index that matches any of the keywords."""
    for idx, col in enumerate(header):
        for keyword in keywords:
            if keyword in col:
                return idx
    return None


def _deduplicate_results(results: list[TestResult]) -> list[TestResult]:
    """Remove duplicate test results, keeping the first occurrence."""
    seen = set()
    unique = []

    for result in results:
        key = result.test_name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(result)

    return unique
