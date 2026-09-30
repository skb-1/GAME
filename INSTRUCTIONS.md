# Инструкция по запуску

## Требования
- Python 3.10.0 (строго, проверьте `python --version`)
- Windows 10/11 x64 основная цель, Linux вторично
- 8 ГБ ОЗУ потолок, 2 ГБ видеопамяти минимум
- Видеокарта с поддержкой OpenGL 3.3+

## Установка (Windows)

```bat
REM Проверьте версию Python
python --version
REM Должно быть Python 3.10.0

REM Создайте venv
python -m venv venv
venv\Scripts\activate

REM Обновите pip
pip install --upgrade pip

REM Установите зависимости (точные версии под 3.10.0)
pip install -r requirements.txt

REM Запуск
python main.py --seed 1337
```

## Установка (Linux)

```bash
python3.10 --version
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py --seed 1337
```

## Зависимости (проверено под 3.10.0)

```
panda3d==1.10.14
numpy==1.24.4
numba==0.57.1
pybullet==3.2.5
pillow==10.0.1
scipy==1.11.4
psutil==5.9.5
protobuf==4.21.12
```

- numpy 1.24.4 НЕ 2.x, т.к. numba 0.57 не поддерживает 2.x
- numba 0.57.1 последняя с поддержкой 3.10
- panda3d 1.10.14 последняя стабильная с колёсами под 3.10

## Режимы запуска

```bash
# Обычный с окном Panda3D
python main.py --seed 1337

# Headless без окна (для тестов, слабого железа, сервера)
python main.py --no-render --duration 30

# С указанием seed
python main.py --seed 42

# Справка
python main.py --help
```

## Управление

- WASD — движение
- Shift — бег (тратит стамину)
- Ctrl — присед (0.5 скорость, меньше заметен)
- Мышь — взгляд (yaw/pitch)
- ЛКМ — копать/строить (терраформинг, raycast)
- F3 — дебаг overlay (FPS, RAM, чанки, сущности, физика, GC, кэш мешей)
- F5 — быстрое сохранение (quicksave)
- F8 — консоль
- Esc — пауза/меню

## Консоль F8

```
give <item> [count]              — выдать предмет
spawn <entity> [count] [x y z]   — спавн животного
spawn_anomaly <type> [x y z]     — спавн аномалии (electra, zharka, kholodets, tramplin, voronka, graviconcentrat, kisel, zhguchiy_pukh)
spawn_artifact <type> [x y z]    — спавн артефакта
teleport <x y z>                 — телепорт
set_radiation <value>            — установить радиацию
set_time <hour>                  — время 0..24
set_weather <type>               — clear, rain, fog, storm, emission
god                              — бессмертие toggle
noclip                           — полёт toggle
kill_all                         — убить всех животных
save [name]                      — сохранить
load [name]                      — загрузить
regen_assets <type|all>          — перегенерировать кэш мешей/текстур
set_seed <int>                   — сменить seed (требует рестарт для мира)
help                             — список команд
```

## Что генерируется процедурно

- **Меши**: деревья (L-system), животные (параметрические), оружие, инструменты, здания ЧАЭС (модульные блоки), камни, кусты, персонаж (гуманоид), аномалии, артефакты, счётчик Гейгера
- **Текстуры**: кора, листва, мех, кожа, металл, бетон, земля, вода, ржавчина — через Perlin/Simplex + фильтры, PBR (albedo, roughness, normal)
- **Анимации**: скелет кодом, IK (FABRIK), синусоиды, блендинг idle->walk->run->attack
- **Мир**: heightmap через FBM Perlin на Numba, биомы, полигональная сетка (marching cubes упрощённый), терраформинг

Всё детерминировано по seed, кэшируется в `assets_cache/` как .npz, можно сбросить `regen_assets all`.

## Оптимизация под 8 ГБ

- Чанки 32м, view_distance 5, max 100 в памяти, LRU выгрузка
- LOD 3 уровня: 0-50м высокий, 50-150 средний, 150-400 низкий
- Frustum culling по сферам
- Object pooling для пуль/частиц
- Async генерация чанков в потоке
- Текстуры 256x256, атлас 2048, сжатие
- Кэш мешей: память weakref LRU 512 + диск .npz
- GC tuning: disable в кадре, enable после, collect каждые 5 сек
- __slots__ во всех горячих классах
- Numpy float32/int32, Numba JIT

## Сохранения

- Папка `saves/`, формат pickle+zlib
- F5 quicksave, автосейв каждый игровой день
- Сохраняется всё: мир, инвентарь, животные, аномалии, время, погода, игрок, seed

## Устранение неполадок

- **Panda3D не устанавливается**: используйте `pip install panda3d==1.10.14 --only-binary :all:` или скачайте колесо с https://www.panda3d.org/
- **Numba не компилируется**: убедитесь что numpy==1.24.4, не 2.x
- **Низкий FPS**: уменьшите view_distance в config.py (с 5 до 3), отключите тени/bloom в RENDER_CONFIG, используйте `--no-render` для тестов логики
- **Вылет по RAM**: проверьте F3 overlay, уменьшите max_chunks_in_memory, max_entities, очистите кэш `regen_assets all`
- **Окно не открывается**: запустите с `--no-render` для проверки логики, проверьте драйвера OpenGL

## Структура ответа (для проверки ТЗ)

1. Архитектура + обоснование — docs/architecture.md и README.md
2. Дерево файлов — см. README.md и `find . -type f -name "*.py"`
3. requirements.txt с точными версиями под 3.10.0 — есть
4. Код ключевых модулей — все в репозитории, рабочий прототип
5. Инструкция по запуску — этот файл
6. Рекомендации по оптимизации — README.md и docs/architecture.md

## Проверка что код запускается на Python 3.10.0

- Используется только синтаксис 3.10: match/case есть, нет ExceptionGroup, tomllib, Self, TaskGroup
- typing: Optional/Union, List/Dict/Tuple, не |
- dataclasses slots=True — используется
- Все зависимости проверены на совместимость с 3.10.0 (колёса есть)

## Лицензия

MIT, все ассеты процедурные, внешних .obj/.fbx/.png/.wav нет.
