@echo off
REM Quick ngrok setup for SalesBreachPro webhook testing

echo Starting SalesBreachPro with Ngrok webhook...
echo.

REM Default port
set PORT=5000

REM Check if custom port provided
if "%1" neq "" (
    set PORT=%1
)

echo Using port: %PORT%
echo.

REM Run the ngrok setup script
python setup_ngrok_webhook.py %PORT%

echo.
echo Press any key to exit...
pause > nul