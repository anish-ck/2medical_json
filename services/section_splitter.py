"""
Section splitter service for medical reports.
Identifies and extracts different report sections based on headings.
"""

import re
from dataclasses import dataclass, field


SECTION_PATTERNS = {
    "cbc": [
        r"complete\s*blood\s*count",
        r"c\.?b\.?c\.?",
        r"haematology",
        r"hematology",
        r"blood\s*count",
        r"hemogram",
        r"full\s*blood\s*count",
    ],
    "lipid_profile": [
        r"lipid\s*profile",
        r"lipid\s*panel",
        r"cholesterol\s*profile",
        r"lipids",
    ],
    "biochemistry": [
        r"biochemistry",
        r"clinical\s*chemistry",
        r"metabolic\s*panel",
        r"liver\s*function",
        r"kidney\s*function",
        r"renal\s*function",
        r"lft",
        r"kft",
        r"rft",
    ],
    "hba1c": [
        r"hba1c",
        r"hb\s*a1c",
        r"glycated\s*h[ae]moglobin",
        r"glycosylated\s*h[ae]moglobin",
        r"a1c",
    ],
    "blood_group": [
        r"blood\s*group",
        r"blood\s*type",
        r"abo\s*group",
        r"rh\s*factor",
        r"blood\s*grouping",
    ],
}


@dataclass
class ReportSections:
    """Container for identified report sections."""

    header: str = ""
    cbc: str = ""
    lipid_profile: str = ""
    biochemistry: str = ""
    hba1c: str = ""
    blood_group: str = ""
    unclassified: str = ""
    raw_text: str = ""


def split_into_sections(text: str) -> ReportSections:
    """
    Split medical report text into categorized sections.

    Args:
        text: Full text extracted from the medical report

    Returns:
        ReportSections object with text organized by section type
    """
    sections = ReportSections(raw_text=text)

    if not text:
        return sections

    lines = text.split("\n")
    section_boundaries = _find_section_boundaries(lines)

    if not section_boundaries:
        sections.unclassified = text
        return sections

    sorted_boundaries = sorted(section_boundaries, key=lambda x: x[1])

    for i, (section_type, start_line) in enumerate(sorted_boundaries):
        if i + 1 < len(sorted_boundaries):
            end_line = sorted_boundaries[i + 1][1]
        else:
            end_line = len(lines)

        section_text = "\n".join(lines[start_line:end_line])

        current = getattr(sections, section_type)
        if current:
            setattr(sections, section_type, current + "\n" + section_text)
        else:
            setattr(sections, section_type, section_text)

    if sorted_boundaries:
        first_section_start = sorted_boundaries[0][1]
        sections.header = "\n".join(lines[:first_section_start])

    return sections


def _find_section_boundaries(lines: list[str]) -> list[tuple[str, int]]:
    """
    Find the starting line numbers for each section.

    Args:
        lines: List of text lines from the report

    Returns:
        List of (section_type, line_number) tuples
    """
    boundaries = []

    for line_num, line in enumerate(lines):
        line_lower = line.lower().strip()

        if not line_lower or len(line_lower) < 3:
            continue

        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line_lower, re.IGNORECASE):
                    boundaries.append((section_type, line_num))
                    break
            else:
                continue
            break

    return boundaries


def identify_section_type(text: str) -> str:
    """
    Identify the section type from a text snippet.

    Args:
        text: Text snippet to analyze

    Returns:
        Section type string or 'unknown'
    """
    text_lower = text.lower()

    for section_type, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return section_type

    return "unknown"


def get_section_keywords() -> dict[str, list[str]]:
    """
    Get all section identification keywords.

    Returns:
        Dictionary mapping section types to their keyword patterns
    """
    return SECTION_PATTERNS.copy()
