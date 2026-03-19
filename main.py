"""
Medical Report Parser API

FastAPI application for parsing medical laboratory PDF reports
into structured JSON format.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router


app = FastAPI(
    title="Medical Report Parser API",
    description=(
        "A production-ready API for parsing medical laboratory PDF reports "
        "into structured JSON format. Supports CBC, Lipid Profile, Biochemistry, "
        "HbA1c, and Blood Group sections."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router, tags=["Medical Report Parser"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler to ensure API never crashes.
    Returns a 500 error with error details.
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {str(exc)}",
        },
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Medical Report Parser API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
