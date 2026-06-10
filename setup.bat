@echo off
cd /d "%~dp0"
echo =============================================
echo   Economics Knowledge Hub - Windows Setup
echo =============================================

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from python.org
    pause
    exit /b 1
)

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Done.
)

call venv\Scripts\activate.bat

echo Installing packages from requirements.txt...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if not exist "bepi_data" mkdir bepi_data

if not exist ".env" (
    copy .env.example .env >nul
    echo Created .env from .env.example. Add your Groq key before running analysis.
)

echo.
echo =============================================
echo   Setup complete! Venv is active.
echo   First run: python -m bepi.database
echo   Daily run: run_bepi.bat
echo =============================================
cmd /k
