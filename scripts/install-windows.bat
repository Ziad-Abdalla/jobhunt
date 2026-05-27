@echo off
title jobhunt - installing...
echo.
echo   Installing jobhunt
echo   -------------------
echo.

:: Check if uv is already installed
where uv >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] uv is already installed.
    goto :install_jobhunt
)

:: Install uv
echo   Installing uv (package manager)...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"

set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Could not install uv. Visit https://docs.astral.sh/uv/
    pause
    exit /b 1
)
echo   [OK] uv installed.

:install_jobhunt
echo.

:: Remove old versions to avoid conflicts
uv tool uninstall jobhunt-app >nul 2>&1
uv tool uninstall jobhunt >nul 2>&1

:: Install latest from PyPI
echo   Installing latest jobhunt...
uv tool install jobhunt-app

:: Add to PATH
for /f "tokens=*" %%i in ('uv tool dir --bin 2^>nul') do set "PATH=%%i;%PATH%"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

:: Show version
jobhunt --version 2>nul
if %errorlevel% neq 0 (
    echo.
    echo   Install failed. Close this window and try again.
    pause
    exit /b 1
)

:: Create desktop shortcut
echo @echo off > "%USERPROFILE%\Desktop\jobhunt.bat"
echo title jobhunt >> "%USERPROFILE%\Desktop\jobhunt.bat"
echo jobhunt >> "%USERPROFILE%\Desktop\jobhunt.bat"
echo pause >> "%USERPROFILE%\Desktop\jobhunt.bat"
echo   [OK] Desktop shortcut created.

echo.
echo   [OK] All done!
echo.
echo   To start: double-click 'jobhunt' on your Desktop
echo   To update: run this installer again
echo.
echo   Starting jobhunt now...
echo.
jobhunt
