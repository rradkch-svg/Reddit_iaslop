@echo off
setlocal enabledelayedexpansion
title AI Slop Studio - Modo Geracao Automatica (Batches de 10 Videos)

echo =======================================================================
echo   AI SLOP STUDIO - GERACAO AUTONOMA EM BATCHES (9:16)
echo   Sistema de Checkpoints Resiliente a Quedas de Energia
echo =======================================================================
echo.

cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado na raiz do projeto.
    echo.
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
echo [*] Iniciando processamento em lote continuo (10 videos por batch)...
echo [*] Checkpoints salvos automaticamente em: .\checkpoint\
echo [*] Blacklist de temas ativada para impedir repeticoes.
echo.

%PY_CMD% src\auto_pipeline.py %*

if !errorlevel! neq 0 (
    echo.
    echo [AVISO] O processo encerrou com codigo: !errorlevel!
    echo Verifique os logs detalhados em .\logs\latest.log
    pause
)
