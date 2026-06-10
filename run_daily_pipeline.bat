@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
call venv\Scripts\activate.bat
python -m bepi.pipeline >> logs\daily_pipeline.log 2>&1
endlocal
