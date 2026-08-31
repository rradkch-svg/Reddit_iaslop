@echo off
chcp 65001 >nul
title Reddit Story Channel Video Studio (High CPM Edition)
echo ========================================================
echo   REDDIT STORY CHANNEL VIDEO STUDIO - HIGH CPM EDITION
echo ========================================================
echo.
cd /d "%~dp0\.."
python -m src.reddit_pipeline %*
echo.
echo Processo concluído! Verifique os vídeos gerados em checkpoint\auto_batches\ (batch_1, batch_2...)
pause
