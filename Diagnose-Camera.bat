@echo off
REM Camera diagnostics: checks every camera and every driver path,
REM then prints which ones actually deliver video.
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python hand_gesture_control.py --diagnose
pause
