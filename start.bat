@echo off
echo Инициализация HeroWarsBot...

IF NOT EXIST "venv" (
    echo Создаем виртуальное окружение...
    python -m venv venv
)

echo Активируем окружение и устанавливаем библиотеки...
call venv\Scripts\activate
pip install -r requirements.txt

echo.
echo Все готово! Запускаем бота...
python main.py
pause