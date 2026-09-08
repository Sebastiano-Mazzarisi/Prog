@echo off
cd /d "C:\Dropbox\Prog\Allenamento"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Dropbox\Prog\Allenamento\Aggiorna_GitHub.ps1" >> "C:\Dropbox\Prog\Allenamento\Aggiorna_GitHub.log" 2>&1
