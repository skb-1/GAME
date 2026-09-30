# STALKERcraft — Процедурная 3D-игра Minecraft + DayZ + S.T.A.L.K.E.R.

**Python 3.10.0 | Panda3D 1.10.14 | Полностью процедурные модели, текстуры, анимации**

## Ключевое требование — НИКАКИХ внешних ассетов

Все 3D-модели, текстуры, анимации генерируются кодом в рантайме:
- Деревья — L-system / рекурсивная генерация
- Животные — параметрические скелетные меши с IK анимацией
- Оружие, предметы — параметрические меши из примитивов
- Здания ЧАЭС — модульная генерация из блоков
- Камни, кусты — шумовая деформация
- Персонаж — параметрический гуманоид
- Текстуры — Perlin/Simplex шум + фильтры в Numpy -> GPU напрямую
- Анимации — скелет кодом, ключевые кадры синусоидами + IK

## Архитектура и обоснование библиотек

### Рендер: Panda3D 1.10.14 (выбран)
**Почему Panda3D, а не Ursina или Pyglet+PyOpenGL:**
- Прямой доступ к GeomVertexData/GeomTriangles для процедурных мешей (критично)
- Встроенный frustum culling, LODNode, instancing, шейдерная система
- Поддержка PBR через кастомные шейдеры
- Оптимизирован под слабое железо, сжатые текстуры, атласы
- Совместимость с PyBullet
- Python 3.10.0 поддержка, кроссплатформенность Windows 10/11 x64, Linux
- Ursina — удобная обёртка, но скрывает low-level Geom API, меньше контроля
- Pyglet+PyOpenGL — требует писать всё с нуля (камера, culling, LOD), дольше и больше багов

### Физика: PyBullet 3.2.5
- Heightfield для террейна, raycast, rigid bodies
- Python 3.10 совместимость
- Pymunk — 2D, не подходит

### Оптимизация под 8 ГБ ОЗУ
- Чанковая система (load/unload по дистанции)
- LOD 3 уровня (кластеризация вершин)
- Object pooling (пули, частицы, звуки)
- Frustum culling
- Асинхронная генерация чанков (threading)
- Сжатые текстуры, атласы, инстансинг
- Кэш мешей на диск .npz + weakref в памяти
- Ручной GC tuning (gc.freeze, gc.disable в кадрах)
- __slots__ во всех горячих классах
- Numpy float32/int32 вместо float64

## Структура проекта

