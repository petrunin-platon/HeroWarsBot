@echo off
:: Новое окно программы (задача 15). Старое окно по-прежнему открывает start.bat
chcp 65001 >nul

echo [SYSTEM] Initializing Hero Wars: Knowledge Engine (new window)...

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
echo [SYSTEM] Launching the new window (gui.py --new-ui)...
python gui.py --new-ui

:: Keep the console window open if the GUI crashes unexpectedly
pause
