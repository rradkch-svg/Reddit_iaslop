@echo off
chcp 65001 >nul
title Reddit Story Studio - Gerador de Historia Unica Longa (25 Minutos)

echo =========================================================================
echo  REDDIT STORY STUDIO — HISTORIA UNICA DE 25 MINUTOS (HIGH CPM)
echo =========================================================================
echo.
cd /d "%~dp0\.."
python -m src.reddit_longform %*
echo.
pause
