@echo off
REM Sync Python dependencies with uv (virtual environment managed by uv)
REM Usage:
REM   sync.bat            → core + edge-tts (lightweight, recommended)
REM   sync.bat full       → everything (including XTTS-v2 voice cloning)
REM   sync.bat bare       → core API only
REM   sync.bat edge       → core + edge-tts
REM   sync.bat xtts       → core + XTTS-v2 voice cloning (needs Python 3.12)
REM   sync.bat dev        → full + test tools

REM Ensure uv is in PATH
set PATH=C:\Users\san33\.local\bin;%PATH%

REM Set proxy (remove if not needed)
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

if "%1"=="" (
    echo === Installing: core + edge-tts (lightweight) ===
    uv sync --extra tts-edge
) else if "%1"=="bare" (
    echo === Installing: core API only ===
    uv sync
) else if "%1"=="edge" (
    echo === Installing: core + edge-tts ===
    uv sync --extra tts-edge
) else if "%1"=="f5" (
    echo === Installing: core + F5-TTS voice cloning ===
    uv sync --extra tts-f5
) else if "%1"=="full" (
    echo === Installing: full (everything) ===
    uv sync --extra full
) else if "%1"=="dev" (
    echo === Installing: full + dev tools ===
    uv sync --extra full --dev
) else (
    echo Unknown option: %1
    echo.
    echo Usage: sync.bat [bare^|edge^|xtts^|full^|dev]
    echo   bare  - core API only (fastapi, uvicorn, openai, pyyaml^)
    echo   edge  - core + Microsoft edge-tts cloud TTS (default^)
    echo   xtts  - core + XTTS-v2 local voice cloning
    echo   full  - everything
    echo   dev   - full + pytest
)
