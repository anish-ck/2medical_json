"""
Pydantic models for medical report structured output.
"""

from typing import Optional
from pydantic import BaseModel, Field


class PatientInfo(BaseModel):
    """Patient demographic information extracted from the report."""

    name: Optional[str] = Field(None, description="Patient's full name")
    age: Optional[int] = Field(None, description="Patient's age in years")
    gender: Optional[str] = Field(None, description="Patient's gender (Male/Female/Other)")
    lab_id: Optional[str] = Field(None, description="Laboratory ID or patient ID")
    report_date: Optional[str] = Field(None, description="Date of the report (YYYY-MM-DD)")


class TestResult(BaseModel):
    """Individual test result with value, unit, and reference range."""

    test_name: str = Field(..., description="Name of the test")
    value: Optional[float] = Field(None, description="Numeric test value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    reference_range: Optional[str] = Field(None, description="Normal reference range")
    flag: Optional[str] = Field(None, description="Flag indicator: 'high', 'low', or null")


class BloodGroup(BaseModel):
    """Blood group information."""

    type: Optional[str] = Field(None, description="Blood group type (e.g., A+, B-, O+)")


class Reports(BaseModel):
    """Collection of all test report sections."""

    cbc: list[TestResult] = Field(default_factory=list, description="Complete Blood Count results")
    lipid_profile: list[TestResult] = Field(default_factory=list, description="Lipid Profile results")
    biochemistry: list[TestResult] = Field(default_factory=list, description="Biochemistry results")
    hba1c: list[TestResult] = Field(default_factory=list, description="HbA1c results")
    blood_group: BloodGroup = Field(default_factory=BloodGroup, description="Blood group information")


class MedicalReportResponse(BaseModel):
    """Complete structured response for a medical report."""

    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    reports: Reports = Field(default_factory=Reports)
    error: Optional[str] = Field(None, description="Error message if parsing partially failed")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")
