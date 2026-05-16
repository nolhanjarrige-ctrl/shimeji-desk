@echo off
title Shimeji Desk
cd /d "%~dp0"

:: Vérifier Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Telecharge Python sur https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Vérifier/installer les dependances au premier lancement
if not exist ".deps_ok" (
    echo Installation des dependances...
    python -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo [ERREUR] Echec de l'installation des dependances.
        pause
        exit /b 1
    )
    echo. > .deps_ok
)

:: Lancer Shimeji Desk (sans fenetre console)
start "" pythonw main.py
