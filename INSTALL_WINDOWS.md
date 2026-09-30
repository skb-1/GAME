# Решение проблемы с PyBullet на Windows

## Ошибка
```
error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools"
Failed to build pybullet
```

## Причина
`pybullet` содержит C++ код и при установке из исходников требует компилятор. Но на PyPI есть готовые колёса (wheels) для Python 3.10 Windows x64, и pip должен брать их, а не собирать.

Почему pip пытается собрать?
- Старый pip (< 22.0) не видит wheel
- Python не 3.10 (например 3.12) — для него может не быть колеса 3.2.5
- Используется `--no-binary`

## Решения (выберите одно)

### Решение 1: Обновить pip и ставить только бинарный пакет (РЕКОМЕНДУЕТСЯ, 1 минута)

```bat
python -m pip install --upgrade pip setuptools wheel
pip install pybullet==3.2.5 --only-binary :all:
```

Проверка:
```bat
pip show pybullet
python -c "import pybullet; print(pybullet.__version__)"
```

Должно показать 3.2.5 без ошибок компиляции.

### Решение 2: Установить Microsoft C++ Build Tools (если Решение 1 не помогло)

1. Скачайте https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Запустите установщик
3. Выберите "Разработка классических приложений на C++" (Desktop development with C++)
4. Установите (около 5 ГБ)
5. Перезагрузите терминал и снова `pip install pybullet==3.2.5`

### Решение 3: Использовать Conda (если у вас Anaconda/Miniconda)

```bat
conda install -c conda-forge pybullet
```

Conda ставит готовый бинарник без компиляции.

### Решение 4: Использовать Pymunk фолбэк (без компиляции, 30 секунд)

В нашей игре физика имеет 3 бэкенда:
1. PyBullet — 3D, лучший
2. Pymunk — 2D, ставится легко, без C++ Build Tools
3. Pure Python stub — всегда работает

Если PyBullet не ставится — игра автоматически переключится на Pymunk или stub.

```bat
pip install pymunk==6.6.0
pip install -r requirements.txt
python main.py --seed 1337
```

Вы увидите в логах:
```
[Physics] PyBullet не найден, пробую Pymunk...
[Physics] Backend: Pymunk 6.6.0
```

Игра работает, но физика упрощённая (2D проекция).

### Решение 5: Играть на stub физике (вообще без зависимостей)

```bat
pip install -r requirements.txt
python main.py --seed 1337
```

Логи:
```
[Physics] Backend: Pure Python stub
```

Физика — простая гравитация + коллизия с землёй y=0, но всё остальное работает: мир, животные, аномалии, инвентарь, сохранения.

## Рекомендуемый порядок установки на Windows 10/11 Python 3.10.0

```bat
REM 1. Проверьте версию
python --version
REM Должно быть Python 3.10.0

REM 2. Venv
python -m venv venv
venv\Scripts\activate

REM 3. Обновите pip
python -m pip install --upgrade pip setuptools wheel

REM 4. Попробуйте PyBullet бинарный
pip install pybullet==3.2.5 --only-binary :all:

REM 5. Если ошибка — ставьте Pymunk
pip install pymunk==6.6.0

REM 6. Остальные зависимости
pip install -r requirements.txt

REM 7. Запуск
python main.py --seed 1337 --location cordon
```

## Проверка что всё работает

```bat
python main.py --no-render --duration 5 --log-level INFO
```

Должно вывести подробные логи:
```
[INFO] [LOCATION] LocationSystem инициализирован, 14 локаций
[INFO] [WORLD] TimeCycle...
[INFO] [PHYSICS] Backend: pybullet / pymunk / stub
[INFO] [GENERAL] Headless run 5.0s
...
```

## Если всё равно не работает

1. Проверьте `game.log` файл — там подробные логи с таймстампами
2. Запустите с `--log-level DEBUG` для максимума инфо
3. Создайте issue с логом

## Почему мы сделали 3 бэкенда?

По ТЗ: PyBullet 3.2.5+ ИЛИ pymunk 6.x. Мы сделали оба + stub, чтобы игра запускалась в любых условиях, даже без компиляторов.

- PyBullet: лучший, 3D, heightfield, raycast
- Pymunk: лёгкий, wheel без компиляции, 2D но с проекцией работает
- Stub: всегда работает, гравитация + интеграция, без внешних зависимостей

CPU: PyBullet самый тяжёлый, Pymunk средний, stub самый лёгкий — для 8 ГБ ОЗУ stub даже лучше.

## Дополнительно: предкомпилированные колёса PyBullet

На PyPI есть файлы:
- pybullet-3.2.5-cp310-cp310-win_amd64.whl — для Python 3.10 Windows x64
- pybullet-3.2.5-cp311-cp311-win_amd64.whl — для 3.11
- и т.д.

Если pip не находит — скачайте вручную с https://pypi.org/project/pybullet/3.2.5/#files и установите:
```bat
pip install C:\path\to\pybullet-3.2.5-cp310-cp310-win_amd64.whl
```
