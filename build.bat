@echo off
REM ============================================================
REM  Build moore.py into a single Windows .exe.
REM
REM  One-time setup:   pip install pyinstaller
REM  Result:            dist\Moore Machine Simulator.exe
REM
REM  --windowed : no console window (it's a GUI app)
REM  --onefile  : everything packed into one .exe
REM ============================================================
cd /d "%~dp0"

REM A running .exe cannot be overwritten. Say so plainly instead of failing
REM with a wall of PyInstaller traceback halfway through the build.
if exist "dist\Moore Machine Simulator.exe" del /f "dist\Moore Machine Simulator.exe"
if exist "dist\Moore Machine Simulator.exe" (
    echo.
    echo *** The old .exe is still running.  Close the Moore Machine Simulator window, then run this again ***
    exit /b 1
)

echo Building Moore Machine Simulator...
pyinstaller --noconfirm --clean --onefile --windowed --name "Moore Machine Simulator" moore.py

if errorlevel 1 (
    echo.
    echo *** BUILD FAILED - see the errors above ***
    exit /b 1
)

echo.
echo Build OK:  %~dp0dist\Moore Machine Simulator.exe
pause
