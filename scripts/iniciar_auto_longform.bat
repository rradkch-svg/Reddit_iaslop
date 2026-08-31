@echo off
chcp 65001 >nul
title Reddit Story Studio - Gerador Automatico de Longform 25min (16:9)
echo =========================================================================
echo   REDDIT STORY STUDIO — GERACAO AUTOMATICA EM BATCHES (APENAS LONGFORM 25MIN)
echo =========================================================================
echo.
echo  Gera lotes continuos apenas de historias unicas profundas de 25 minutos
echo  divididas em 8 capitulos com gameplay HD 1080p60 e timestamps para YouTube.
echo.
cd /d "%~dp0\.."
python src/auto_pipeline.py --mode longform %*
echo.
echo =========================================================================
echo   LOTE LONGFORM CONCLUIDO! Verifique em checkpoint\auto_batches\
echo =========================================================================
pause
