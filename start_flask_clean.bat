@echo off
echo Killing all Python processes...
taskkill /F /IM python.exe 2>nul

echo Waiting for processes to terminate...
timeout /t 5 /nobreak >nul

echo Starting Flask on port 5001...
cd "C:\Anas's PC\Moaz\Sales Master"
python app.py

pause
