@echo off
setlocal
set "APP_NAME=Suite Rodriguez Finura"
set "INSTALL_DIR=%LOCALAPPDATA%\Suite Rodriguez Finura"
set "TEMP_ROOT=%TEMP%\Suite_Rodriguez_Finura_FullInstall"
set "ZIP_FILE=%TEMP_ROOT%\Suite_Rodriguez_Finura_v1.7.4_full.zip"
set "EXPECTED_SHA=8FA9E64ED2F00441D62FC8A8D8F5F33665BFE2A8AEF305EE7FE5F97BC8CD75E8"
set "DOWNLOAD_URL=https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/Suite_Rodriguez_Finura_v1.7.4_full.zip"

echo Instalando %APP_NAME% 1.7.4
echo Cerrando procesos abiertos de la suite...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$install=$env:INSTALL_DIR.ToLower(); Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($install) -and ($_.Name -match 'python|pythonw|Suite') } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"

if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%"
echo Descargando paquete completo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%ZIP_FILE%' -UseBasicParsing"
if errorlevel 1 goto error

echo Verificando descarga...
for /f "usebackq tokens=*" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash '%ZIP_FILE%' -Algorithm SHA256).Hash"`) do set "ACTUAL_SHA=%%H"
if /I not "%ACTUAL_SHA%"=="%EXPECTED_SHA%" (
  echo Hash incorrecto.
  echo Esperado: %EXPECTED_SHA%
  echo Obtenido: %ACTUAL_SHA%
  goto error
)

echo Preparando instalacion limpia...
if exist "%TEMP_ROOT%\extract" rmdir /s /q "%TEMP_ROOT%\extract"
mkdir "%TEMP_ROOT%\extract"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP_FILE%' -DestinationPath '%TEMP_ROOT%\extract' -Force"
if errorlevel 1 goto error

if exist "%INSTALL_DIR%.bak" rmdir /s /q "%INSTALL_DIR%.bak"
if exist "%INSTALL_DIR%" ren "%INSTALL_DIR%" "Suite Rodriguez Finura.bak"
mkdir "%LOCALAPPDATA%\Suite Rodriguez Finura"
robocopy "%TEMP_ROOT%\extract\Suite Rodriguez Finura" "%INSTALL_DIR%" /E /NFL /NDL /NJH /NJS /NP
if %ERRORLEVEL% GEQ 8 goto error

echo Abriendo suite actualizada...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $shortcut=$ws.CreateShortcut((Join-Path $desktop 'Suite Rodriguez Finura.lnk')); $shortcut.TargetPath=(Join-Path $env:INSTALL_DIR 'Abrir_Suite_Rodriguez_Finura.vbs'); $shortcut.WorkingDirectory=$env:INSTALL_DIR; $shortcut.IconLocation=(Join-Path $env:INSTALL_DIR 'ICONO_SUITE.ico'); $shortcut.Save()"
start "" "%INSTALL_DIR%\runtime\pythonw.exe" "%INSTALL_DIR%\SuiteLauncher.py"
echo Instalacion completada.
pause
exit /b 0

:error
echo.
echo No se pudo completar la instalacion.
echo Si existia una copia anterior, revisa: %INSTALL_DIR%.bak
pause
exit /b 1
