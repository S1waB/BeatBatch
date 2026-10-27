"""
Application configuration loaded from environment variables.

Uses pydantic-settings so values can come from a .env file or
real environment variables. Defaults are development-friendly.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the BeatBatch backend."""

    # Directory where downloaded MP3 files are stored temporarily
    download_dir: str = "downloads"

    # Comma-separated list of allowed CORS origins
    cors_origins: str = "http://localhost:5173"

    # Uvicorn host / port (used when running via `python -m app.main`)
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Cookie settings (needed to bypass YouTube IP blocks) ──────────────
    # Browser to read cookies from automatically.
    # Supported values: "chrome", "edge", "firefox", "safari", "brave",
    #                   "opera", "chromium", "vivaldi", or "" to disable.
    # Set to "auto" to let BeatBatch try common browsers in order.
    cookies_from_browser: str = "auto"

    # Absolute path to a Netscape-format cookies.txt file (alternative to
    # browser extraction).  Leave empty to use browser cookies instead.
    cookie_file: str = ""

    # ── File delivery & cleanup ────────────────────────────────────────────
    # How long (hours) to keep downloaded MP3 folders before auto-deletion.
    file_retention_hours: int = 24

    # How often (hours) the cleanup sweep runs. Set to 0 to disable.
    cleanup_interval_hours: int = 1

    # Maximum number of YouTube links accepted per job.
    max_links_per_job: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton – import this everywhere
settings = Settings()
