@echo off
echo ========================================
echo  IdleNote -- Build EXE
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause & exit /b 1
)

echo [1/3] Installing dependencies...
pip install pynput pystray pillow pyinstaller --quiet
if errorlevel 1 ( echo [ERROR] pip failed & pause & exit /b 1 )

echo [2/3] Building EXE...
pyinstaller --onefile --noconsole --name IdleNote ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pynput.mouse._win32 ^
    --hidden-import pystray._win32 ^
    idlenote.py
if errorlevel 1 ( echo [ERROR] PyInstaller failed & pause & exit /b 1 )

echo [3/3] Done!
echo.
echo Your EXE is at: dist\IdleNote.exe
echo Just double-click it to run. No Python needed.
echo.
pause
