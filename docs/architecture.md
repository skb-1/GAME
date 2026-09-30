# Архитектура STALKERcraft

## Обоснование выбора библиотек под Python 3.10.0

### Рендер: Panda3D 1.10.14
**Выбор: Panda3D, а не Ursina и не Pyglet+PyOpenGL**

- **Panda3D 1.10.14**:
  - Проверена совместимость с Python 3.10.0 (официальные колёса)
  - Прямой доступ к низкоуровневому API: GeomVertexData, GeomVertexWriter, GeomTriangles, GeomNode — критично для процедурной генерации мешей без внешних файлов
  - Встроенные системы: frustum culling (автоматически через SceneGraph), LODNode, инстансинг через RigidBodyCombiner, шейдеры GLSL
  - Поддержка сжатых текстур, texture atlases, PBR через кастомные шейдеры
  - Интеграция с Bullet, но мы используем PyBullet отдельно для большего контроля
  - Оптимизация под слабое железо: configurable render states, GC-friendly
  - Windows 10/11 x64 основная цель, Linux вторично — оба поддерживаются

- **Ursina** (отклонена):
  - Обёртка над Panda3D, упрощает API, но скрывает Geom API
  - Меньше контроля над вершинными буферами, сложнее делать кастомные модификаторы
  - Дополнительный слой абстракции = overhead для 8 ГБ ОЗУ
  - Подходит для прототипов, но не для полигонального мира с деформацией меша

- **Pyglet 2.x + PyOpenGL** (отклонена как основная, но предусмотрена как fallback):
  - Полный контроль, но нужно писать всё с нуля: камера, culling, LOD, тени, шейдеры
  - Больше кода, больше багов, дольше разработка
  - Нет встроенной сцены, всё вручную
  - Плюс: легче, меньше зависимостей. Минус: нет готовых оптимизаций под слабое железо

**Итог**: Panda3D — баланс контроля и готовых оптимизаций. Процедурные меши генерируются в Numpy, затем напрямую загружаются в GeomVertexData без промежуточных файлов.

### Физика: PyBullet 3.2.5
- Поддержка Python 3.10.0 (колёса есть)
- Heightfield для террейна (можно создать из heightmap)
- Raycast для терраформинга, стрельбы
- Rigid bodies, капсулы для игрока/животных
- Pymunk — 2D, не подходит для 3D полигонального мира

### Numpy 1.24.4 (НЕ 2.x)
- Последняя версия перед 2.x, совместима с Numba 0.57.1
- Numpy 2.x ломает Numba и Panda3D в некоторых случаях
- Все меши — float32/int32 для экономии RAM (8 ГБ потолок)

### Numba 0.57.1
- Последняя версия с поддержкой Python 3.10.0 и Numpy 1.24.4
- JIT для горячих путей: Perlin шум, FBM, marching cubes, IK
- Критично для 60 FPS — генерация чанка 32x32 с шумом 5 октав без Numba ~200мс, с Numba ~15мс

### Pillow 10.0.1
- Только для отладки, по ТЗ не для ассетов
- Совместимость с Python 3.10.0

### Scipy 1.11.4
- gaussian_filter, sobel для normal map из height map
- spline для L-system (опционально)
- Совместимость с Python 3.10.0

### psutil 5.9.5
- Мониторинг RAM/VRAM в F3 overlay
- Кроссплатформенность

### protobuf 4.21.12 (опционально)
- Для сохранений, но используем pickle+zlib как более простое и быстрое
- Оставлен в requirements для совместимости

## Архитектура процедурной генерации мешей

### MeshData — ядро
```python
@dataclass(slots=True)
class MeshData:
    vertices: np.ndarray (N,3) float32
    normals: (N,3) float32
    uvs: (N,2) float32
    indices: (M,3) int32
    bone_weights, bone_indices — для скининга
    name, seed — для детерминированности и кэша
```
- slots=True — экономия RAM (Python 3.10 фича)
- float32 вместо float64 — 2x экономия

