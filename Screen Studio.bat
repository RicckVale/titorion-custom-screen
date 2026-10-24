@echo off
rem Abre a interface grafica sem janela de terminal.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "src\app.py"
