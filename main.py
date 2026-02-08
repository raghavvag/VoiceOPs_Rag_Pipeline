"""
Financial Audio Intelligence — RAG Service
Main entry point for the FastAPI application.
"""

from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes import router

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="Financial Audio Intelligence — RAG Service",
    description="Call-centric risk grounding pipeline for financial call analysis",
    version="2.0.0",
)

# Register API routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "rag-pipeline"}
