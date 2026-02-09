"""
Financial Audio Intelligence — RAG Service
Main entry point for the FastAPI application.
"""

import logging
from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes import router

# Load environment variables from .env
load_dotenv()

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rag.main")

app = FastAPI(
    title="Financial Audio Intelligence — RAG Service",
    description="Call-centric risk grounding pipeline for financial call analysis",
    version="2.0.0",
)

# Register API routes
app.include_router(router)

logger.info("🚀 RAG Service initialized — v2.0.0")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "ok", "service": "rag-pipeline"}
