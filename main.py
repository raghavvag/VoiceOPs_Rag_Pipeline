"""
Financial Audio Intelligence — RAG Service
Main entry point for the FastAPI application.
"""

from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="Financial Audio Intelligence — RAG Service",
    description="Call-centric risk grounding pipeline for financial call analysis",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "rag-pipeline"}
