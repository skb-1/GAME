@echo off
echo === STALKERcraft Установка для Windows 10/11 Python 3.10.0 ===
echo.

echo [1/6] Проверка Python версии...
python --version
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден! Установите Python 3.10.0 с https://www.python.org/downloads/release/python-3100/
    pause
    exit /b 1
)

echo.
echo [2/6] Обновление pip, setuptools, wheel...
python -m pip install --upgrade pip setuptools wheel

echo.
echo [3/6] Попытка установки PyBullet (бинарный wheel)...
pip install pybullet==3.2.5 --only-binary :all:
if %errorlevel% neq 0 (
    echo ВНИМАНИЕ: PyBullet не установился бинарно, пробую Pymunk фолбэк...
    echo Если нужно 3D физика — установите Microsoft C++ Build Tools:
    echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo И выберите "Desktop development with C++"
) else (
    echo PyBullet установлен успешно!
)

echo.
echo [4/6] Установка Pymunk (2D физика, фолбэк, без компиляции)...
pip install pymunk==6.6.0

echo.
echo [5/6] Установка остальных зависимостей...
pip install -r requirements.txt

echo.
echo [6/6] Проверка установки...
python -c "import numpy, numba, scipy, psutil; print('Основные зависимости OK')"
python -c "import pymunk; print('Pymunk OK')" 2>nul || echo "Pymunk не установлен, будет stub"
python -c "import pybullet; print('PyBullet OK')" 2>nul || echo "PyBullet не установлен, будет Pymunk/stub фолбэк"

echo.
echo === Установка завершена ===
echo Запуск: python main.py --seed 1337 --location cordon
echo Headless тест: python main.py --no-render --duration 5
echo Логи: game.log
echo.
pause
