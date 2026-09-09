@echo off
rem Process-local script permission; no machine execution policy is changed.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Dashboard.ps1" -NoPause %*
set "dashboard_exit_code=%errorlevel%"
if not "%dashboard_exit_code%"=="0" pause
exit /b %dashboard_exit_code%
