@echo off
title AI Slop Studio - Configurar Windows AutoLogon
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0configurar_autologon.ps1" -Action enable
echo.
pause
