@echo off
title jobhunt - installing...
echo.
echo   jobhunt installer
echo   -----------------
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

:: Add uv to PATH for this session
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Could not install uv automatically.
    echo   Please install it from: https://docs.astral.sh/uv/
    echo.
    pause
    exit /b 1
)
echo   [OK] uv installed.

:install_jobhunt
echo.

:: Check if jobhunt is already installed
where jobhunt >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] jobhunt is already installed. Updating...
    uv tool install --reinstall --upgrade jobhunt-app
    goto :launch
)

echo   Installing jobhunt...
echo.
uv tool install jobhunt-app
if %errorlevel% neq 0 (
    echo.
    echo   PyPI install failed. Trying from GitHub...
    uv tool install "git+https://github.com/Abdalla2004-collab/Jobhunt.git"
)

:: Add tool bin to PATH
for /f "tokens=*" %%i in ('uv tool dir --bin 2^>nul') do set "PATH=%%i;%PATH%"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

:launch
where jobhunt >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   jobhunt was installed but is not in your PATH yet.
    echo   Close this window, open a new terminal, and type: jobhunt
    echo.
    pause
    exit /b 0
)

echo.
echo   [OK] jobhunt installed.
echo.
echo   Starting jobhunt...
echo   Your browser will open shortly.
echo   Press Ctrl+C to stop.
echo.
jobhunt
