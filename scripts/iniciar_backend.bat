@echo off
setlocal enabledelayedexpansion
title AI Slop Studio - Backend WebUI

echo ========================================================
echo   AI Slop Studio - Inicializando Backend WebUI (9:16)
echo ========================================================
echo.

REM Garante que o diretorio de trabalho e a raiz do projeto
cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM 1. Verificacao do arquivo .env
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul 2>&1
        echo [*] Arquivo .env inicializado automaticamente a partir de .env.example.
        echo.
    )
)

REM 2. Deteccao do interpretador Python correto (Python 3.11+ prioritario)
echo [*] Verificando ambiente Python...
set "PY_CMD="

py -3.11 -c "import streamlit" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.11"
    goto found_python
)

py -c "import streamlit" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto found_python
)

python -c "import streamlit" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto found_python
)

py -3.9 -c "import streamlit" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.9"
    goto found_python
)

if exist "C:\ProgramData\Anaconda3\python.exe" (
    "C:\ProgramData\Anaconda3\python.exe" -c "import streamlit" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=C:\ProgramData\Anaconda3\python.exe"
        goto found_python
    )
)

:found_python
if "%PY_CMD%"=="" (
    echo [ERRO] Nao foi possivel encontrar uma instalacao do Python com Streamlit.
    echo Por favor, instale as dependencias executando:
    echo   py -3.11 -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python detectado: %PY_CMD%
echo [*] Iniciando Streamlit WebUI na porta 8501...
echo.

REM 3. Execucao do Streamlit apontando para src/app.py
%PY_CMD% -m streamlit run src\app.py --server.port 8501 --browser.gatherUsageStats false --server.fileWatcherType none

if !errorlevel! neq 0 (
    echo.
    echo [ERRO] O servidor encerrou com codigo de erro: !errorlevel!
    pause
)