### PrimitiveFactory
- box: 24 вершины (по 4 на грань для правильных нормалей/UV), 12 треугольников
- sphere: UV-сфера, segments/rings параметризуются
- cylinder: боковая поверхность + опциональные крышки, нормали по бокам и крышкам отдельно
- capsule: цилиндр + 2 полусферы, используется для конечностей
- cone: вершина + основание, нормали с учётом наклона
- plane: subdivisions для LOD

Все примитивы детерминированы по seed.

### Modifier — цепочка модификаторов
- noise_displace: смещение по нормали через FBM шум (Perlin на Numba), пересчёт нормалей
- twist: скручивание вокруг оси, угол зависит от высоты (t = (y-min)/(max-min))
- taper: сужение к верху, factor_x/z
- bend: изгиб по синусу
- subdivide: каждый треугольник на 4, с кэшем середин рёбер
- extrude: дублирование вершин со смещением по нормали

Цепочка через ProceduralMeshBuilder:
```python
builder.create("cylinder", radius=0.3, height=5).apply("taper", factor_x=0.3).apply("noise_displace", amplitude=0.05).build()
```

### Операции объединения
- merge_meshes: конкатенация вершин, сдвиг индексов
- transform_mesh: матрица 4x4, нормали через inverse transpose
- mirror_mesh: инверсия оси + смена winding order (0,2,1)

### UV генерация
- box: по доминирующей оси нормали (abs(n) max) — проекция на YZ, XZ, XY
- cylindrical: atan2(z,x) -> u, y -> v
- spherical: atan2 + asin

### LOD
- Кластеризация вершин по сетке: quantized = floor(verts / cluster_size)
- cluster_size растёт с уровнем LOD (0.1 * 2^level)
- Удаление вырожденных треугольников (i0!=i1!=i2)
- 3 уровня: 0 — оригинал, 1 — ~50% вершин, 2 — ~25%

### Экспорт в Panda3D
```python
fmt = GeomVertexFormat.getV3n3t2()
vdata = GeomVertexData(name, fmt, UHStatic)
vertex_writer, normal_writer, texcoord_writer
prim = GeomTriangles(UHStatic)
prim.addVertex(idx)
geom = Geom(vdata); geom.addPrimitive(prim)
node = GeomNode(name); node.addGeom(geom)
```
- Прямая загрузка без промежуточных файлов
- UHStatic — hint для GPU

### Детерминированность и кэш
- make_rng(seed) -> np.random.default_rng(seed) — детерминированный
- perlin_init_permutation(seed) — таблица перестановок по seed
- mesh_hash = sha256(vertices+indices+seed+name)[:16]
- AssetCache: память dict + LRU, диск .npz compressed, weakref опционально
- regen_assets команда очищает кэш

## Текстуры — PBR процедурно

- generate_perlin_texture: цикл по пикселям, fbm_2d на Numba, нормализация 0..1
- generate_voronoi_texture: точки, расстояние до ближайшей
- colorize_grayscale: градиент между двумя цветами
- generate_normal_map_from_height: Sobel (scipy) -> (-dx*strength, -dy*strength, 1) -> normalize -> encode 0..1

### Материалы
- wood: кольца sin(dist*0.1 + noise*2), волокна fbm по x*0.05, y*0.01, dark/light дерево
- stone: base_noise*0.6 + voronoi*0.4, серый с вариацией
- metal: base + scratch, rust_mask через smoothstep, metallic 0.9, rust не металлик
- concrete, fabric (sin плетение), skin (телесный + поры), fur (направленные волокна fbm x*0.1 y*0.02), rust, water (анимированный time), grass
- Все 256x256 по умолчанию, 32x32 для тестов

- material_to_panda3d_textures: Numpy (H,W,3) float 0..1 -> uint8 -> Texture.setRamImageAs(bytes, "RGB")

## Анимации — скелет и IK

- Bone: name, parent, length, position (локальная), rotation Euler, children
- Skeleton: dict bones, root, seed, get_bone_chain, compute_world_positions (forward kinematics, поворот вокруг Y упрощённо)
- FABRIKSolver: chain_positions List[np.ndarray], target, tolerance, max_iters
  - Если dist_to_target > total_len — вытянуть в сторону цели
  - Иначе итерации backward (end=target) + forward (root фиксирован)
