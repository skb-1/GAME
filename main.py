"""
Главная точка входа — полноценная 3D-игра Minecraft + DayZ + S.T.A.L.K.E.R.
с ПОЛИГОНАЛЬНОЙ геометрией и полностью процедурной генерацией.

Версия 0.2.0 — с интерактивным меню, системой локаций и подробным логированием.

Стек:
- Panda3D 1.10.14 — рендер, GeomVertexData для процедурных мешей, LOD, culling
- PyBullet 3.2.5+ / Pymunk 6.x / Pure Python stub — физика с фолбэками
- Numpy 1.24.4, Numba 0.57.1, Scipy 1.11.4
- Python 3.10.0

Архитектура:
- GameStates: MENU, LOADING, PLAYING, PAUSED, SETTINGS, LOCATION_MAP, LOCATION_TRANSITION
- LocationSystem: разделение карты на 14 локаций с переходами, только активная загружена -> CPU x5-10 меньше
- Подробное логирование: utils/logger.py с категориями и цветами в терминале + game.log файл
"""
import sys
import os
import argparse
import time
import math
import threading
import gc
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------- Логирование — инициализируем первым ----------
from utils.logger import init_logger, get_logger, LogCategory, LogLevel

logger = init_logger(log_file="game.log", level=LogLevel.DEBUG)
logger.info(LogCategory.GENERAL, "=== STALKERcraft v0.2.0 Запуск ===")
logger.info(LogCategory.GENERAL, f"Python {sys.version}")
logger.info(LogCategory.GENERAL, f"Аргументы: {sys.argv}")

# ---------- Конфиги ----------
try:
    from config import WORLD_CONFIG, RENDER_CONFIG, OPTIMIZATION_CONFIG, TIME_CONFIG
    logger.info(LogCategory.GENERAL, "Конфиги загружены")
except Exception as e:
    logger.critical(LogCategory.GENERAL, f"Ошибка загрузки конфигов: {e}")
    raise

# ---------- Импорты игровых систем ----------
from world.chunk_system import ChunkSystem
from world.time_cycle import TimeCycle
from world.weather import WeatherSystem
from world.terraforming import TerraformingSystem
from world.location_system import LocationSystem, LOCATION_DEFINITIONS
from physics.physics_engine import PhysicsEngine
from entities.player import Player
from spawn.spawn_manager import SpawnManager
from anomalies.anomaly_system import AnomalySystem
from anomalies.artifact_system import ArtifactSystem
from radiation.radiation_map import RadiationMap
from radiation.geiger import GeigerCounter
from save.save_manager import SaveManager
from ui.console import GameConsole
from ui.hud import HUD
from utils.optimization import GCTuner, ProfilerOverlay, FrustumCuller
from utils.asset_cache import global_cache

# Panda3D
try:
    from direct.showbase.ShowBase import ShowBase
    from panda3d.core import (
        GeomVertexFormat, GeomVertexData, GeomVertexWriter,
        GeomTriangles, Geom, GeomNode, NodePath,
        LVector3, LVector2, Texture, Shader, AmbientLight, DirectionalLight,
        PointLight, Fog, LColor, loadPrcFileData
    )
    HAS_PANDA3D = True
    logger.info(LogCategory.RENDER, "Panda3D импортирован успешно")
except ImportError as e:
    HAS_PANDA3D = False
    logger.warning(LogCategory.RENDER, f"Panda3D не установлен ({e}), headless режим")

import numpy as np

class GameState(Enum):
    MENU = "menu"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    SETTINGS = "settings"
    LOCATION_MAP = "location_map"
    LOCATION_TRANSITION = "location_transition"

