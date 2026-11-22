@echo off
REM ============================================================
REM  Eidak - Hand Gesture PC Control
REM  One-click installer + launcher for Windows.
REM  Double-click this file. First run installs everything,
REM  later runs start the app directly.
REM ============================================================
cd /d "%~dp0"
title Eidak - Hand Gesture PC Control

REM ---- 1. Setup is skipped only if a previous install FINISHED --
if exist ".venv\Scripts\python.exe" if exist ".venv\.installed" goto :run

REM ---- 2. Find a supported Python (3.9 - 3.12) -----------------
set PY=
REM Prefer the py launcher: it can pick a specific version even when
REM a newer, unsupported Python (3.13+) is also installed.
where py >nul 2>nul
if not errorlevel 1 (
    for %%V in (3.12 3.11 3.10 3.9) do (
        if not defined PY (
            py -%%V -c "import sys" >nul 2>nul && set PY=py -%%V
        )
    )
)
REM Fall back to "python", but make sure it really runs and is supported
REM (the Microsoft Store stub passes "where" but cannot run anything).
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info[0]==3 and 9<=sys.version_info[1]<=12 else 1)" >nul 2>nul && set PY=python
)
if not defined PY (
    echo.
    echo [Eidak] No supported Python found ^(need 3.9 - 3.12^).
    echo Download Python 3.11 from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" during installation,
    echo then run this file again.
    echo ^(If Python is installed but this message appears, turn off the
    echo  "python.exe" App Execution Alias in Windows Settings.^)
    echo.
    pause
    exit /b 1
)

REM ---- 3. (Re)create the virtual environment -------------------
if exist ".venv" (
    echo [Eidak] Previous setup was incomplete - rebuilding the environment...
    rmdir /s /q ".venv"
)
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
REM Marker: written only after a fully successful install.
echo ok> ".venv\.installed"

:run
call ".venv\Scripts\activate.bat"
echo.
echo [Eidak] Starting... show your hand to the camera.
echo [Eidak] If the camera does not open, run:  python hand_gesture_control.py --diagnose
echo.
python hand_gesture_control.py %*
if errorlevel 1 pause
