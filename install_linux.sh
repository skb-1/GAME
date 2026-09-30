#!/bin/bash
echo "=== STALKERcraft Установка для Linux Python 3.10.0 ==="
echo ""

echo "[1/6] Проверка Python версии..."
python3.10 --version
if [ $? -ne 0 ]; then
    echo "ОШИБКА: Python 3.10 не найден! Установите python3.10"
    exit 1
fi

echo ""
echo "[2/6] Создание venv..."
python3.10 -m venv venv
source venv/bin/activate

echo ""
echo "[3/6] Обновление pip..."
pip install --upgrade pip setuptools wheel

echo ""
echo "[4/6] Установка PyBullet (обычно ставится без проблем на Linux)..."
pip install pybullet==3.2.5 --only-binary :all: || pip install pybullet==3.2.5

echo ""
echo "[5/6] Установка Pymunk и остальных..."
pip install pymunk==6.6.0
pip install -r requirements.txt

echo ""
echo "[6/6] Проверка..."
python -c "import numpy, numba, scipy, psutil; print('Основные зависимости OK')"
python -c "import pymunk; print('Pymunk OK')" || echo "Pymunk не установлен"
python -c "import pybullet; print('PyBullet OK')" || echo "PyBullet не установлен, будет фолбэк"

echo ""
echo "=== Установка завершена ==="
echo "Запуск: python main.py --seed 1337 --location cordon"
echo "Headless: python main.py --no-render --duration 5"
