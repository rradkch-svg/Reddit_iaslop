@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0setup_task.ps1" -Action unregister
pause
