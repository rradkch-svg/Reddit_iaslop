@echo off
title AI Slop Studio - Registrar Agendador de Tarefas
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0setup_task.ps1" -Action register
echo.
pause
