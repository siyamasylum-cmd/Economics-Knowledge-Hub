@echo off
cd /d "%~dp0"
echo Starting BEPI Pipeline...

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: venv not found. Double-click setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if not exist "bepi_data" mkdir bepi_data

echo [1/4] Initializing database...
python -m bepi.database
if errorlevel 1 goto error

echo [2/4] Collecting articles...
python -m bepi.collector
if errorlevel 1 goto error

echo [3/4] Running AI analysis...
python -m bepi.analyzer
if errorlevel 1 goto error

echo [4/4] Computing BEPI score...
python -m bepi.index_engine
if errorlevel 1 goto error

echo.
echo Launching dashboard...
streamlit run bepi/dashboard.py
pause
exit /b 0

:error
echo.
echo Something failed. Read the message above, then press any key.
pause
exit /b 1
