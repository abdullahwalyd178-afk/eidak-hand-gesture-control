@echo off
REM Camera diagnostics: checks every camera and every driver path,
REM then prints which ones actually deliver video.
REM The report is saved to camera-report.txt next to this file;
REM attach it when asking for help (item 19).
cd /d "%~dp0"

REM Diagnosing without the installed environment tells the user
REM nothing - refuse early and point at the installer (item 19).
if not exist ".venv\Scripts\python.exe" (
    if not exist "%LOCALAPPDATA%\Eidak\venv\Scripts\python.exe" (
        echo [Eidak] The environment is not installed yet.
        echo Run Install-And-Run.bat first, then run this file again.
        echo.
        pause
        exit /b 1
    )
    call "%LOCALAPPDATA%\Eidak\venv\Scripts\activate.bat"
) else (
    call ".venv\Scripts\activate.bat"
)

python hand_gesture_control.py --diagnose
pause
