@echo off
REM Start P2P File-Sharing Client
REM No login required - uses persistent peer identity

echo ========================================
echo   P2P File-Sharing Client
echo   Like qBittorrent - No Login Required
echo ========================================
echo.

REM Start tracker server first (if not running)
echo Checking if tracker is running...
netstat -ano | findstr :5000 >nul
if %errorlevel% neq 0 (
    echo Starting tracker server...
    start "P2P Tracker" cmd /k "python tracker/tracker_server.py"
    timeout /t 2 >nul
) else (
    echo Tracker already running on port 5000
)

echo.
echo Starting peer client...
python peer/peer_client.py

pause
