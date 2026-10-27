"""
Health-check router.

Provides a lightweight GET /api/health endpoint that the frontend
(and monitoring tools) can use to verify the backend is alive.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return a simple status payload confirming the server is running."""
    return {"status": "ok"}
