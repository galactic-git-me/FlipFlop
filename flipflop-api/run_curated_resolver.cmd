@echo off
cd /d "%~dp0"
if not exist output\curated_offers mkdir output\curated_offers
".venv\Scripts\python.exe" scripts\resolve_curated_offers.py %* > output\curated_offers\last_run.log 2>&1
echo EXIT CODE %ERRORLEVEL% >> output\curated_offers\last_run.log
