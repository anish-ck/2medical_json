"""
Common utility functions for text processing and data cleaning.
"""

import re
from typing import Optional
from datetime import datetime


def clean_text(text: str) -> str:
    """
    Clean and normalize text by removing extra whitespace.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text with normalized whitespace
    """
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_number(value: str) -> Optional[float]:
    """
    Parse a string to a float, handling common formats.

    Args:
        value: String representation of a number

    Returns:
        Parsed float or None if parsing fails
    """
    if not value:
        return None

    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned or cleaned in (".", "-", "-."):
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_flag(text: str) -> tuple[Optional[str], str]:
    """
    Extract flag indicator (H/L) from text and return cleaned value.

    Args:
        text: Text that may contain H/L flag prefix

    Returns:
        Tuple of (flag, cleaned_text) where flag is 'high', 'low', or None
    """
    if not text:
        return None, ""

    text = str(text).strip()

    high_match = re.match(r"^[Hh]\s*(\d+\.?\d*)", text)
    if high_match:
        return "high", high_match.group(1)

    low_match = re.match(r"^[Ll]\s*(\d+\.?\d*)", text)
    if low_match:
        return "low", low_match.group(1)

    if text.upper().endswith(" H") or text.upper().endswith("(H)"):
        return "high", re.sub(r"\s*\(?H\)?\s*$", "", text, flags=re.IGNORECASE)

    if text.upper().endswith(" L") or text.upper().endswith("(L)"):
        return "low", re.sub(r"\s*\(?L\)?\s*$", "", text, flags=re.IGNORECASE)

    return None, text


def infer_flag_from_reference_range(value: Optional[float], reference_range: Optional[str]) -> Optional[str]:
    """Infer high/low flag from a numeric value and textual reference range."""
    if value is None or not reference_range:
        return None

    range_text = str(reference_range).strip()
    if not range_text:
        return None

    between = re.search(r"(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)", range_text)
    if between:
        low = float(between.group(1))
        high = float(between.group(2))
        if value < low:
            return "low"
        if value > high:
            return "high"
        return None

    lower_only = re.search(r"(?:>=|>|above|more\s+than|greater\s+than)\s*(-?\d+(?:\.\d+)?)", range_text, re.IGNORECASE)
    if lower_only:
        low = float(lower_only.group(1))
        return "low" if value < low else None

    upper_only = re.search(r"(?:<=|<|below|less\s+than)\s*(-?\d+(?:\.\d+)?)", range_text, re.IGNORECASE)
    if upper_only:
        high = float(upper_only.group(1))
        return "high" if value > high else None

    return None


def normalize_date(date_str: str) -> Optional[str]:
    """
    Normalize date string to YYYY-MM-DD format.

    Args:
        date_str: Date string in various formats

    Returns:
        Normalized date string or None if parsing fails
    """
    if not date_str:
        return None

    date_formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %B %Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
    ]

    cleaned = clean_text(date_str)

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return cleaned


def normalize_gender(gender: str) -> Optional[str]:
    """
    Normalize gender string to standard format.

    Args:
        gender: Gender string in various formats

    Returns:
        Normalized gender string (Male/Female/Other) or None
    """
    if not gender:
        return None

    gender = gender.strip().upper()

    if gender in ("M", "MALE"):
        return "Male"
    if gender in ("F", "FEMALE"):
        return "Female"
    if gender in ("O", "OTHER"):
        return "Other"

    return gender.title()


def extract_age(age_str: str) -> Optional[int]:
    """
    Extract age as integer from various formats.

    Args:
        age_str: Age string (e.g., "45", "45 Years", "45Y")

    Returns:
        Age as integer or None
    """
    if not age_str:
        return None

    match = re.search(r"(\d+)", str(age_str))
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None

    return None


def is_valid_test_value(value: str) -> bool:
    """
    Check if a string represents a valid test value.

    Args:
        value: String to check

    Returns:
        True if the string contains numeric data
    """
    if not value:
        return False

    return bool(re.search(r"\d", str(value)))