class Game:
    def __init__(self, world_seed=1337, headless=False, start_location="cordon"):
        self.world_seed = world_seed
        self.headless = headless or not HAS_PANDA3D
        self.start_location = start_location
        self.running = True
        self.state = GameState.MENU if not self.headless else GameState.PLAYING

        logger.info(LogCategory.GENERAL, f"Инициализация Game, seed={world_seed}, headless={self.headless}, start_location={start_location}")
        logger.info(LogCategory.OPTIMIZATION, f"Конфиг оптимизации: {OPTIMIZATION_CONFIG}")

        # Системы
        logger.info(LogCategory.WORLD, "Создание мировых систем...")
        self.location_system = LocationSystem(world_seed=world_seed, chunk_size=WORLD_CONFIG["chunk_size"])
        logger.info(LogCategory.LOCATION, f"LocationSystem: {len(self.location_system.locations)} локаций")

        self.time_cycle = TimeCycle(start_hour=TIME_CONFIG["start_hour"], day_length_minutes=TIME_CONFIG["day_length_minutes"])
        logger.info(LogCategory.WORLD, f"TimeCycle: start {TIME_CONFIG['start_hour']}h, day_length {TIME_CONFIG['day_length_minutes']}m")

        self.weather = WeatherSystem(seed=world_seed)
        logger.info(LogCategory.WORLD, "WeatherSystem создан")

        self.physics = PhysicsEngine()
        logger.info(LogCategory.PHYSICS, f"Physics backend: {self.physics.get_backend_name()}")

        self.radiation_map = None
        self.geiger = GeigerCounter(seed=world_seed)
        self.save_manager = SaveManager()
        self.hud = HUD()
        self.console = GameConsole(self)
        self.gc_tuner = GCTuner(collect_interval=OPTIMIZATION_CONFIG["gc_collect_interval"])
        self.profiler = ProfilerOverlay()
        self.frustum_culler = FrustumCuller(fov=RENDER_CONFIG["fov"], aspect=16/9, near=RENDER_CONFIG["near_clip"], far=RENDER_CONFIG["far_clip"])

        # Игрок
        self.player = Player(seed=world_seed, start_pos=np.array([0, 20, 0], dtype=np.float32))
        logger.info(LogCategory.ENTITY, f"Игрок создан, seed={world_seed}, pos={self.player.state.position}")

        # Локационные системы — будут из активной локации
        self.chunk_system = None
        self.spawn_manager = None
        self.anomaly_system = None
        self.artifact_system = None
        self.terraforming = None

        # Состояние
        self.god_mode = False
        self.noclip = False
        self.last_day = 0
        self.keys = {"w": False, "a": False, "s": False, "d": False, "shift": False, "ctrl": False, "space": False}
        self.mouse_sensitivity = 0.2

        # Panda3D
        self.showbase = None
        self.menus = {}

        if not self.headless:
            try:
                logger.info(LogCategory.RENDER, "Инициализация Panda3D...")
                self.init_panda3d()
                logger.info(LogCategory.RENDER, "Panda3D инициализирован")
            except Exception as e:
                logger.error(LogCategory.RENDER, f"Panda3D init failed: {e}, переключаюсь в headless")
                import traceback
                logger.error(LogCategory.RENDER, traceback.format_exc())
                self.headless = True
                self.state = GameState.PLAYING

        # Если headless — сразу загружаем стартовую локацию
        if self.headless:
            logger.info(LogCategory.LOCATION, f"Headless: загрузка стартовой локации {self.start_location}")
            self.load_location(self.start_location)
        else:
            # В графическом режиме — показываем меню, локация загрузится при новой игре
            logger.info(LogCategory.MENU, "Графический режим, показываем главное меню")
            self.show_main_menu()

        logger.info(LogCategory.GENERAL, "Инициализация Game завершена")

    def init_panda3d(self):
        """Инициализация Panda3D окна и меню."""
        logger.info(LogCategory.RENDER, f"Настройка Panda3D: {RENDER_CONFIG['window_width']}x{RENDER_CONFIG['window_height']}, title={RENDER_CONFIG}")

        loadPrcFileData("", f"win-size {RENDER_CONFIG['window_width']} {RENDER_CONFIG['window_height']}")
        loadPrcFileData("", "window-title STALKERcraft - Procedural 3D Survival | Seed {0}".format(self.world_seed))
        loadPrcFileData("", f"framebuffer-multisample 0")
        loadPrcFileData("", "textures-auto-compress #t")
        loadPrcFileData("", "compressed-textures 1")
        loadPrcFileData("", "show-frame-rate-meter #f")

        self.showbase = ShowBase()
        self.showbase.setBackgroundColor(0.05, 0.05, 0.08)

        # Свет
        logger.debug(LogCategory.RENDER, "Создание освещения")
        ambient = AmbientLight("ambient")
        ambient.setColor((0.4, 0.4, 0.45, 1))
        self.showbase.render.setLight(self.showbase.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor((0.9, 0.9, 0.8, 1))
        sun_np = self.showbase.render.attachNewNode(sun)
        sun_np.setHpr(45, -45, 0)
        self.showbase.render.setLight(sun_np)

        # Туман
        if RENDER_CONFIG["enable_fog"]:
            fog = Fog("fog")
            fog.setColor(0.6, 0.7, 0.8)
            fog.setExpDensity(0.001)
            self.showbase.render.setFog(fog)
            logger.debug(LogCategory.RENDER, "Туман включён")

        # Камера
        self.showbase.disableMouse()
        self.showbase.camera.setPos(0, -10, 5)
        logger.debug(LogCategory.RENDER, "Камера настроена")

        # Задачи
        self.showbase.taskMgr.add(self.panda3d_update_task, "game_update")
        logger.debug(LogCategory.GENERAL, "Задача обновления добавлена")

        # Инпуты
        self.showbase.accept("w", self.set_key, ["w", True])
        self.showbase.accept("w-up", self.set_key, ["w", False])
        self.showbase.accept("a", self.set_key, ["a", True])
        self.showbase.accept("a-up", self.set_key, ["a", False])
        self.showbase.accept("s", self.set_key, ["s", True])
        self.showbase.accept("s-up", self.set_key, ["s", False])
        self.showbase.accept("d", self.set_key, ["d", True])
        self.showbase.accept("d-up", self.set_key, ["d", False])
        self.showbase.accept("shift", self.set_key, ["shift", True])
        self.showbase.accept("shift-up", self.set_key, ["shift", False])
        self.showbase.accept("control", self.set_key, ["ctrl", True])
        self.showbase.accept("control-up", self.set_key, ["ctrl", False])
        self.showbase.accept("space", self.set_key, ["space", True])
        self.showbase.accept("space-up", self.set_key, ["space", False])
        self.showbase.accept("f3", self.on_f3)
        self.showbase.accept("f5", self.quick_save)
        self.showbase.accept("f8", self.on_f8)
        self.showbase.accept("escape", self.on_escape)
        self.showbase.accept("mouse1", self.on_left_click)
        self.showbase.accept("mouse3", self.on_right_click)

        # Мышь — захват
        self.showbase.accept("m", self.toggle_mouse_lock)
        self.mouse_locked = False

        # Меню
        self.init_menus()

        logger.info(LogCategory.RENDER, "Panda3D окно создано, pipe types: wglGraphicsPipe")

    def init_menus(self):
        """Инициализация всех меню."""
        logger.info(LogCategory.MENU, "Инициализация меню...")

        from ui.menu import MainMenu, SettingsMenu, PauseMenu, LocationMapMenu, LoadingScreen

        # Главное меню
        self.menus['main'] = MainMenu(
            self,
            on_new_game=self.on_new_game,
            on_load_game=self.on_load_game,
            on_settings=self.on_settings_from_main,
            on_exit=self.on_exit
        )

        # Настройки
        self.menus['settings'] = SettingsMenu(
            self,
            on_back=self.on_settings_back
        )

        # Пауза
        self.menus['pause'] = PauseMenu(
            self,
            on_resume=self.on_resume,
            on_save=self.quick_save,
            on_load=self.on_load_game,
            on_settings=self.on_settings_from_pause,
            on_exit_to_menu=self.on_exit_to_menu
        )

        # Карта локаций
        self.menus['location_map'] = LocationMapMenu(
            self,
            location_system=self.location_system,
            on_select_location=self.on_location_map_select,
            on_back=self.on_location_map_back
        )

        # Загрузка
        self.menus['loading'] = LoadingScreen(self)

        logger.info(LogCategory.MENU, f"Меню инициализированы: {list(self.menus.keys())}")

    def show_main_menu(self):
        logger.info(LogCategory.MENU, "Показ главного меню")
        self.state = GameState.MENU
        self.hide_all_menus()
        if 'main' in self.menus:
            self.menus['main'].show()
        # Разблокируем мышь для меню
        self.unlock_mouse()
        if self.showbase:
            self.showbase.setBackgroundColor(0.05, 0.05, 0.1)

    def show_pause_menu(self):
        logger.info(LogCategory.MENU, "Показ меню паузы")
        self.state = GameState.PAUSED
        self.hide_all_menus()
        if 'pause' in self.menus:
            self.menus['pause'].show()
        self.unlock_mouse()

    def show_settings_menu(self, from_state=GameState.MENU):
        logger.info(LogCategory.MENU, f"Показ настроек, from={from_state}")
        self._settings_return_state = from_state
        self.state = GameState.SETTINGS
        self.hide_all_menus()
        if 'settings' in self.menus:
            self.menus['settings'].show()
        self.unlock_mouse()

    def show_location_map(self):
        logger.info(LogCategory.MENU, "Показ карты Зоны")
        self.state = GameState.LOCATION_MAP
        self.hide_all_menus()
        if 'location_map' in self.menus:
            self.menus['location_map'].show()
        self.unlock_mouse()

    def show_loading_screen(self, text="Загрузка...", percent=0):
        logger.debug(LogCategory.MENU, f"Экран загрузки: {text} {percent}%")
        if self.state != GameState.LOADING:
            self.state = GameState.LOADING
            self.hide_all_menus()
            if 'loading' in self.menus:
                self.menus['loading'].show()
        if 'loading' in self.menus and hasattr(self.menus['loading'], 'update_progress'):
            self.menus['loading'].update_progress(percent, text)

    def hide_all_menus(self):
        for menu in self.menus.values():
            if hasattr(menu, 'hide'):
                menu.hide()

    def lock_mouse(self):
        if not self.showbase:
            return
        try:
            self.showbase.win.movePointer(0, self.showbase.win.getXSize()//2, self.showbase.win.getYSize()//2)
            # Скрываем курсор
            props = self.showbase.win.getProperties()
            self.showbase.win.requestProperties(props)
            self.mouse_locked = True
            logger.debug(LogCategory.UI, "Мышь заблокирована")
        except Exception as e:
            logger.warning(LogCategory.UI, f"Не удалось заблокировать мышь: {e}")

    def unlock_mouse(self):
        self.mouse_locked = False
        logger.debug(LogCategory.UI, "Мышь разблокирована")

    def toggle_mouse_lock(self):
        if self.mouse_locked:
            self.unlock_mouse()
        else:
            self.lock_mouse()

    # ---------- Обработчики меню ----------

    def on_new_game(self, seed, location_id="cordon"):
        logger.info(LogCategory.MENU, f"Новая игра: seed={seed}, location={location_id}")
        self.world_seed = seed
        self.player = Player(seed=seed, start_pos=np.array([0, 20, 0], dtype=np.float32))
        self.show_loading_screen("Инициализация мира...", 10)

        # Загрузка локации в фоне
        def load_thread():
            try:
                logger.info(LogCategory.LOCATION, f"Поток загрузки локации {location_id}")
                self.load_location(location_id)
                logger.info(LogCategory.LOCATION, f"Локация {location_id} загружена, переход в PLAYING")
                # Переключаем состояние в главном потоке через task
                if self.showbase:
                    self.showbase.taskMgr.doMethodLater(0.1, lambda task: self.start_gameplay(), "start_gameplay")
                else:
                    self.start_gameplay()
            except Exception as e:
                logger.error(LogCategory.LOCATION, f"Ошибка загрузки локации {location_id}: {e}")
                import traceback
                logger.error(LogCategory.LOCATION, traceback.format_exc())

        threading.Thread(target=load_thread, daemon=True, name="LocationLoader").start()

    def load_location(self, location_id):
        """Загрузка локации с логированием."""
        logger.info(LogCategory.LOCATION, f"load_location({location_id}) вызван")
        self.show_loading_screen(f"Загрузка {location_id}...", 20)

        loc = self.location_system.set_active_location(location_id)
        if not loc:
            logger.error(LogCategory.LOCATION, f"Не удалось загрузить локацию {location_id}")
            return None

        self.show_loading_screen(f"Инициализация {loc.definition.display_name}...", 50)

        # Берём системы из локации
        self.chunk_system = loc.chunk_system
        self.spawn_manager = loc.spawn_manager
        self.anomaly_system = loc.anomaly_system
        self.artifact_system = loc.artifact_system
        self.radiation_map = loc.radiation_map
        self.terraforming = TerraformingSystem(self.chunk_system)

        self.show_loading_screen(f"Генерация мешей {loc.definition.display_name}...", 80)

        # Ждём загрузки чанков
        if self.chunk_system:
            self.chunk_system.request_chunk(0, 0)
            time.sleep(0.3)
            self.chunk_system.update(0, 0)
            logger.info(LogCategory.TERRAIN, f"Чанки загружены: {len(self.chunk_system.chunks)}")

        self.show_loading_screen(f"{loc.definition.display_name} готов!", 100)
        time.sleep(0.2)

        return loc

    def start_gameplay(self):
        """Начало геймплея после загрузки."""
        logger.info(LogCategory.GENERAL, "start_gameplay()")
        self.hide_all_menus()
        self.state = GameState.PLAYING
        self.lock_mouse()
        if self.showbase:
            self.showbase.setBackgroundColor(0.5, 0.7, 1.0)
        logger.info(LogCategory.GENERAL, f"Игра началась, локация={self.location_system.active_location_id}")

    def on_load_game(self):
        logger.info(LogCategory.MENU, "Загрузка игры")
        saves = self.save_manager.list_saves()
        if not saves:
            logger.warning(LogCategory.SAVE, "Нет сохранений")
            return

        # Загружаем последнее
        latest = saves[0]
        logger.info(LogCategory.SAVE, f"Загрузка {latest['name']}")
        data = self.save_manager.load_game(latest['name'])
        if data:
            self.load_save_data(data)
            self.start_gameplay()
        else:
            logger.error(LogCategory.SAVE, f"Не удалось загрузить {latest['name']}")

    def on_settings_from_main(self):
        self.show_settings_menu(from_state=GameState.MENU)

    def on_settings_from_pause(self):
        self.show_settings_menu(from_state=GameState.PAUSED)

    def on_settings_back(self):
        logger.info(LogCategory.MENU, "Назад из настроек")
        return_state = getattr(self, '_settings_return_state', GameState.MENU)
        if return_state == GameState.PAUSED:
            self.show_pause_menu()
        else:
            self.show_main_menu()

    def on_resume(self):
        logger.info(LogCategory.MENU, "Продолжить игру")
        self.hide_all_menus()
        self.state = GameState.PLAYING
        self.lock_mouse()

    def on_exit_to_menu(self):
        logger.info(LogCategory.MENU, "Выход в главное меню")
        # Сохраняем текущую локацию
        self.quick_save()
        self.show_main_menu()

    def on_location_map_select(self, loc_id):
        logger.info(LogCategory.LOCATION, f"Выбрана локация на карте: {loc_id}")
        # Телепорт (читерство) или обычный переход
        # Проверяем связь
        active = self.location_system.get_active_location()
        if active and loc_id not in active.definition.connections:
            logger.warning(LogCategory.LOCATION, f"Локация {loc_id} не связана с {active.definition.location_id}, телепорт читерский")
        # Загружаем
        self.menus['location_map'].hide()
        self.on_new_game(self.world_seed, loc_id)

    def on_location_map_back(self):
        logger.info(LogCategory.MENU, "Назад с карты")
        if self.state == GameState.PLAYING or self.location_system.active_location_id:
            self.show_pause_menu()
        else:
            self.show_main_menu()

    def on_exit(self):
        logger.info(LogCategory.GENERAL, "Выход из игры")
        self.shutdown()
        sys.exit(0)

    # ---------- Инпуты ----------

    def set_key(self, key, value):
        self.keys[key] = value
        logger.debug(LogCategory.UI, f"Key {key}={value}, state={self.state}")

    def on_f3(self):
        logger.info(LogCategory.UI, "F3 нажат")
        self.hud.toggle_debug()
        # Выводим подробный лог в терминал
        logger.info(LogCategory.OPTIMIZATION, f"Profiler: {self.profiler.get_text()}")
        if self.chunk_system:
            logger.info(LogCategory.TERRAIN, f"Чанки: {len(self.chunk_system.chunks)}")
        if self.spawn_manager:
            logger.info(LogCategory.SPAWN, f"Животные: {len(self.spawn_manager.animals)}")
        logger.info(LogCategory.OPTIMIZATION, f"MeshCache: {global_cache.stats()}")

    def on_f8(self):
        logger.info(LogCategory.UI, "F8 консоль")
        self.console.toggle()
        if self.console.is_open:
            self.unlock_mouse()
        else:
            if self.state == GameState.PLAYING:
                self.lock_mouse()

    def on_escape(self):
        logger.info(LogCategory.UI, f"Escape, state={self.state}")
        if self.state == GameState.PLAYING:
            self.show_pause_menu()
        elif self.state == GameState.PAUSED:
            self.on_resume()
        elif self.state == GameState.SETTINGS:
            self.on_settings_back()
        elif self.state == GameState.LOCATION_MAP:
            self.on_location_map_back()
        elif self.state == GameState.MENU:
            # В главном меню Esc = выход?
            pass

    def on_left_click(self):
        logger.debug(LogCategory.UI, f"ЛКМ, state={self.state}")
        if self.state != GameState.PLAYING:
            return
        cam_pos = self.player.get_camera_pos()
        cam_dir = self.player.get_camera_dir()
        hit = self.physics.raycast(cam_pos, cam_pos + cam_dir*10)
        if hit["hit"]:
            pos = hit["position"]
            logger.info(LogCategory.TERRAIN, f"Копание в {pos}")
            if self.terraforming:
                self.terraforming.dig(pos[0], pos[2], radius=2.0, depth=1.0)

    def on_right_click(self):
        logger.debug(LogCategory.UI, f"ПКМ, state={self.state}")
        if self.state != GameState.PLAYING:
            return
        cam_pos = self.player.get_camera_pos()
        cam_dir = self.player.get_camera_dir()
        hit = self.physics.raycast(cam_pos, cam_pos + cam_dir*10)
        if hit["hit"]:
            pos = hit["position"]
            logger.info(LogCategory.TERRAIN, f"Строительство в {pos}")
            if self.terraforming:
                self.terraforming.build(pos[0], pos[2], radius=2.0, height=1.0)

    def quick_save(self):
        logger.info(LogCategory.SAVE, "Quicksave...")
        data = self.get_save_data()
        self.save_manager.save_game("quicksave", data)
        logger.info(LogCategory.SAVE, "Quicksave done")

    # ---------- Игровой цикл ----------

    def panda3d_update_task(self, task):
        dt = globalClock.getDt()
        dt = min(dt, 1/30.0)  # clamp

        if self.state == GameState.PLAYING:
            self.update(dt)
            # Камера
            cam_pos = self.player.get_camera_pos()
            cam_dir = self.player.get_camera_dir()
            self.showbase.camera.setPos(cam_pos[0], cam_pos[1], cam_pos[2])
            target = cam_pos + cam_dir*10
            self.showbase.camera.lookAt(target[0], target[1], target[2])

            # Проверка переходов между локациями
            transition = self.location_system.check_transitions(self.player.state.position)
            if transition:
                target_id, trans_obj = transition
                logger.info(LogCategory.LOCATION, f"Переход обнаружен: {self.location_system.active_location_id} -> {target_id}")
                self.start_location_transition(target_id)

            # Обновление видимых чанков (заглушка для рендера мешей)
            if self.chunk_system:
                visible = self.chunk_system.get_visible_chunks(cam_pos, self.frustum_culler)
                # В реальном — создание GeomNode для каждого чанка, здесь лог
                if task.frame % 300 == 0:  # каждые 5 сек при 60 FPS
                    logger.debug(LogCategory.TERRAIN, f"Видимых чанков: {len(visible)}")

        return task.cont

    def start_location_transition(self, target_location_id):
        """Начало перехода между локациями."""
        if self.state == GameState.LOCATION_TRANSITION:
            return

        logger.info(LogCategory.LOCATION, f"Начало перехода в {target_location_id}")
        self.state = GameState.LOCATION_TRANSITION
        self.show_loading_screen(f"Переход в {LOCATION_DEFINITIONS[target_location_id].display_name}...", 0)

        def transition_thread():
            try:
                # Сохраняем текущую
                self.quick_save()
                # Загружаем новую
                self.load_location(target_location_id)
                # Телепортируем игрока к центру новой локации
                self.player.state.position = np.array([0, 20, 0], dtype=np.float32)
                logger.info(LogCategory.LOCATION, f"Переход завершён, игрок в {target_location_id}")

                if self.showbase:
                    self.showbase.taskMgr.doMethodLater(0.1, lambda task: self.finish_location_transition(), "finish_transition")
                else:
                    self.finish_location_transition()
            except Exception as e:
                logger.error(LogCategory.LOCATION, f"Ошибка перехода: {e}")
                import traceback
                logger.error(LogCategory.LOCATION, traceback.format_exc())

        threading.Thread(target=transition_thread, daemon=True, name="TransitionLoader").start()

    def finish_location_transition(self):
        logger.info(LogCategory.LOCATION, "finish_location_transition()")
        self.hide_all_menus()
        self.state = GameState.PLAYING
        self.lock_mouse()

    def update(self, dt):
        # GC tuning
        self.gc_tuner.disable_in_frame()

        # Время
        new_day = self.time_cycle.update(dt)
        if new_day:
            logger.info(LogCategory.WORLD, f"Новый день {self.time_cycle.day_count}, время {self.time_cycle.get_time_string()}")
            if self.anomaly_system:
                self.anomaly_system.respawn_daily(self.chunk_system, self.time_cycle.day_count)
            if self.artifact_system:
                self.artifact_system.respawn_daily(self.anomaly_system, self.chunk_system)
            self.save_manager.autosave(self.get_save_data())
            logger.info(LogCategory.SAVE, "Автосейв выполнен")

        self.weather.update(dt)
        if self.weather.time_in_weather < dt*1.1:  # смена погоды
            logger.info(LogCategory.WORLD, f"Погода сменилась на {self.weather.current_weather}")

        # Игрок
        forward = 0
        right = 0
        if self.keys.get("w"):
            forward += 1
        if self.keys.get("s"):
            forward -= 1
        if self.keys.get("a"):
            right -= 1
        if self.keys.get("d"):
            right += 1
        is_running = self.keys.get("shift", False)
        is_crouching = self.keys.get("ctrl", False)

        self.player.move(forward, right, dt, is_running=is_running, is_crouching=is_crouching)
        self.player.update(dt)

        # Физика
        self.physics.step(dt)

        # Чанки активной локации
        if self.chunk_system:
            player_chunk_x = int(self.player.state.position[0] // self.chunk_system.chunk_size)
            player_chunk_z = int(self.player.state.position[2] // self.chunk_system.chunk_size)
            self.chunk_system.update(player_chunk_x, player_chunk_z)

            # Высота игрока по террейну
            if not self.noclip:
                terrain_h = self.chunk_system.get_height_at(self.player.state.position[0], self.player.state.position[2])
                if self.player.state.position[1] < terrain_h + 1.8:
                    self.player.state.position[1] = terrain_h + 1.8
                    self.player.state.velocity[1] = 0

        # Радиация
        if self.radiation_map:
            rad_level = self.radiation_map.get_radiation_at_3d(self.player.state.position)
        else:
            rad_level = 0.05

        anom_rad = 0
        art_rad = 0
        if self.anomaly_system:
            _, anom_rad = self.anomaly_system.update(dt, self.player.state.position)
        if self.artifact_system:
            art_rad = self.artifact_system.update(dt, self.player.state.position)

        total_rad = rad_level + anom_rad + art_rad
        self.player.needs.add_radiation(total_rad*dt*0.01)

        if total_rad > 1.0:
            logger.debug(LogCategory.RADIATION, f"Радиация {total_rad:.2f} uSv/h, накоплено {self.player.needs.radiation:.1f} mSv")

        # Гейгер
        clicks = self.geiger.update(total_rad, dt)
        if clicks > 0:
            logger.debug(LogCategory.RADIATION, f"Гейгер клики: {clicks}, rate {self.geiger.click_rate:.1f}/s")

        # Животные
        if self.spawn_manager:
            self.spawn_manager.update(dt, player_pos=self.player.state.position, chunk_system=self.chunk_system)

        # Аномалии урон
        if self.anomaly_system:
            anom_damage, _ = self.anomaly_system.update(dt, self.player.state.position)
            if anom_damage > 0 and not self.god_mode:
                logger.warning(LogCategory.ANOMALY, f"Урон от аномалии: {anom_damage:.1f}")
                self.player.take_damage(anom_damage*dt, zone="torso")

        # Frustum culler
        self.frustum_culler.update_from_camera(self.player.get_camera_pos(), self.player.get_camera_dir(), (0,1,0))

        # Профайлер
        chunk_count = len(self.chunk_system.chunks) if self.chunk_system else 0
        entity_count = len(self.spawn_manager.animals) if self.spawn_manager else 0
        self.profiler.update(fps=1.0/dt if dt>0 else 0, chunk_count=chunk_count, entity_count=entity_count, mesh_cache_count=global_cache.stats()["memory_items"])

        self.gc_tuner.enable_after_frame()

    def get_save_data(self):
        data = {
            "world_seed": self.world_seed,
            "player": self.player.to_save_dict(),
            "time": {"hours": self.time_cycle.time_hours, "day": self.time_cycle.day_count},
            "weather": {"current": self.weather.current_weather},
            "timestamp": time.time(),
            "location_system": self.location_system.to_save_dict(),
        }
        if self.anomaly_system:
            data["anomalies"] = self.anomaly_system.to_dict()
        if self.artifact_system:
            data["artifacts"] = self.artifact_system.to_dict()
        if self.spawn_manager:
            data["animals"] = self.spawn_manager.to_dict()
        if self.radiation_map:
            data["radiation"] = self.radiation_map.to_dict()

        logger.debug(LogCategory.SAVE, f"Собраны данные сохранения, размер ~{len(str(data))} символов")
        return data

    def load_save_data(self, data):
        logger.info(LogCategory.SAVE, f"Загрузка сохранения, seed={data.get('world_seed')}")
        self.world_seed = data.get("world_seed", self.world_seed)
        if "player" in data:
            self.player.from_save_dict(data["player"])
            logger.info(LogCategory.ENTITY, f"Игрок загружен, pos={self.player.state.position}")
        if "time" in data:
            self.time_cycle.time_hours = data["time"]["hours"]
            self.time_cycle.day_count = data["time"]["day"]
            logger.info(LogCategory.WORLD, f"Время загружено: {self.time_cycle.get_time_string()}")
        if "location_system" in data:
            self.location_system.from_save_dict(data["location_system"])
            active_loc = data["location_system"].get("active_location")
            if active_loc:
                logger.info(LogCategory.LOCATION, f"Загрузка активной локации {active_loc}")
                self.load_location(active_loc)

        # Остальные системы загрузятся вместе с локацией, но если есть в сохранении — перезапишем
        if "anomalies" in data and self.anomaly_system:
            self.anomaly_system.from_dict(data["anomalies"])
        if "artifacts" in data and self.artifact_system:
            self.artifact_system.from_dict(data["artifacts"])
        if "animals" in data and self.spawn_manager:
            self.spawn_manager.from_dict(data["animals"])
        if "radiation" in data and self.radiation_map:
            self.radiation_map.from_dict(data["radiation"])

    def run_headless(self, duration=10.0):
        logger.info(LogCategory.GENERAL, f"Headless run {duration}s")
        start = time.time()
        last = start
        while time.time() - start < duration and self.running:
            now = time.time()
            dt = now - last
            last = now
            dt = min(dt, 1/30.0)
            self.update(dt)
            time.sleep(1/60.0)
            if int(time.time() - start) % 2 == 0:
                logger.info(LogCategory.GENERAL, self.hud.update(self.player, self.time_cycle, self.weather, self.geiger, self.anomaly_system, self.profiler))
        logger.info(LogCategory.GENERAL, "Headless finished")
        self.shutdown()

    def shutdown(self):
        logger.info(LogCategory.GENERAL, "Shutdown начат")
        if self.chunk_system:
            self.chunk_system.stop_workers()
        # Выгружаем все локации
        for loc_id in list(self.location_system.locations.keys()):
            if self.location_system.locations[loc_id].is_loaded:
                self.location_system.unload_location(loc_id)
        self.physics.shutdown()
        logger.info(LogCategory.GENERAL, "Shutdown завершён")
        get_logger().shutdown()

def main():
    parser = argparse.ArgumentParser(description="STALKERcraft - Procedural Survival v0.2.0")
    parser.add_argument("--seed", type=int, default=1337, help="World seed")
    parser.add_argument("--no-render", action="store_true", help="Headless mode without Panda3D window")
    parser.add_argument("--duration", type=float, default=0, help="Headless duration seconds (0 = infinite with render)")
    parser.add_argument("--location", type=str, default="cordon", help="Start location id (cordon, garbage, bar, etc)")
    parser.add_argument("--log-level", type=str, default="DEBUG", help="Log level DEBUG/INFO/WARNING/ERROR")
    args = parser.parse_args()

    # Устанавливаем уровень лога
    try:
        lvl = LogLevel[args.log_level.upper()]
        get_logger().level = lvl
        logger.info(LogCategory.GENERAL, f"Уровень лога установлен: {lvl.name}")
    except:
        pass

    logger.info(LogCategory.GENERAL, f"Запуск main(), seed={args.seed}, location={args.location}, no-render={args.no_render}")

    game = Game(world_seed=args.seed, headless=args.no_render, start_location=args.location)

    if args.no_render or not HAS_PANDA3D:
        dur = args.duration if args.duration>0 else 10.0
        logger.info(LogCategory.GENERAL, f"Headless режим, duration={dur}")
        game.run_headless(duration=dur)
    else:
        logger.info(LogCategory.GENERAL, "Графический режим, запуск ShowBase.run()")
        try:
            game.showbase.run()
        except KeyboardInterrupt:
            logger.warning(LogCategory.GENERAL, "KeyboardInterrupt")
            game.shutdown()
        except Exception as e:
            logger.critical(LogCategory.GENERAL, f"Критическая ошибка в main loop: {e}")
            import traceback
            logger.critical(LogCategory.GENERAL, traceback.format_exc())
            game.shutdown()

if __name__ == "__main__":
    main()
