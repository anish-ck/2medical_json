# Medical Report Parser API

A FastAPI backend that converts medical laboratory PDF reports into structured JSON.

## Features

- PDF text extraction using pdfplumber
- Automatic section detection (CBC, Lipid Profile, Biochemistry, HbA1c, Blood Group)
- Patient information extraction
- Flag handling (high/low indicators)
- Table parsing support

## Project Structure

```
project/
├── main.py                  # FastAPI entry point
├── api/
│   └── routes.py           # API endpoints
├── services/
│   ├── pdf_extractor.py    # PDF text extraction
│   ├── section_splitter.py # Split report into sections
│   └── parser.py           # Extract structured data
├── models/
│   └── schema.py           # Pydantic response models
├── utils/
│   └── helpers.py          # Common utilities
└── requirements.txt
```

## Installation

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### POST /parse-medical-report

Upload a PDF and receive structured JSON.

```bash
curl -X POST "http://localhost:8000/parse-medical-report" \
  -F "file=@medical_report.pdf"
```

### GET /health

Health check endpoint.

## Response Format

```json
{
  "patient_info": {
    "name": "string",
    "age": 0,
    "gender": "string",
    "lab_id": "string",
    "report_date": "string"
  },
  "reports": {
    "cbc": [...],
    "lipid_profile": [...],
    "biochemistry": [...],
    "hba1c": [...],
    "blood_group": { "type": "string" }
  },
  "error": null
}
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
