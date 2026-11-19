@echo off
rem PkoStat daily run for Windows Task Scheduler: sync, rebuild, LLM, reports, backup.
rem Output goes to <data folder>\logs\run.log. See docs/ai/roadmap.md, stage 8, for scheduling.
cd /d "%~dp0"
if not exist "%USERPROFILE%\pkostatistics\logs" mkdir "%USERPROFILE%\pkostatistics\logs"
echo ==== %DATE% %TIME% ==== >> "%USERPROFILE%\pkostatistics\logs\run.log"
uv run pkostat run >> "%USERPROFILE%\pkostatistics\logs\run.log" 2>&1
