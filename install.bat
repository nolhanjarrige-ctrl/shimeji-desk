@echo off
title Shimeji Desk – Installation
cd /d "%~dp0"
echo ============================================
echo   Shimeji Desk – Installation
echo ============================================
echo.

:: Vérifier Python 3.10+
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe.
    echo Telecharge Python 3.10+ sur https://www.python.org/downloads/
    echo Coche "Add Python to PATH" lors de l'installation !
    pause
    exit /b 1
)

echo Installation des dependances Python...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERREUR] Echec de l'installation.
    pause
    exit /b 1
)

:: Supprimer le cache de deps si existant
if exist ".deps_ok" del ".deps_ok"
echo. > .deps_ok

echo.
echo ============================================
echo   Installation terminee !
echo   Lance Shimeji Desk avec launch.bat
echo ============================================
pause