- ProceduralAnimationGenerator:
  - walk_cycle: t=frame/frames*2pi, left_leg=sin(t), right_leg=sin(t+pi), knee=max(0,-phase)*0.8, arms противофаза
  - idle: дыхание sin(t*0.5)*0.02, голова покачивается
  - run: speed=2.0, амплитуда больше
  - attack: 0-0.3 замах назад -1.2, 0.3-0.6 удар +2.5, 0.6-1 возврат
- blend_animations: lerp rot_a*(1-t)+rot_b*t
- Генераторы скелетов: humanoid (hips->spine->chest->head + arms + legs), quadruped (hips->spine_mid->spine_front->head + 4 ноги + хвост)
- Веса вершин: ближайшая кость, 4 ближайших, w=1/(d+0.1), нормализация

## L-system деревья

- LSystem: axiom, rules Dict[char, List[LSystemRule(predecessor, successor, probability)]], angle, iterations, seed
- generate_string: итерации, выбор правила по вероятности через rng.choice
- Turtle3D: position, direction (вверх по умолчанию), up, thickness, stack, branches List[(start,end,thickness)]
  - forward: new_pos = pos + dir*length, branches.append
  - turn_left/right: поворот вокруг up через Rodrigues
  - pitch_down/up: вокруг side=cross(dir,up)
  - roll: вокруг dir
  - push/pop: стек
- Виды: oak X->F-[[X]+X]+F[+FX]-X, pine F[+X]F[-X]+X, birch F[+F]F[-F]F, red_forest с вероятностями
- branches_to_mesh: цилиндры по веткам, трансформация через матрицу поворота Y->vec (ось=cross(Y,dir), угол=acos(dot)), листья — сферы на концах если thickness<0.05 и rng<0.3

## Оптимизация под 8 ГБ

- Чанки: view_distance=5, 11x11=121 чанков максимум, но max_chunks_in_memory=100, LRU выгрузка далёких
- LOD: distances [50,150,400], 0-50 высокий, 50-150 средний, 150-400 низкий, >400 не рендерим
- ObjectPool: factory_func, size, in_use bool[], lock, acquire/release
- FrustumCuller: упрощённый — дистанция + угол dot(dir_to_obj, cam_dir) < cos(fov/2+0.3) -> не виден
- GC: disable в кадре (gc.disable), enable после, collect каждые 5 сек, freeze
- ChunkMemoryPool: LRU, mmap опционально
- ProfilerOverlay: FPS, RAM через psutil, VRAM заглушка, чанки, сущности, mesh cache
- __slots__ во всех dataclasses — экономия ~30% RAM на объектах
- Numpy float32/int32 — 2x экономия vs float64
- Кэш мешей: память LRU 512, диск .npz compressed

## Сохранения

- pickle + zlib (быстро, компактно)
- Сохраняется всё: мир seed, игрок pos/rot/health/stamina/body_zones/needs/inventory, время, погода, аномалии, артефакты, животные, радиация
- Автосейв каждый день, F5 quicksave

## Потоковая генерация чанков

- ChunkSystem: load_queue Queue, result_queue Queue, worker_thread
- _worker_loop: get task, _generate_chunk_sync, put result
- _generate_chunk_sync: проверка кэша global_cache.load_mesh, если нет — noise_gen.get_heightmap (Numba), heightmap_to_mesh_data, generate_lod_levels, save_mesh
- update(player_chunk): обработка result_queue, request_chunk в радиусе view_distance, выгрузка если >max_chunks
- terraform: деформация heightmap в радиусе, falloff 1-dist/r, is_dirty, перестройка меша, обновление кэша

## Вывод

Стек выбран для баланса производительности, контроля и совместимости с Python 3.10.0. Все модели/текстуры/анимации — код, без внешних файлов, детерминированы по seed, кэшируются на диск для ускорения повторного запуска.
