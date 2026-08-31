@echo off
setlocal enabledelayedexpansion
title Reddit Story Studio - Geracao Automatica em Batches (video_0 Dual + video_1..9 Shorts)

echo =======================================================================
echo   REDDIT STORY STUDIO — GERACAO AUTONOMA EM BATCHES (10 SLOTS/LOTE)
echo   Regra: video_0 = Dual (25min Longform + Teaser) ^| video_1..9 = Shorts
echo   Sistema de Checkpoints Resiliente a Quedas e Interrupcoes
echo =======================================================================
echo.

cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul 2>&1
        echo [*] Arquivo .env inicializado automaticamente a partir de .env.example.
        echo.
    )
)

echo [*] Detectando ambiente Python 3.11+...
set "PY_CMD="

py -3.11 -c "import google.genai, edge_tts, yt_dlp, PIL" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.11"
    goto found_python
)

py -c "import google.genai, edge_tts, yt_dlp, PIL" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto found_python
)

python -c "import google.genai, edge_tts, yt_dlp, PIL" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto found_python
)

:found_python
if "%PY_CMD%"=="" (
    echo [ERRO] Interpretador Python com as dependencias necessarias nao foi encontrado.
    echo Por favor, instale as dependencias executando:
    echo   py -3.11 -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python detectado: %PY_CMD%
echo [*] Iniciando processamento automatico do lote...
echo.

%PY_CMD% src\auto_pipeline.py %*

if !errorlevel! neq 0 (
    echo.
    echo [AVISO] O processo encerrou com codigo: !errorlevel!
    echo Verifique os logs detalhados em .\logs\latest.log
    pause
)
