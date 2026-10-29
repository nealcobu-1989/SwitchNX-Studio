@echo off
rem Construye "SwitchNX Studio.exe" en la carpeta dist. Solo hace falta correrlo una vez
rem (o cada vez que llegue una versión nueva del código).
setlocal
cd /d "%~dp0"

set PY=
py -3.12 --version >nul 2>nul && set PY=py -3.12
if "%PY%"=="" py -3 --version >nul 2>nul && set PY=py -3
if "%PY%"=="" python --version >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo No encontre Python. Instala Python 3.12 desde https://www.python.org/downloads/
  echo y marca "Add python.exe to PATH" durante la instalacion.
  pause
  exit /b 1
)
echo Usando: %PY%
%PY% --version

if not exist .venv (
  echo Creando entorno...
  %PY% -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || goto :error

echo Probando que el motor arranque...
python -c "import sys; sys.path.insert(0,'.'); import skynx.audit, skynx.bsa, skynx.fixes, skynx.converter, skynx.nvn, skynx.diet, skynx.precheck, skynx.loot, skynx.nexus, numpy, yaml, lz4.frame, py7zr, texture2ddecoder; print('motor ok')" || goto :error

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "SwitchNX Studio" --icon app\icon.ico ^
  --add-data "app\web;web" --paths . --paths app ^
  --hidden-import lz4.frame --hidden-import py7zr --hidden-import texture2ddecoder --hidden-import yaml --hidden-import numpy --hidden-import ipc --hidden-import api --hidden-import server ^
  --collect-submodules skynx ^
  app\main.py || goto :error

echo.
echo Listo: dist\SwitchNX Studio.exe
echo Puedes copiar ese .exe a donde quieras; no necesita nada mas.
pause
exit /b 0

:error
echo.
echo Algo fallo. Revisa el mensaje de arriba (o abre un issue en GitHub con ese texto).
pause
exit /b 1
