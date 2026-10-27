# BeatBatch

<div align="center">

```text
  ____                  _   ____          _       _     
 | __ )   ___    __ _  | |_| __ )   __ _ | |_  __| |__  
 |  _ \  / _ \  / _` | | __|  _ \  / _` || __|/ _| '_ \ 
 | |_) ||  __/ | (_| | | |_| |_) || (_| || |_| (_| | | |
 |____/  \___|  \__,_|  \__|____/  \__,_| \__|\__|_| |_|
```

### *Drop your links. Get your beats.*

A modern, high-speed batch YouTube-to-MP3 extraction engine with real-time telemetry, concurrent worker queues, glassmorphic UI, and containerized packaging.

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_19_TypeScript-61DAFB?logo=react)](https://react.dev)
[![Vite](https://img.shields.io/badge/Bundler-Vite_8-646CFF?logo=vite)](https://vitejs.dev)
[![yt-dlp](https://img.shields.io/badge/Downloader-yt--dlp-red?logo=youtube)](https://github.com/yt-dlp/yt-dlp)
[![FFmpeg](https://img.shields.io/badge/Audio-FFmpeg-007808?logo=ffmpeg)](https://ffmpeg.org)
[![Docker](https://img.shields.io/badge/Packaging-Docker_Compose-2496ED?logo=docker)](https://www.docker.com)
[![Tests](https://img.shields.io/badge/Tests-Pytest_%26_Vitest-4CAF50)](https://pytest.org)

</div>

---

## Table of Contents

- [Features](#features)
- [Screenshots & UI Showcase](#screenshots--ui-showcase)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [Option A: Docker Compose (Recommended)](#option-a-docker-compose-recommended)
  - [Option B: Local Development](#option-b-local-development)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Configuration Reference](#configuration-reference)
- [yt-dlp Maintenance & Upgrades](#yt-dlp-maintenance--upgrades)
- [Troubleshooting](#troubleshooting)
  - [1. FFmpeg Not Found](#1-ffmpeg-not-found)
  - [2. HTTP 403 Forbidden & YouTube Bot Detection](#2-http-403-forbidden--youtube-bot-detection)
  - [3. Outdated yt-dlp & Extraction Errors](#3-outdated-yt-dlp--extraction-errors)
  - [4. Rate Limit (HTTP 429) & Input Size Limits](#4-rate-limit-http-429--input-size-limits)
- [Architecture & Project Structure](#architecture--project-structure)
- [Legal Disclaimer](#legal-disclaimer)

---

## Features

- **Batch Link Processing**: Paste dozens of YouTube links at once. Supports watch URLs, `youtu.be` shortlinks, YouTube Shorts, and YouTube Music links.
- **Smart Validation & Sanitization**: Live debounced client & backend validation; automatically extracts video IDs, removes tracking query parameters, strips playlist references, and deduplicates identical links while preserving order.
- **Selectable Bitrates**: High-quality MP3 encoding powered by FFmpeg: **128 kbps**, **192 kbps** (standard), **256 kbps**, or **320 kbps** (audiophile).
- **Real-Time SSE Telemetry**: Server-Sent Events stream live status, percent completion, download speed (KiB/s, MiB/s), ETA, and duration per item without polling.
- **Dual Delivery Modes**: Download individual MP3 tracks on demand or grab the entire finished batch as a single, cleanly named ZIP file (`BeatBatch_YYYY-MM-DD.zip`).
- **Resilient Retry Mechanism**: Retry any individual failed link or click **"Retry all failed"** with a single click.
- **Security & Safeguards**:
  - In-memory sliding-window rate limiting on `POST /api/jobs` (15 requests/min per IP by default).
  - Strict host whitelist enforcing valid YouTube domains only (`youtube.com`, `youtu.be`, `music.youtube.com`).
  - Request payload size protection (150 KB max text input).
  - Path-traversal sanitization preventing directory escape during file downloads.
  - Automatic 24-hour cleanup cron deleting stale downloads and freeing disk space.
- **Rich Dark/Light Glassmorphic UX**:
  - Dynamic ambient gradient glow and glassmorphism styling.
  - Smooth Dark / Light theme toggle with local storage persistence.
  - Drag-and-drop `.txt` file import onto the link editor.
  - Keyboard shortcut: <kbd>Ctrl+Enter</kbd> (or <kbd>Cmd+Enter</kbd>) to instantly start jobs.
  - Slide-out Session History drawer tracking past jobs with one-click re-download.
  - Toast notification banners for batch events, completion, and errors.
  - Complete WCAG accessibility: `role="progressbar"`, `aria-valuenow`, `aria-live` screen reader announcements, and high-visibility focus indicators.

---

## Screenshots & UI Showcase

### 1. Main Batch View (Dark Mode)
```text
+------------------------------------------------------------------------------------+
|  [~] BeatBatch               Drop your links. Get your beats.    [☀ Light] [History] |
+------------------------------------------------------------------------------------+
|                                                                                    |
|  +-- Input YouTube Links --------------------------------------------------------+ |
|  | https://www.youtube.com/watch?v=dQw4w9WgXcQ                                    | |
|  | https://youtu.be/3JZ_D3ELwOQ                                                   | |
|  | https://music.youtube.com/watch?v=kXYiU_JCYtU                                  | |
|  |                                                                                | |
|  +--------------------------------------------------------------------------------+ |
|  [ ✓ 3 valid links ] [ Drop .txt or Import ] [ Bitrate: (128) (192*) (256) (320) ] |
|                                                                                    |
|                           [ ▶ Start Download (Ctrl+Enter) ]                        |
+------------------------------------------------------------------------------------+
```

### 2. Active Batch Progress with Live SSE Telemetry
```text
+------------------------------------------------------------------------------------+
|  BATCH IN PROGRESS: 2 of 3 finished                                [ Cancel Batch ] |
|  [========================================....................] 67%                |
+------------------------------------------------------------------------------------+
|  [#1] Rick Astley - Never Gonna Give You Up                         [DONE]         |
|       [==========================================================] 100%             |
|       3:32 • 192 kbps • 4.8 MB                                [ ↓ Download MP3 ]   |
|                                                                                    |
|  [#2] Lofi Hip Hop Radio - Beats to Relax/Study To                  [DOWNLOADING]  |
|       [==============================............................] 54%              |
|       Speed: 3.4 MiB/s • ETA: 00:12 • 4:15                                        |
|                                                                                    |
|  [#3] Synthwave Chill Mix 2026                                      [QUEUED]       |
|       [..........................................................] 0%              |
|       Waiting for available worker slot...                                         |
+------------------------------------------------------------------------------------+
|  [ ↓ Download all as ZIP ]                                   [ ⟳ Retry all failed ]|
+------------------------------------------------------------------------------------+
```

---

## Prerequisites

| Dependency | Minimum Version | Notes |
| ---------- | --------------- | ----- |
| **Python** | `3.11+` | Backend runtime |
| **Node.js** | `18+` (or `20+`) | Frontend build tool |
| **FFmpeg** | Any modern release | Required for audio extraction & MP3 conversion |
| **Docker** | `20+` / Docker Compose v2 | Optional: for containerized deployment |

---

## Quick Start

### Option A: Docker Compose (Recommended)

Run the entire application (Backend + Frontend + Nginx Proxy + FFmpeg) with a single command:

```bash
docker compose up --build
```

- **Frontend Application**: <http://localhost:5173>
- **Backend API & Docs**: <http://localhost:8000/docs>
- **Health Check**: <http://localhost:8000/api/health>

To stop the containers:
```bash
docker compose down
```

---

### Option B: Local Development

#### 1. Backend Setup (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Customize environment settings
copy .env.example .env

# Run FastAPI server
uvicorn app.main:app --reload --port 8000
```

Verify backend: <http://127.0.0.1:8000/api/health> returns `{"status":"ok"}`.

#### 2. Frontend Setup (React + Vite)

In a separate terminal:

```bash
cd frontend

# Install Node modules
npm install

# Start Vite dev server
npm run dev
```

Open your browser at <http://localhost:5173>.

---

## Testing & Quality Assurance

Both the backend and frontend include test suites covering parser logic, download orchestration, mocks, file delivery, rate limiting, and component states.

### Run Backend Tests (pytest)

```bash
cd backend
.\venv\Scripts\activate
pytest -v
```

**Coverage includes**:
- `test_link_parser.py`: URL cleaning, ID extraction, duplicate filtering, invalid line reporting.
- `test_job_manager.py`: Async job lifecycle, cancellation, mock `yt-dlp` download results, SSE broadcast queues, retry logic.
- `test_file_endpoints.py`: Single MP3 download, ZIP archive generation, path traversal blocking, sliding window rate limiter (429), and 150 KB input overflow guard (422).

### Run Frontend Tests (Vitest + React Testing Library)

```bash
cd frontend
npm run test
```

**Coverage includes**:
- `LinkInput.test.tsx`: Textarea input, live debounced valid/invalid counter chips, bitrate selector, keyboard shortcut trigger.
- `ItemCard.test.tsx`: Progress bar styling, accessible ARIA attributes (`aria-valuenow`), download speed/ETA telemetry, error states, and individual retry callback.

### Run Linting & Production Build Checks

```bash
cd frontend
npm run lint    # Runs oxlint
npm run build   # Typechecks with tsc and builds production dist
```

---

## Configuration Reference

Configure backend behavior by editing `backend/.env` or providing environment variables:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `HOST` | `127.0.0.1` | Network interface to bind backend |
| `PORT` | `8000` | Port for backend HTTP server |
| `LOG_LEVEL` | `INFO` | Structured logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated list of allowed CORS origins |
| `FILE_RETENTION_HOURS` | `24` | Hours before completed MP3 job files are pruned |
| `MAX_CONCURRENT_DOWNLOADS`| `3` | Worker thread concurrency limit |
| `RATE_LIMIT_REQUESTS` | `15` | Maximum job creation requests allowed per IP per window |
| `RATE_LIMIT_WINDOW_SECONDS`| `60` | Time window (seconds) for IP rate limiter |
| `COOKIES_FROM_BROWSER` | *(empty)* | Optional: Browser name to extract cookies from (e.g. `chrome`, `firefox`, `edge`) |
| `COOKIES_FILE` | *(empty)* | Optional: Absolute path to a `cookies.txt` file |

---

## yt-dlp Maintenance & Upgrades

### Why does yt-dlp need updates?
YouTube regularly updates its streaming infrastructure, player JavaScript, signature ciphers (`n-token`), and bot detection protocols. Outdated downloaders can experience:
- Extraction failures (`Unable to extract video data`)
- HTTP 403 Forbidden errors
- Throttled download speeds (< 50 KiB/s)

### Upgrading yt-dlp in BeatBatch

BeatBatch includes dedicated upgrade scripts:

- **Windows**: Double-click `scripts/update_ytdlp.bat`
- **Linux / macOS**: Run `./scripts/update_ytdlp.sh`
- **Manual (Python)**:
  ```bash
  python scripts/update_ytdlp.py
  ```

The script automatically detects your active virtual environment, upgrades `yt-dlp` to the latest release, verifies package functionality, and updates `requirements.txt`.

---

## Troubleshooting

### 1. FFmpeg Not Found
**Symptom**: Backend startup fails with:
`ERROR: FFmpeg is not installed or not in PATH.`

**Solution**:
- **Windows**:
  ```powershell
  winget install Gyan.FFmpeg
  # or via Chocolatey:
  choco install ffmpeg
  ```
  Restart your terminal and verify with `ffmpeg -version`.
- **macOS**:
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```

---

### 2. HTTP 403 Forbidden & YouTube Bot Detection
**Symptom**: Download fails with error:
`Sign in to confirm you're not a bot` or `HTTP Error 403: Forbidden`.

**Cause**: YouTube flags requests from certain data centers or aggressive IP pools.

**Solutions**:
1. **Extract Browser Cookies**: Set `COOKIES_FROM_BROWSER` in `backend/.env`:
   ```ini
   COOKIES_FROM_BROWSER=chrome
   # Options: chrome, edge, firefox, brave, opera, vivaldi
   ```
2. **Use a `cookies.txt` file**:
   - Install a browser extension such as "Get cookies.txt LOCALLY".
   - Export your YouTube cookies to a file.
   - Point `COOKIES_FILE` in `backend/.env` to the exported file:
     ```ini
     COOKIES_FILE=C:\path\to\youtube_cookies.txt
     ```
3. **Reduce Concurrency**: Lower `MAX_CONCURRENT_DOWNLOADS=1` in `backend/.env` to avoid triggering IP burst thresholds.

---

### 3. Outdated yt-dlp & Extraction Errors
**Symptom**: Downloads fail on videos that play fine in your web browser.

**Solution**:
Run the upgrade utility:
```bash
python scripts/update_ytdlp.py
```
Then restart the backend server (`uvicorn`).

---

### 4. Rate Limit (HTTP 429) & Input Size Limits
**Symptom**: API returns `HTTP 429 Too Many Requests: Rate limit exceeded. Try again in X seconds.`

**Solution**:
BeatBatch enforces a sliding-window rate limit (default 15 jobs per 60 seconds per IP). If running in a trusted local environment or testing heavily, adjust `RATE_LIMIT_REQUESTS` in `backend/.env`:
```ini
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

---

## Architecture & Project Structure

```text
BeatBatch/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application, CORS, structured logging
│   │   ├── config.py                # Environment settings via Pydantic
│   │   ├── logging_config.py        # Structured JSON-friendly log formatter
│   │   ├── models/                  # Pydantic schemas (jobs, items, requests)
│   │   ├── routers/
│   │   │   ├── health.py            # GET /api/health
│   │   │   ├── validate.py          # POST /api/validate
│   │   │   ├── jobs.py              # POST /api/jobs, SSE streaming, cancellation
│   │   │   └── files.py             # GET /files/{item_index}, GET /zip
│   │   └── services/
│   │       ├── link_parser.py       # URL extraction, cleaning, and host validation
│   │       ├── downloader.py        # Python yt-dlp wrapper & FFmpeg hook
│   │       ├── job_manager.py       # Thread pool execution, job status & event queue
│   │       ├── cleanup.py           # Background retention scheduler
│   │       └── rate_limiter.py      # In-memory sliding-window IP rate limiter
│   ├── tests/                       # Pytest test suite (56 tests)
│   ├── downloads/                   # Temporary directory for converted MP3 files
│   ├── Dockerfile                   # Python 3.11 + FFmpeg container definition
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/                     # Typed client (validate, jobs, events SSE)
│   │   ├── components/              # React UI components (LinkInput, ItemCard, etc.)
│   │   ├── context/                 # Toast notification & theme contexts
│   │   ├── hooks/                   # useJobEvents, useDebounce, useLocalStorage
│   │   └── test/                    # Vitest & React Testing Library suites
│   ├── Dockerfile                   # Multi-stage build + Nginx static server
│   ├── nginx.conf                   # Reverse proxy for /api/ and SSE streaming
│   └── package.json
│
├── scripts/
│   ├── update_ytdlp.py              # Cross-platform yt-dlp updater
│   ├── update_ytdlp.bat             # Windows shortcut
│   └── update_ytdlp.sh              # Unix shortcut
│
├── docker-compose.yml               # Unified multi-container orchestration
└── README.md
```

---

## Legal Disclaimer

> [!CAUTION]
> **For Personal and Archival Use Only**
>
> BeatBatch is developed as an educational project and personal utility. Users are solely responsible for ensuring they have the legal right to access and download any media content. Downloading copyrighted audio without explicit authorization from the copyright holder may violate YouTube's Terms of Service and applicable intellectual property laws. The authors and maintainers of BeatBatch assume no liability for misuse of this tool.
