@echo off
setlocal

cd /d "%~dp0"
set "PYTHON_EXE="
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    set "PYTHON_EXE=%VENV_PYTHON%"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv ".venv"
        if exist "%VENV_PYTHON%" set "PYTHON_EXE=%VENV_PYTHON%"
    )
)

if not defined PYTHON_EXE (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python -m venv ".venv"
        if exist "%VENV_PYTHON%" set "PYTHON_EXE=%VENV_PYTHON%"
    )
)

if not defined PYTHON_EXE (
    echo Python not found. Install Python 3.11+.
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%\src"

"%PYTHON_EXE%" -c "import PySide6, fitz" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

"%PYTHON_EXE%" -m pdfbread

:end
if errorlevel 1 (
    echo.
    echo PDFBread exited with an error.
    pause
)
endlocal
