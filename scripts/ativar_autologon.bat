@echo off
chcp 65001 >nul 2>&1
title AI Slop Studio - Ativar AutoLogon
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0configurar_autologon.ps1" -Action enable
pause
