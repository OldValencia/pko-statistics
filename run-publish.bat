@echo off
rem PkoStat: fetch new pushes and republish the encrypted reports (only if something changed).
rem For Task Scheduler every 2 hours; no LLM, no backup. Output goes to <data folder>\logs\publish.log.
cd /d "%~dp0"
if not exist "%USERPROFILE%\pkostatistics\logs" mkdir "%USERPROFILE%\pkostatistics\logs"
set LOG="%USERPROFILE%\pkostatistics\logs\publish.log"
echo ==== %DATE% %TIME% ==== >> %LOG%
uv run pkostat sync >> %LOG% 2>&1
uv run pkostat rebuild >> %LOG% 2>&1
uv run pkostat publish >> %LOG% 2>&1
