@echo off
:: Старое окно программы (на всякий случай). Обычный запуск start.bat открывает новое окно (задача 15)
chcp 65001 >nul

echo [SYSTEM] Initializing Hero Wars: Knowledge Engine (old window)...

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
echo [SYSTEM] Launching the old window (gui.py --old-ui)...
python gui.py --old-ui

:: Keep the console window open if the GUI crashes unexpectedly
pause
