#!/usr/bin/env python3
"""
BeatBatch – Complete Full-Stack Application Launcher

Starts the entire BeatBatch ecosystem with a single command:
  • Python Virtual Environment & Backend Dependencies
  • FFmpeg Audio Processing Engine
  • FastAPI REST API & OpenAPI Documentation (/docs)
  • Real-Time SSE Telemetry & Worker Queues
  • Node.js & Vite React Frontend
  • Automatic Port Detection, Health Probing & Browser Opening
  • Graceful process-tree cleanup on shutdown (Ctrl+C)
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DOWNLOADS_DIR = BACKEND_DIR / "downloads"


def print_banner() -> None:
    print(r"""
======================================================================
  ____                  _   ____          _       _     
 | __ )   ___    __ _  | |_| __ )   __ _ | |_  __| |__  
 |  _ \  / _ \  / _` | | __|  _ \  / _` || __|/ _| '_ \ 
 | |_) ||  __/ | (_| | | |_| |_) || (_| || |_| (_| | | |
 |____/  \___|  \__,_|  \__|____/  \__,_| \__|\__|_| |_|
               Drop your links. Get your beats.
======================================================================
""")


def check_ffmpeg() -> bool:
    """Verify that FFmpeg is available on PATH."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"[✓] FFmpeg engine located: {ffmpeg_path}")
        return True

    print("\n[!] WARNING: FFmpeg was not found on your system PATH!")
    print("    BeatBatch requires FFmpeg to convert YouTube audio streams to MP3.")
    print("    Install instructions:")
    print("      • Windows : winget install Gyan.FFmpeg")
    print("      • macOS   : brew install ffmpeg")
    print("      • Ubuntu  : sudo apt update && sudo apt install -y ffmpeg\n")
    return False


def get_or_create_backend_python() -> str:
    """Find or create backend virtual environment and return its Python binary."""
    # Existing virtual environment candidates
    candidates = [
        BACKEND_DIR / "venv" / "Scripts" / "python.exe",
        BACKEND_DIR / "venv" / "bin" / "python",
        ROOT_DIR / ".venv" / "Scripts" / "python.exe",
        ROOT_DIR / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.is_file():
            print(f"[✓] Virtualenv Python detected: {c}")
            return str(c)

    # If no virtual environment exists, create one in backend/venv
    venv_dir = BACKEND_DIR / "venv"
    print(f"[*] Creating Python virtual environment at {venv_dir}...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        py_exe = (
            venv_dir / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else venv_dir / "bin" / "python"
        )
        if py_exe.is_file():
            print(f"[✓] Created virtual environment: {py_exe}")
            # Install requirements
            req_file = BACKEND_DIR / "requirements.txt"
            if req_file.is_file():
                print("[*] Installing backend dependencies (pip install -r requirements.txt)...")
                subprocess.run([str(py_exe), "-m", "pip", "install", "-r", str(req_file)], check=True)
            return str(py_exe)
    except Exception as exc:
        print(f"[!] Virtual environment creation failed ({exc}). Using system interpreter.")

    return sys.executable


def ensure_backend_dependencies(py_exe: str) -> None:
    """Ensure required backend packages are installed."""
    check_code = "import fastapi, uvicorn, yt_dlp; print('ok')"
    res = subprocess.run([py_exe, "-c", check_code], capture_output=True, text=True)
    if res.returncode != 0:
        req_file = BACKEND_DIR / "requirements.txt"
        print("[*] Installing missing backend packages from requirements.txt...")
        if req_file.is_file():
            subprocess.run([py_exe, "-m", "pip", "install", "-r", str(req_file)], check=True)
        else:
            subprocess.run([py_exe, "-m", "pip", "install", "fastapi", "uvicorn[standard]", "yt-dlp", "pydantic-settings"], check=True)
    print("[✓] Backend Python packages verified.")


def get_npm_command() -> str:
    """Locate npm executable."""
    npm_cmd = shutil.which("npm.cmd") if sys.platform == "win32" else shutil.which("npm")
    if not npm_cmd:
        print("[!] ERROR: 'npm' not found on PATH. Node.js (18+) is required for the frontend.")
        print("    Download Node.js from https://nodejs.org/")
        sys.exit(1)
    print(f"[✓] Node/NPM detected: {npm_cmd}")
    return npm_cmd


def ensure_frontend_dependencies(npm_cmd: str) -> None:
    """Ensure frontend node_modules is installed."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.is_dir():
        print("[*] Installing frontend packages (npm install)...")
        subprocess.run([npm_cmd, "install"], cwd=FRONTEND_DIR, check=True)
    print("[✓] Frontend Node dependencies verified.")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a network port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def find_free_port(preferred: int, fallbacks: list[int] | None = None) -> int:
    """Use preferred port if free, otherwise find an available alternate port."""
    if not is_port_in_use(preferred):
        return preferred

    if fallbacks:
        for candidate in fallbacks:
            if not is_port_in_use(candidate):
                print(f"[i] Port {preferred} is in use. Using alternate port {candidate}.")
                return candidate

    return preferred


def sync_env_configurations(backend_port: int, frontend_port: int = 5173) -> None:
    """Sync backend and frontend environment files for seamless communication."""
    # Ensure backend downloads folder exists
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Update backend/.env
    backend_env = BACKEND_DIR / ".env"
    be_content = (
        f"# BeatBatch Backend Configuration\n"
        f"DOWNLOAD_DIR=downloads\n\n"
        f"# Allowed CORS origins (comma-separated)\n"
        f"CORS_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port},http://localhost,http://127.0.0.1\n\n"
        f"# Uvicorn host and port\n"
        f"HOST=0.0.0.0\n"
        f"PORT={backend_port}\n\n"
        f"COOKIES_FROM_BROWSER=\n"
        f"COOKIE_FILE=\n"
    )
    backend_env.write_text(be_content, encoding="utf-8")

    # 2. Update frontend/.env
    frontend_env = FRONTEND_DIR / ".env"
    fe_content = f"VITE_API_BASE=http://localhost:{backend_port}\n"
    frontend_env.write_text(fe_content, encoding="utf-8")


def wait_for_url(url: str, timeout_sec: float = 20.0) -> bool:
    """Poll a URL until it responds with HTTP 200 or times out."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BeatBatch-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


def terminate_tree(proc: subprocess.Popen | None, name: str) -> None:
    """Safely kill a process and all of its child processes."""
    if proc is None or proc.poll() is not None:
        return

    print(f"[*] Stopping {name} (PID: {proc.pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass


def forward_stream(stream, prefix: str) -> None:
    """Read a process stream line-by-line and print to stdout."""
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            text = line.rstrip()
            if text:
                print(f"{prefix} {text}")
    except Exception:
        pass


def main() -> None:
    print_banner()

    check_ffmpeg()
    py_exe = get_or_create_backend_python()
    ensure_backend_dependencies(py_exe)
    npm_cmd = get_npm_command()
    ensure_frontend_dependencies(npm_cmd)

    backend_port = find_free_port(8000, [8008, 8080, 8001, 8002, 8005, 8088])
    frontend_port = find_free_port(5173, [5174, 5175, 5176, 5177, 3000])

    sync_env_configurations(backend_port, frontend_port)

    backend_proc: subprocess.Popen | None = None
    frontend_proc: subprocess.Popen | None = None

    def handle_exit(sig=None, frame=None):
        print("\n\n[!] Shutdown signal received. Closing all BeatBatch servers...")
        terminate_tree(backend_proc, "Backend API")
        terminate_tree(frontend_proc, "Frontend App")
        print("[✓] All servers cleanly terminated. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print("\n" + "-" * 70)
    print(f"[*] Starting Backend API on http://localhost:{backend_port}...")
    backend_proc = subprocess.Popen(
        [
            py_exe,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            "0.0.0.0",
            "--port",
            str(backend_port),
        ],
        cwd=BACKEND_DIR,
    )

    print(f"[*] Starting Frontend on http://localhost:{frontend_port}...")
    frontend_proc = subprocess.Popen(
        [
            npm_cmd,
            "run",
            "dev",
            "--",
            "--host",
            "0.0.0.0",
            "--port",
            str(frontend_port),
            "--strictPort",
        ],
        cwd=FRONTEND_DIR,
    )

    print("[*] Probing services until online...")
    backend_ok = wait_for_url(f"http://127.0.0.1:{backend_port}/api/health", timeout_sec=15)
    frontend_ok = wait_for_url(f"http://127.0.0.1:{frontend_port}", timeout_sec=15)

    print("-" * 70)
    if backend_ok and frontend_ok:
        print("  🎉 BEATBATCH IS FULLY RUNNING AND ONLINE!\n")
        print(f"  ➜ 🖥️  Frontend Application : http://localhost:{frontend_port}")
        print(f"  ➜ ⚙️  FastAPI Backend API   : http://localhost:{backend_port}")
        print(f"  ➜ 📖 Interactive Docs (UI) : http://localhost:{backend_port}/docs")
        print(f"  ➜ 📑 ReDoc Documentation  : http://localhost:{backend_port}/redoc")
        print(f"  ➜ 🩺 System Health Check   : http://localhost:{backend_port}/api/health")
        print("-" * 70)
        print("[*] Opening BeatBatch in your browser... (Press Ctrl+C to stop)\n")
        webbrowser.open(f"http://localhost:{frontend_port}")
    else:
        print("[!] Services started, but health checks took longer than usual.")
        print(f"    Check http://localhost:{frontend_port} directly in your browser.")
        print("-" * 70)

    # Monitor subprocesses until interrupted
    try:
        while True:
            if backend_proc.poll() is not None:
                print(f"[!] Backend API process exited with code {backend_proc.returncode}")
                break
            if frontend_proc.poll() is not None:
                print(f"[!] Frontend process exited with code {frontend_proc.returncode}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        handle_exit()
    finally:
        handle_exit()


if __name__ == "__main__":
    main()
