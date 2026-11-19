@echo off
rem PkoStat: start the local admin website (http://127.0.0.1:8765) and open the browser.
rem Close this window or press Ctrl+C to stop it. Extra arguments go to pkostat, e.g. "run.bat report --user jane".
cd /d "%~dp0"
uv run pkostat %*
if errorlevel 1 pause
