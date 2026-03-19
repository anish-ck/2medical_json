"""
API routes for medical report parsing.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException

from models.schema import MedicalReportResponse, ErrorResponse
from services.pdf_extractor import extract_pdf_content
from services.parser import parse_medical_report


router = APIRouter()

ALLOWED_CONTENT_TYPES = ["application/pdf", "application/x-pdf"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/parse-medical-report",
    response_model=MedicalReportResponse,
    responses={
        200: {"description": "Successfully parsed medical report"},
        400: {"model": ErrorResponse, "description": "Invalid file or request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Parse Medical Report PDF",
    description="Upload a medical laboratory report PDF and receive structured JSON data.",
)
async def parse_medical_report_endpoint(
    file: UploadFile = File(..., description="Medical report PDF file"),
) -> MedicalReportResponse:
    """
    Parse a medical laboratory report PDF into structured JSON.

    Returns structured data including:
    - Patient information (name, age, gender, lab ID, report date)
    - Test results organized by category (CBC, Lipid Profile, Biochemistry, HbA1c, Blood Group)
    """
    _validate_file(file)

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading uploaded file: {e}")

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        pdf_content = extract_pdf_content(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF file: {e}")

    if not pdf_content.text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF. The file may be scanned/image-based or empty.")

    try:
        result = parse_medical_report(pdf_content)
    except Exception as e:
        return MedicalReportResponse(error=f"Parsing error: {e}. Partial data may be available.")

    return result


def _validate_file(file: UploadFile) -> None:
    """Validate the uploaded file."""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="File has no filename.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        if "pdf" not in file.content_type.lower():
            raise HTTPException(status_code=400, detail=f"Invalid content type: {file.content_type}.")


@router.get("/health", summary="Health Check")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "medical-report-parser"}
