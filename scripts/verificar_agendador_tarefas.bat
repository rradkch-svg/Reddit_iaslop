@echo off
title AI Slop Studio - Status do Agendador de Tarefas e Watchdog
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0setup_task.ps1" -Action status
echo.
pause
