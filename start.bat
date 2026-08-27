@echo off
:: Enable UTF-8 support in Windows console for proper character rendering
chcp 65001 >nul

echo [SYSTEM] Initializing Hero Wars: Knowledge Engine...

:: Check if the virtual environment exists by looking for the activation script
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [SYSTEM] Virtual environment not found. Creating "venv"...
    python -m venv venv
    
    echo [SYSTEM] Activating environment and installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    
    echo [SYSTEM] Installation complete!
) ELSE (
    echo [SYSTEM] Virtual environment found. Activating...
    call venv\Scripts\activate.bat
)

echo.
echo [SYSTEM] Launching Graphical User Interface (GUI)...
:: Entry point is the GUI, which will spawn the bot process
python gui.py

:: Keep the console window open if the GUI crashes unexpectedly
pause