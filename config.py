"""
Конфигурация игры. Python 3.10.0 совместимость.
Все константы, настройки баланса, версии зависимостей.
"""
from typing import Dict, Tuple
import os

# Версии зависимостей (проверено под Python 3.10.0)
DEPENDENCIES = {
    "panda3d": "1.10.14",
    "numpy": "1.24.4",
    "numba": "0.57.1",
    "pybullet": "3.2.5",
    "pillow": "10.0.1",
    "scipy": "1.11.4",
    "psutil": "5.9.5",
    "protobuf": "4.21.12",
}

# Параметры окна и рендера
RENDER_CONFIG = {
    "window_width": 1920,
    "window_height": 1080,
    "target_fps": 60,
    "min_fps": 30,
    "fov": 75,
    "near_clip": 0.1,
    "far_clip": 2000.0,
    "shadow_map_size": 1024,
    "enable_bloom": True,
    "enable_fog": True,
    "enable_shadows": True,
}

# Мир
WORLD_CONFIG = {
    "world_seed": 1337,
    "chunk_size": 32,  # метров
    "chunk_height": 128,
    "view_distance_chunks": 5,  # радиус загрузки
    "world_size_chunks": 64,  # 64*32 = 2048 метров в сторону
    "terrain_scale": 0.015,
    "terrain_amplitude": 45.0,
    "terrain_octaves": 5,
    "terrain_lacunarity": 2.0,
    "terrain_persistence": 0.5,
    "sea_level": 5.0,
    "marching_cubes_iso": 0.0,
}

# Оптимизация под 8 ГБ
OPTIMIZATION_CONFIG = {
    "max_entities": 256,
    "max_chunks_in_memory": 100,
    "max_procedural_mesh_cache": 512,
    "texture_atlas_size": 2048,
    "lod_distances": [50.0, 150.0, 400.0],
    "gc_collect_interval": 5.0,  # секунд
    "use_mmap_for_chunks": True,
    "pool_sizes": {
        "bullets": 64,
        "particles": 512,
        "sounds": 32,
    },
    "compress_textures": True,
    "enable_frustum_culling": True,
    "enable_occlusion_culling": False,  # дорого для слабого железа
}

# Выживание
SURVIVAL_CONFIG = {
    "max_hp": 100.0,
    "hunger_decrease_per_min": 0.5,
    "thirst_decrease_per_min": 0.8,
    "stamina_max": 100.0,
    "radiation_max": 1000.0,  # мЗв
    "body_zones": ["head", "torso", "left_arm", "right_arm", "left_leg", "right_leg"],
}

# Аномалии
ANOMALY_CONFIG = {
    "types": ["electra", "zharka", "kholodets", "tramplin", "voronka", "graviconcentrat", "kisel", "zhguchiy_pukh"],
    "respawn_interval_hours": 24,  # игровых часов
    "max_anomalies_per_chunk": 2,
    "radiation_per_type": {
        "electra": 15.0,
        "zharka": 25.0,
        "kholodets": 10.0,
        "tramplin": 5.0,
        "voronka": 30.0,
        "graviconcentrat": 40.0,
        "kisel": 20.0,
        "zhguchiy_pukh": 12.0,
    },
}

# Животные
ANIMAL_CONFIG = {
    "types": ["wolf", "bear", "boar", "deer", "hare", "raven", "snake"],
    "max_per_chunk": 3,
    "despawn_distance": 500.0,
}

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_CACHE_DIR = os.path.join(BASE_DIR, "assets_cache")
SAVE_DIR = os.path.join(BASE_DIR, "saves")

# Создаём папки
os.makedirs(ASSET_CACHE_DIR, exist_ok=True)
os.makedirs(SAVE_DIR, exist_ok=True)

# Биомы
BIOME_TYPES = ["forest", "field", "swamp", "mountains", "red_forest", "wasteland"]

# Время
TIME_CONFIG = {
    "day_length_minutes": 24,  # 24 игровых минуты = сутки
    "start_hour": 8.0,
}

# Радиация
RADIATION_CONFIG = {
    "chernobyl_center": (0, 0),  # координаты центра зоны
    "max_radius": 800.0,
    "background": 0.05,  # мкЗв/ч
}

# Локации Сталкера — разделение карты для снижения CPU
LOCATION_CONFIG = {
    "enabled": True,  # включить систему локаций (разделение карты)
    "preload_neighbors": True,  # предзагружать соседние локации
    "unload_distant": True,  # выгружать далёкие
    "transition_radius": 8.0,  # радиус перехода
    "start_location": "cordon",  # стартовая локация
    # Список локаций см. world/location_system.py LOCATION_DEFINITIONS
    # 14 локаций: cordon, garbage, agroprom, dark_valley, bar, wild_territory, yantar,
    # army_warehouses, red_forest, pripyat, jupiter, zaton, skadovsk, sarcophagus
}

# Логирование
LOGGING_CONFIG = {
    "level": "DEBUG",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "log_file": "game.log",
    "enable_file": True,
    "enable_console": True,
    "enable_colors": True,
    "log_categories": ["GENERAL", "RENDER", "PHYSICS", "WORLD", "LOCATION", "MENU", "ENTITY", "ANOMALY"],
}
