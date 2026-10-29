@echo off
rem Arma los archivos para publicar un release en GitHub, en la carpeta release.
rem Antes: construir.bat (el .exe) y extras\nxmods\construir_nro.bat (el .nro).
rem Uso: preparar_release.bat  [ruta a Skyrim.esm]  [carpeta de herramientas]
rem Ejemplo: preparar_release.bat "C:\SkyNX\Vanilla\BSAs\Skyrim.esm" "C:\SkyNX\Tools"
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Primero corre construir.bat una vez.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
set ARGS=
if not "%~1"=="" set ARGS=%ARGS% --skyrim-esm "%~1"
if not "%~2"=="" set ARGS=%ARGS% --tools "%~2"
python extras\release\make_release.py %ARGS% || goto :error
echo.
echo Listo: los zip estan en %~dp0release
pause
exit /b 0
:error
echo Algo fallo. Revisa el mensaje de arriba.
pause
exit /b 1
