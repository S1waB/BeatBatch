"""
conftest.py – shared pytest fixtures for BeatBatch backend tests.

Provides a FastAPI TestClient that bypasses the lifespan hook (which
requires FFmpeg to be installed) so unit tests can run in any CI
environment.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import validate


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Minimal FastAPI app with only the validate router – no lifespan."""
    _app = FastAPI()
    _app.include_router(validate.router)
    return _app


@pytest.fixture(scope="session")
def client(app: FastAPI) -> TestClient:
    """Synchronous TestClient for the minimal app."""
    return TestClient(app)