```
GAME/
├── main.py                         # Точка входа, ShowBase, игровой цикл
├── config.py                       # Константы, балансы
├── requirements.txt                # Точные версии под Python 3.10.0
├── utils/
│   ├── procedural_mesh.py          # ЯДРО: примитивы, модификаторы, merge, LOD, экспорт в Panda3D
│   ├── procedural_texture.py       # ЯДРО: PBR материалы из шума
│   ├── procedural_animation.py     # ЯДРО: скелет, FABRIK IK, walk/idle/run/attack, блендинг
│   ├── lsystem.py                  # L-system деревья, кусты
│   ├── asset_cache.py              # Кэш мешей/текстур на диск .npz + память weakref
│   ├── optimization.py             # Пулы, LOD, frustum culling, GC tuning, F3 overlay
│   └── math_utils.py               # Perlin/FBM на Numba, матрицы
├── world/
│   ├── chunk_system.py             # Чанки, async генерация, терраформинг
│   ├── noise_gen.py                # Heightmap + биомы на Numba, marching cubes упрощённый
│   ├── biome.py                    # Свойства биомов
│   ├── weather.py                  # Погода, выброс
│   ├── time_cycle.py               # 24 игровых минуты = сутки
│   └── terraforming.py             # Копание/стройка деформацией меша
├── physics/
│   └── physics_engine.py           # PyBullet обёртка
├── entities/
│   ├── player.py                   # Игрок с процедурным гуманоидом
│   ├── animal_ai.py                # Behavior Trees + Utility AI
│   ├── animal_generator.py         # Генератор моделей животных по видам
│   └── base_entity.py
├── anomalies/
│   ├── anomaly_system.py           # Электра, Жарка, Холодец, Трамплин, Воронка, Гравиконцентрат, Кисель, Жгучий пух
│   └── artifact_system.py          # Артефакты, привязка к аномалиям, артефакт->аномалия
├── radiation/
│   ├── geiger.py                   # Счётчик Гейгера
│   └── radiation_map.py            # Карта заражения
├── survival/
│   ├── needs.py                    # Голод, жажда, усталость, радиация
│   ├── body_zones.py               # Зоны тела HP, раны, переломы, кровотечение
│   ├── medicine.py                 # Бинты, антирад, etc
│   └── sleep.py                    # Сон с событиями
├── items/
│   ├── inventory.py                # Инвентарь с весом
│   ├── durability.py               # Прочность
│   ├── item_defs.py                # Определения предметов
│   └── item_generator.py           # Процедурные модели предметов
├── chernobyl/
│   ├── chernobyl_location.py       # Саркофаг, Припять, Юпитер — модульно
│   └── building_blocks.py          # Блоки зданий
├── ui/
│   ├── menu.py                     # Главное меню, пауза
│   ├── hud.py                      # HUD, F3 overlay
│   └── console.py                  # Консоль F8
├── save/
│   └── save_manager.py             # pickle+zlib сохранения
├── spawn/
│   └── spawn_manager.py            # Спавн животных/предметов по биомам
├── shaders/
│   └── shader_generator.py         # Процедурные GLSL шейдеры
├── assets_cache/                   # Кэш сгенерированных мешей (gitignored)
└── saves/                          # Сохранения (gitignored)
```

## Генерация моделей — подробно

### utils/procedural_mesh.py
- **MeshData** — vertices (N,3) float32, normals, uvs, indices, bone_weights
- **PrimitiveFactory**: box, sphere, cylinder, capsule, cone, plane
- **Modifier**: noise_displace (Perlin по нормалям), twist, taper, bend, subdivide (каждый треугольник на 4), extrude
- **Операции**: merge_meshes, transform_mesh (4x4 матрица), mirror_mesh (смена winding)
- **UV**: box (по доминирующей оси нормали), cylindrical, spherical
- **LOD**: кластеризация вершин по сетке, 3 уровня
- **Экспорт**: export_to_panda3d (GeomVertexData, GeomTriangles) и export_to_dict для кэша
- **Сложные генераторы**: generate_tree_trunk, generate_rock, generate_bush, generate_weapon_mesh, generate_humanoid_full

### utils/procedural_texture.py
- Шум: generate_perlin_texture (Numba FBM), generate_voronoi_texture
- Normal map из height map через Sobel (scipy)
- PBRMaterial: albedo (H,W,3), roughness (H,W), metallic, normal, height
- Генераторы: wood (кольца + волокна), stone (voronoi+fbm), metal (царапины+ржавчина), concrete, fabric (плетение sin), skin, fur (направленные волокна), rust, water (анимированный), grass
- material_to_panda3d_textures — Numpy -> Panda3D Texture.setRamImage

### utils/procedural_animation.py
- Bone, Skeleton — кости с parent, position, rotation, children
- FABRIKSolver — IK для цепочки
- ProceduralAnimationGenerator: walk_cycle (синусоиды, противофаза ног/рук), idle (дыхание), run, attack (замах-удар-возврат)
- blend_animations — lerp между анимациями
- Генераторы скелетов: humanoid (hips->spine->chest->head + arms + legs), quadruped (волк, олень)
- Веса вершин по близости к костям

### utils/lsystem.py
- LSystem с правилами и вероятностями, детерминирован по seed
- Turtle3D — 3D черепашка с position, direction, up, thickness, стек
- Интерпретация: F вперёд, + - поворот, & ^ pitch, \ / roll, [ ] push/pop
- Ветки -> цилиндры + сферы листьев, трансформация по направлению
- Виды: oak (широкие ветви), pine (узкая), birch, red_forest (искажённая)

