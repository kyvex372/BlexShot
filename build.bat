@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" tools\make_icon.py
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean BlexShot.spec
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" tools\verify_package.py
if errorlevel 1 goto :fail
echo.
echo Hazir: %CD%\dist\BlexShot.exe
exit /b 0
:fail
echo.
echo Islem basarisiz. Yukaridaki hata mesajini kontrol edin.
exit /b 1
