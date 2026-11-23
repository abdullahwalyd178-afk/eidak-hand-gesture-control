@echo off
REM ============================================================
REM  Eidak - Hand Gesture PC Control
REM  One-click installer + launcher for Windows.
REM  Double-click this file. First run installs everything,
REM  later runs start the app directly.
REM ============================================================
cd /d "%\~dp0"
title Eidak - Hand Gesture PC Control

REM The virtual environment normally lives next to the app. When the
REM app folder path has non-English letters, Python venv/pip can fail,
REM so then we fall back to a path-safe location (item 18).
set VENV=.venv

REM ---- 1. Setup is skipped only if a previous install FINISHED --
if exist ".venv\Scripts\python.exe" if exist ".venv\\.installed" goto :run
if exist "%LOCALAPPDATA%\Eidak\venv\Scripts\python.exe" if exist "%LOCALAPPDATA%\Eidak\venv\\.installed" (
&#x20;   set VENV=%LOCALAPPDATA%\Eidak\venv
&#x20;   goto :run
)

REM ---- 2. Find a supported Python (3.9 - 3.12) -----------------
set PY=
REM Prefer the py launcher: it can pick a specific version even when
REM a newer, unsupported Python (3.13+) is also installed.
where py >nul 2>nul
if not errorlevel 1 (
&#x20;   for %%V in (3.12 3.11 3.10 3.9) do (
&#x20;       if not defined PY (
&#x20;           py -%%V -c "import sys" >nul 2>nul && set PY=py -%%V
&#x20;       )
&#x20;   )
)
REM Fall back to "python", but make sure it really runs and is supported
REM (the Microsoft Store stub passes "where" but cannot run anything).
if not defined PY (
&#x20;   python -c "import sys; sys.exit(0 if sys.version_info[0]==3 and 9<=sys.version_info[1]<=12 else 1)" >nul 2>nul && set PY=python
)
if not defined PY (
&#x20;   echo.
&#x20;   echo [Eidak] No supported Python found ^(need 3.9 - 3.12^).
&#x20;   REM A very common case: the PC has ONLY Python 3.13+, which
&#x20;   REM mediapipe does not support yet (item 20).
&#x20;   python -c "import sys; sys.exit(0 if sys.version_info[0]==3 and sys.version_info[1]>=13 else 1)" >nul 2>nul
&#x20;   if not errorlevel 1 (
&#x20;       echo Your PC only has Python 3.13 or newer - mediapipe does not
&#x20;       echo support it yet. Install Python 3.11 ^(64-bit^) alongside it:
&#x20;   ) else (
&#x20;       echo Download Python 3.11 from [https://www.python.org/downloads/](https://www.python.org/downloads/)
&#x20;   )
&#x20;   echo [https://www.python.org/downloads/release/python-3119/](https://www.python.org/downloads/release/python-3119/)
&#x20;   echo IMPORTANT: tick "Add python.exe to PATH" during installation,
&#x20;   echo then run this file again.
&#x20;   echo ^(If Python is installed but this message appears, turn off the
&#x20;   echo  "python.exe" App Execution Alias in Windows Settings.^)
&#x20;   echo.
&#x20;   pause
&#x20;   exit /b 1
)

REM ---- 3. (Re)create the virtual environment -------------------
if exist ".venv" (
&#x20;   echo [Eidak] Previous setup was incomplete - rebuilding the environment...
&#x20;   rmdir /s /q ".venv"
)
echo [Eidak] First run: preparing the environment...
%PY% -m venv .venv
if errorlevel 1 (
&#x20;   echo.
&#x20;   echo [Eidak] Could not create the environment in this folder.
&#x20;   echo This usually happens when the folder path has non-English letters.
&#x20;   echo Trying a path-safe location instead: %LOCALAPPDATA%\Eidak\venv
&#x20;   if exist "%LOCALAPPDATA%\Eidak\venv" rmdir /s /q "%LOCALAPPDATA%\Eidak\venv"
&#x20;   %PY% -m venv "%LOCALAPPDATA%\Eidak\venv"
&#x20;   if errorlevel 1 (
&#x20;       echo [Eidak] Could not create the virtual environment at all.
&#x20;       pause
&#x20;       exit /b 1
&#x20;   )
&#x20;   set VENV=%LOCALAPPDATA%\Eidak\venv
)
call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 (
&#x20;   echo [Eidak] pip self-upgrade failed - continuing with the bundled pip.
)
pip install -r requirements.txt
if errorlevel 1 (
&#x20;   echo.
&#x20;   echo [Eidak] Package installation failed. Check your internet
&#x20;   echo connection and run this file again.
&#x20;   echo.
&#x20;   pause
&#x20;   exit /b 1
)
REM Post-install sanity check: packages downloaded but can they LOAD? (item 17)
python -c "import cv2, mediapipe, pyautogui" 2>nul
if errorlevel 1 (
&#x20;   echo.
&#x20;   echo [Eidak] Packages installed but failed to load.
&#x20;   echo This is usually the missing Microsoft Visual C++ Redistributable.
&#x20;   echo Download and install vc_redist.x64.exe from:
&#x20;   echo   [https://aka.ms/vs/17/release/vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)
&#x20;   echo then run this file again.
&#x20;   echo.
&#x20;   pause
&#x20;   exit /b 1
)
REM Marker: written only after a fully successful install.
echo ok> "%VENV%\\.installed"

:run
call "%VENV%\Scripts\activate.bat"
echo.
echo [Eidak] Starting... show your hand to the camera.
echo [Eidak] If the camera does not open, run:  python hand_gesture_control.py --diagnose
echo.
python hand_gesture_control.py %\*
if errorlevel 1 pause
