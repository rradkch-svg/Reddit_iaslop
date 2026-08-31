@echo off
setlocal enabledelayedexpansion
title AI Slop Studio - Watchdog Supervisor

echo =======================================================================
echo   AI SLOP STUDIO - WATCHDOG SUPERVISOR
echo =======================================================================
echo.

cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

set "PY_CMD="
py -3.11 -c "import os" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.11"
    goto found_py
)

py -c "import os" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto found_py
)

python -c "import os" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto found_py
)

:found_py
if "%PY_CMD%"=="" (
    set "PY_CMD=python"
)

%PY_CMD% src\watchdog.py %*

if !errorlevel! neq 0 (
    echo.
    echo [AVISO] Watchdog encerrou com codigo: !errorlevel!
    pause
)
