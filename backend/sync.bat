@echo off
REM Sync Python dependencies with uv
REM Usage:
REM   sync.bat            → core + edge-tts (lightweight, recommended)
REM   sync.bat full       → everything (including XTTS-v2 voice cloning)
REM   sync.bat edge       → core + edge-tts only
REM   sync.bat xtts       → core + XTTS-v2 voice cloning
REM   sync.bat dev        → core + everything + test tools

if "%1"=="" (
    echo Installing: core + edge-tts ^(lightweight^)
    uv sync --extra tts-edge
) else if "%1"=="full" (
    echo Installing: full ^(everything^)
    uv sync --extra full
) else if "%1"=="edge" (
    echo Installing: core + edge-tts only
    uv sync --extra tts-edge
) else if "%1"=="xtts" (
    echo Installing: core + XTTS-v2 voice cloning
    uv sync --extra tts-xtts
) else if "%1"=="dev" (
    echo Installing: full + dev tools
    uv sync --extra full --dev
) else if "%1"=="bare" (
    echo Installing: core only ^(no TTS^)
    uv sync
) else (
    echo Unknown option: %1
    echo Usage: sync.bat [bare^|edge^|xtts^|full^|dev]
    echo   bare  - core API only
    echo   edge  - core + Microsoft edge-tts ^(default^)
    echo   xtts  - core + XTTS-v2 voice cloning
    echo   full  - everything
    echo   dev   - full + test tools
)
