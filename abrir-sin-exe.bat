@echo off
rem Abre SwitchNX Studio desde el código, sin construir el .exe (útil para probar cambios).
cd /d "%~dp0"
if not exist .venv (
  echo Primero corre construir.bat una vez.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
rem new versions may need new packages
pip install -q -r requirements.txt
python app\main.py %*
