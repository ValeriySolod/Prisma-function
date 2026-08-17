@echo off
cd /d "%~dp0"
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
echo.
echo Installation complete.
echo Start the program with run.bat
pause
