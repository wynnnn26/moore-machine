@echo off
REM ============================================================
REM  Build the simulator into a single Windows .exe.
REM
REM  Clicking this installs whatever the build needs first:
REM      requirements.txt  ->  the app's own dependencies
REM      pyinstaller       ->  the packer itself
REM  Result:  dist\Moore Machine Simulator.exe
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

echo Installing requirements...
python -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :failed
python -m pip install --quiet pyinstaller
if errorlevel 1 goto :failed

echo Building Moore Machine Simulator...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "Moore Machine Simulator" main.py
if errorlevel 1 goto :failed

echo.
echo Build OK:  %~dp0dist\Moore Machine Simulator.exe
pause
exit /b 0

:failed
echo.
echo *** BUILD FAILED - see the errors above ***
pause
exit /b 1
