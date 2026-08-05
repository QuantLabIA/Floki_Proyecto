@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python no esta instalado o no esta agregado al PATH.
  echo Instala Python 3.11 o superior y marca la opcion "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno de Floki Manager...
  python -m venv .venv
  if errorlevel 1 goto :error
)

call .venv\Scripts\activate

if not exist ".venv\.floki_deps_v2_5" (
  echo Instalando dependencias por unica vez...
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  type nul > ".venv\.floki_deps_v2_5"
)

python run.py
goto :end

:error
echo.
echo No se pudo iniciar Floki Manager. Revisa el mensaje anterior.
pause
exit /b 1

:end
endlocal