## Механики

### Мир и геометрия
- Heightmap через Numba FBM Perlin, 32x32 чанки, полигональная сетка (не воксели)
- Terraforming в реальном времени — деформация heightmap + перестройка меша чанка в потоке
- Вода (шейдер), погода, день/ночь (24 игровых минуты = сутки)

### Выживание DayZ-стиль
- Тело по зонам: head/torso/arms/legs — отдельные HP, кровотечение, переломы, боль
- Показатели: HP, сытость, жажда, бодрость, температура, усталость, радиация, инфекция
- Сон с событиями, лекарства, прочность предметов

### Животные
- Виды: волк, медведь, кабан, олень, заяц, ворон, змея
- Для каждого — процедурный меш + скелет + анимации
- Behavior Trees + Utility AI: стайность, территориальность, расписание, память об игроке, тактика окружения
- Реакция на звук, запах, свет, ранение, кровь

### Аномалии и артефакты S.T.A.L.K.E.R.-стиль
- Типы: Электра, Жарка, Холодец, Трамплин, Воронка, Гравиконцентрат, Кисель, Жгучий пух
- Визуал — процедурные меши + шейдеры (пульсация, свечение)
- Артефакты привязаны к аномалиям, модели — искажённые сферы с шумом
- Ключевое: выброшенный артефакт в правильных условиях -> зарождает аномалию
- Респавн каждый игровой день
- Радиация: карта заражения, счётчик Гейгера (треск по уровню)

### ЧАЭС
- Саркофаг, Припять, Юпитер, рыжий лес — модульная генерация из блоков
- Разрушаемость, строительство укреплений
- Внутри — особый лут, высокая радиация, мутанты

## Запуск

### Windows 10/11, Python 3.10.0

```bat
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py --seed 1337
```

### Linux

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py --seed 1337
```

### Headless (без окна, для тестов)

```bash
python main.py --no-render --duration 10
```

### Управление
- WASD — движение
- Shift — бег
- Ctrl — присед
- Мышь — взгляд
- ЛКМ — копать/строить
- F3 — дебаг overlay (FPS, RAM, чанки, сущности)
- F5 — быстрое сохранение
- F8 — консоль
- Esc — меню

### Консоль команды
```
give <item> [count]
spawn <entity> [count] [x y z]
spawn_anomaly <type> [x y z]
spawn_artifact <type> [x y z]
teleport <x y z>
set_radiation <value>
set_time <hour>
set_weather <type> (clear, rain, fog, storm, emission)
god, noclip, kill_all, save, load
regen_assets <type|all>
set_seed <int>
help
```

## Оптимизация под 8 ГБ

- Чанки: только 5 радиус вокруг игрока, выгрузка по LRU
- LOD: 3 уровня, выбор по дистанции
- Object pooling для пуль, частиц, звуков
- Frustum culling по сферам чанков
- Async генерация чанков в потоке
- Текстуры 256x256, атласы 2048, сжатие
- Кэш мешей: память weakref + диск .npz
- GC: disable в кадре, enable после, collect каждые 5 сек, freeze
- __slots__ в горячих классах
- Numpy float32, Numba JIT для шума

## Сохранения

- F5 быстрое, автосейв каждый день и по событиям
- Формат: pickle + zlib (быстро, компактно)
- Сохраняется всё: мир, инвентарь, животные, аномалии, время, погода, игрок, seed

## Дальнейшее развитие

- Полный marching cubes / dual contouring для пещер
- PBR шейдеры с процедурными текстурами в Panda3D
- 3D-звук с эхо, процедурная генерация звуков через numpy -> wav в памяти
- Разрушаемость зданий ЧАЭС через boolean мешей
- Экосистема: травоядные -> хищники -> падальщики -> гниение

## Лицензия

MIT, все ассеты процедурные, внешних файлов нет.
