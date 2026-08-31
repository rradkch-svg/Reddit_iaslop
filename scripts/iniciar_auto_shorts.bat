@echo off
chcp 65001 >nul
title Reddit Story Studio - Gerador Automatico de Shorts (9:16)
echo =========================================================================
echo   REDDIT STORY STUDIO — GERACAO AUTOMATICA EM BATCHES (APENAS SHORTS)
echo =========================================================================
echo.
echo  Gera lotes continuos apenas de Shorts individuais verticais (9:16)
echo  com Cards Oficiais do Reddit, narracao acelerada e pergunta de CTA.
echo.
cd /d "%~dp0\.."
python src/auto_pipeline.py --mode shorts %*
echo.
echo =========================================================================
echo   LOTE DE SHORTS CONCLUIDO! Verifique em checkpoint\auto_batches\
echo =========================================================================
pause
