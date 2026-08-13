@echo off
cd /d "%~dp0"
.\.venv\Scripts\python.exe run_dev.py --host 0.0.0.0 --port 4311
