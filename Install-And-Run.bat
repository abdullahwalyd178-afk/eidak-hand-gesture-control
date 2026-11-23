@echo off
REM ============================================================
REM  Eidak - Hand Gesture PC Control
REM  One-click installer + launcher for Windows.
REM  Double-click this file. First run installs everything,
REM  later runs start the app directly.
REM ============================================================
cd /d "%~dp0"
title Eidak - Hand Gesture PC Control

REM The virtual environment normally lives next to the app. When the
REM app folder path has non-English letters, Python venv/pip can fail,
REM so then we fall back to a path-safe location (item 18).
set VENV=.venv

REM ---- 1. Setup is skipped only if a previous install FINISHED --
if exist ".venv\Scripts\python.exe" if exist ".venv\.installed" goto :run
if exist "%LOCALAPPDATA%\Eidak\venv\Scripts\python.exe" if exist "%LOCALAPPDATA%\Eidak\venv\.installed" (
    set VENV=%LOCALAPPDATA%\Eidak\venv
    goto :run
)

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
    REM A very common case: the PC has ONLY Python 3.13+, which
    REM mediapipe does not support yet (item 20).
    python -c "import sys; sys.exit(0 if sys.version_info[0]==3 and sys.version_info[1]>=13 else 1)" >nul 2>nul
    if not errorlevel 1 (
        echo Your PC only has Python 3.13 or newer - mediapipe does not
        echo support it yet. Install Python 3.11 ^(64-bit^) alongside it:
    ) else (
        echo Download Python 3.11 from https://www.python.org/downloads/
    )
    echo https://www.python.org/downloads/release/python-3119/
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
    echo.
    echo [Eidak] Could not create the environment in this folder.
    echo This usually happens when the folder path has non-English letters.
    echo Trying a path-safe location instead: %LOCALAPPDATA%\Eidak\venv
    if exist "%LOCALAPPDATA%\Eidak\venv" rmdir /s /q "%LOCALAPPDATA%\Eidak\venv"
    %PY% -m venv "%LOCALAPPDATA%\Eidak\venv"
    if errorlevel 1 (
        echo [Eidak] Could not create the virtual environment at all.
        pause
        exit /b 1
    )
    set VENV=%LOCALAPPDATA%\Eidak\venv
)
call "%VENV%\Scripts\activate.bat"
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
REM Post-install sanity check: packages downloaded but can they LOAD? (item 17)
python -c "import cv2, mediapipe, pyautogui" 2>nul
if errorlevel 1 (
    echo.
    echo [Eidak] Packages installed but failed to load.
    echo This is usually the missing Microsoft Visual C++ Redistributable.
    echo Download and install vc_redist.x64.exe from:
    echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo then run this file again.
    echo.
    pause
    exit /b 1
)
REM Marker: written only after a fully successful install.
echo ok> "%VENV%\.installed"

:run
call "%VENV%\Scripts\activate.bat"
echo.
echo [Eidak] Starting... show your hand to the camera.
echo [Eidak] If the camera does not open, run:  python hand_gesture_control.py --diagnose
echo.
python hand_gesture_control.py %*
if errorlevel 1 pause
