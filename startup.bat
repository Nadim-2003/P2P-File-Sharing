@echo off
REM P2P File-Sharing System Startup Script for Windows

echo.
echo ============================================================
echo   P2P FILE-SHARING SYSTEM - STARTUP MENU
echo ============================================================
echo.
echo 1. Start Tracker Server
echo 2. Start Peer Client (GUI)
echo 3. Run Tests
echo 4. Run Quick Start Examples
echo 5. Exit
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Starting Tracker Server...
    echo.
    python tracker/tracker_server.py
) else if "%choice%"=="2" (
    echo.
    echo Starting Peer Client...
    echo.
    python peer/peer_client.py
) else if "%choice%"=="3" (
    echo.
    echo Running Tests...
    echo.
    python -m unittest tests.test_chunking -v
    pause
) else if "%choice%"=="4" (
    echo.
    echo Running Quick Start Examples...
    echo.
    python quick_start.py
    pause
) else if "%choice%"=="5" (
    exit /b 0
) else (
    echo Invalid choice!
    goto menu
)
