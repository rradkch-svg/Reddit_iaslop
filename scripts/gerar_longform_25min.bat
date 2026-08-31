@echo off
chcp 65001 >nul
title Reddit Story Studio - Gerador de Historia Unica Longa (25 Minutos)

echo =========================================================================
echo  REDDIT STORY STUDIO — HISTORIA UNICA DE 25 MINUTOS (HIGH CPM SAGA)
echo =========================================================================
echo.
echo  [1] Selecionando historia real de alto impacto (r/maliciouscompliance, etc.)
echo  [2] Expandindo em narrativa profunda de 8 capitulos da MESMA historia
echo  [3] Sintetizando narracao neural continua (~25 minutos)
echo  [4] Renderizando com Gameplay 1080p60fps HD e Cards Oficiais do Reddit
echo  [5] Queimando legendas dinamicas estilo Hormozi palavra por palavra
echo.
echo  Iniciando processamento autonomo...
echo.

cd /d "%~dp0\.."
python -m src.reddit_longform %*

echo.
echo =========================================================================
echo  PRODUCAO CONCLUIDA! Verifique os arquivos em checkpoint/auto_batches/ (batch_1, batch_2...)
echo =========================================================================
pause
