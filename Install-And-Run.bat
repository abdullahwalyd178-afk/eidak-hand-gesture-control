@echo off
REM ============================================================
REM  Eidak - Hand Gesture PC Control
REM  One-click installer + launcher for Windows.
REM  Double-click this file. First run installs everything,
REM  later runs start the app directly.
REM ============================================================
cd /d "%~dp0"
title Eidak - Hand Gesture PC Control

REM ---- 1. Find Python ----------------------------------------
set PY=
where python >nul 2>nul && set PY=python
if not defined PY (
    where py >nul 2>nul && set PY=py -3
)
if not defined PY (
    echo.
    echo [Eidak] Python is not installed.
    echo Download Python 3.11 from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" during installation,
    echo then run this file again.
    echo.
    pause
    exit /b 1
)

REM ---- 2. Check the version (need 3.9 - 3.12 for MediaPipe) --
%PY% -c "import sys; ok=(9<=sys.version_info.minor<=12) and sys.version_info.major==3; sys.exit(0 if ok else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo [Eidak] Your Python version is not supported by MediaPipe.
    echo Please install Python 3.11 or 3.12 from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM ---- 3. Create the virtual environment once ----------------
if not exist ".venv\Scripts\python.exe" (
    echo [Eidak] First run: preparing the environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [Eidak] Could not create the virtual environment.
        pause
        exit /b 1
    )
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [Eidak] Package installation failed. Check your internet
        echo connection and run this file again.
        echo.
        pause
        exit /b 1
    )
) else (
    call ".venv\Scripts\activate.bat"
)

REM ---- 4. Run -------------------------------------------------
echo.
echo [Eidak] Starting... show your hand to the camera.
echo [Eidak] If the camera does not open, run:  python hand_gesture_control.py --diagnose
echo.
python hand_gesture_control.py %*
if errorlevel 1 pause
