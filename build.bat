@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm PrismaFunction.spec
if errorlevel 1 exit /b %errorlevel%

echo Build complete: dist\PrismaFunction\PrismaFunction.exe
