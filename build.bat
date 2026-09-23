@echo off
REM Build Countdown.exe. Run this on a Windows machine with Python 3.9+.
REM The result is dist\Countdown.exe - copy it, with countdown.txt, anywhere.

setlocal
cd /d "%~dp0"

python -m venv .venv || goto :fail
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip           || goto :fail
python -m pip install -r requirements.txt     || goto :fail
python -m pip install pyinstaller==6.11.1     || goto :fail

rmdir /s /q build dist 2>nul
pyinstaller --clean --noconfirm Countdown.spec || goto :fail

copy /y countdown.txt dist\countdown.txt >nul

echo.
echo Built: dist\Countdown.exe
echo Ship dist\Countdown.exe and dist\countdown.txt together.
goto :eof

:fail
echo.
echo BUILD FAILED
exit /b 1
