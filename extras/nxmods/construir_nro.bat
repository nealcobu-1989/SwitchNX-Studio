@echo off
rem Construye SkyNXMods.nro (el homebrew para activar y desactivar mods en la Switch).
rem Necesita devkitPro instalado en C:\devkitPro con "Switch Development".
setlocal
cd /d "%~dp0"
set BASH=C:\devkitPro\msys2\usr\bin\bash.exe
if not exist "%BASH%" (
  echo No encontre devkitPro en C:\devkitPro. Instalalo desde
  echo https://github.com/devkitPro/installer/releases y marca "Switch Development".
  pause
  exit /b 1
)
echo Instalando las librerias de SDL2 para Switch (solo la primera vez tarda)...
"%BASH%" -lc "pacman -S --needed --noconfirm switch-dev switch-sdl2 switch-sdl2_ttf switch-sdl2_image" || goto :error
echo Compilando...
rem CHERE_INVOKING deja a bash en esta carpeta
set CHERE_INVOKING=1
"%BASH%" -lc "make -f Makefile.switch" || goto :error
if not exist SkyNXMods.nro goto :error
echo.
echo Listo: %~dp0SkyNXMods.nro
echo Copialo a la carpeta switch de la SD y abrelo desde el menu de homebrew.
pause
exit /b 0

:error
echo.
echo Algo fallo. Revisa el mensaje de arriba (o abre un issue en GitHub con ese texto).
pause
exit /b 1
