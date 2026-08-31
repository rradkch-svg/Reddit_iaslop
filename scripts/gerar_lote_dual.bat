@echo off
chcp 65001 >nul
title Reddit Story Studio - Gerador de Lotes Dual (Longform 25min + Teaser Short)
echo =========================================================================
echo   REDDIT STORY STUDIO — LOTE DUAL (25MIN MASTER 16:9 + TEASER SHORT 9:16)
echo =========================================================================
echo.
echo  Produz lotes completos organizados em batch_1, batch_2... (video_0 a video_9).
echo  Cada slot contem:
echo   - longform_25min/ (Master 25min 16:9 + 8 chunks + narration + timestamps)
echo   - teaser_short/ (Short 9:16 com Gancho Final "👉 FULL 25-MIN SAGA ON CHANNEL")
echo.
cd /d "%~dp0\.."
python src/auto_pipeline.py --mode dual %*
echo.
echo =========================================================================
echo   LOTE CONCLUIDO! Verifique em checkpoint\auto_batches\
echo =========================================================================
pause
