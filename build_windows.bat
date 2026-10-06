@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.11 or newer is required.
  exit /b 1
)

py -3 -m venv .venv-build
if errorlevel 1 exit /b 1
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[build,documents]"
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean "AI_Novel_Factory.spec"
if errorlevel 1 exit /b 1

echo.
echo Build complete: dist\AI Novel Factory.exe
endlocal
