"""
STALKERcraft v0.2.1 — Procedural 3D Survival with working rendering and menu

Fixes:
- DirectGUI English only to avoid Cyrillic font warnings
- Actual terrain rendering via GeomNode
- Mouse look
- Location system with transitions
- Detailed logging
- 3 physics backends fallback

Run: python main.py --seed 1337 --location cordon --log-level INFO
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

from utils.logger import init_logger, get_logger, LogCategory, LogLevel
logger = init_logger(log_file="game.log", level=LogLevel.DEBUG)
logger.info(LogCategory.GENERAL, "=== STALKERcraft v0.2.1 Starting ===")
logger.info(LogCategory.GENERAL, f"Python {sys.version}")

from config import WORLD_CONFIG, RENDER_CONFIG, OPTIMIZATION_CONFIG, TIME_CONFIG, LOCATION_CONFIG
from world.location_system import LocationSystem, LOCATION_DEFINITIONS
from world.time_cycle import TimeCycle
from world.weather import WeatherSystem
from world.terraforming import TerraformingSystem
from physics.physics_engine import PhysicsEngine
from entities.player import Player
from save.save_manager import SaveManager
from ui.console import GameConsole
from ui.hud import HUD
from utils.optimization import GCTuner, ProfilerOverlay, FrustumCuller
from utils.asset_cache import global_cache
from utils.procedural_mesh import MeshData

try:
    from direct.showbase.ShowBase import ShowBase
    from panda3d.core import (
        GeomVertexFormat, GeomVertexData, GeomVertexWriter,
        GeomTriangles, Geom, GeomNode, NodePath,
        LVector3, LVector2, Texture, Shader, AmbientLight, DirectionalLight,
        PointLight, Fog, LColor, loadPrcFileData, LineSegs, TransparencyAttrib
    )
    HAS_PANDA3D = True
    logger.info(LogCategory.RENDER, "Panda3D imported")
except ImportError as e:
    HAS_PANDA3D = False
    logger.warning(LogCategory.RENDER, f"Panda3D not installed: {e}")

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

        logger.info(LogCategory.GENERAL, f"Game init seed={world_seed} headless={self.headless} start_loc={start_location}")

        self.location_system = LocationSystem(world_seed=world_seed, chunk_size=WORLD_CONFIG["chunk_size"])
        self.time_cycle = TimeCycle(start_hour=TIME_CONFIG["start_hour"], day_length_minutes=TIME_CONFIG["day_length_minutes"])
        self.weather = WeatherSystem(seed=world_seed)
        self.physics = PhysicsEngine()
        logger.info(LogCategory.PHYSICS, f"Physics backend: {self.physics.get_backend_name()}")

        from radiation.geiger import GeigerCounter
        from radiation.radiation_map import RadiationMap
        from anomalies.anomaly_system import AnomalySystem
        from anomalies.artifact_system import ArtifactSystem
        from spawn.spawn_manager import SpawnManager

        self.geiger = GeigerCounter(seed=world_seed)
        self.save_manager = SaveManager()
        self.hud = HUD()
        self.console = GameConsole(self)
        self.gc_tuner = GCTuner(collect_interval=OPTIMIZATION_CONFIG["gc_collect_interval"])
        self.profiler = ProfilerOverlay()
        self.frustum_culler = FrustumCuller(fov=RENDER_CONFIG["fov"], aspect=16/9, near=RENDER_CONFIG["near_clip"], far=RENDER_CONFIG["far_clip"])

        self.player = Player(seed=world_seed, start_pos=np.array([0, 30, 0], dtype=np.float32))

        self.chunk_system = None
        self.spawn_manager = None
        self.anomaly_system = None
        self.artifact_system = None
        self.radiation_map = None
        self.terraforming = None

        self.god_mode = False
        self.noclip = False
        self.keys = {"w": False, "a": False, "s": False, "d": False, "shift": False, "ctrl": False, "space": False}
        self.mouse_sensitivity = 0.15

        self.showbase = None
        self.menus = {}
        self.chunk_nodes = {}  # chunk_key -> NodePath
        self.entity_nodes = {}  # entity_id -> NodePath
        self.anomaly_nodes = {}
        self.transition_nodes = {}

        if not self.headless:
            try:
                self.init_panda3d()
            except Exception as e:
                logger.error(LogCategory.RENDER, f"Panda3D init failed: {e}")
                import traceback
                logger.error(LogCategory.RENDER, traceback.format_exc())
                self.headless = True
                self.state = GameState.PLAYING

        if self.headless:
            logger.info(LogCategory.LOCATION, f"Headless loading {self.start_location}")
            self.load_location(self.start_location)
        else:
            self.show_main_menu()

        logger.info(LogCategory.GENERAL, "Game init complete")

    def init_panda3d(self):
        logger.info(LogCategory.RENDER, f"Panda3D setup {RENDER_CONFIG['window_width']}x{RENDER_CONFIG['window_height']}")

        loadPrcFileData("", f"win-size {RENDER_CONFIG['window_width']} {RENDER_CONFIG['window_height']}")
        loadPrcFileData("", f"window-title STALKERcraft - Seed {self.world_seed} - {self.start_location}")
        loadPrcFileData("", "framebuffer-multisample 0")
        loadPrcFileData("", "textures-auto-compress #t")
        loadPrcFileData("", "compressed-textures 1")
        loadPrcFileData("", "show-frame-rate-meter #f")
        # Disable default font warnings, try to find a font with more glyphs
        loadPrcFileData("", "text-default-font /c/Windows/Fonts/arial.ttf")  # Windows attempt, will fallback if not found

        self.showbase = ShowBase()
        self.showbase.setBackgroundColor(0.1, 0.15, 0.25)

        # Lighting
        ambient = AmbientLight("ambient")
        ambient.setColor((0.5, 0.5, 0.55, 1))
        self.showbase.render.setLight(self.showbase.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor((0.9, 0.9, 0.8, 1))
        sun_np = self.showbase.render.attachNewNode(sun)
        sun_np.setHpr(45, -45, 0)
        self.showbase.render.setLight(sun_np)
        self.sun_np = sun_np

        # Fog
        if RENDER_CONFIG["enable_fog"]:
            fog = Fog("fog")
            fog.setColor(0.6, 0.7, 0.8)
            fog.setExpDensity(0.002)
            self.showbase.render.setFog(fog)

        # Camera
        self.showbase.disableMouse()
        self.showbase.camera.setPos(0, 0, 5)

        # Create a simple axis helper to prove rendering works
        self.create_axis_helper()

        # Tasks
        self.showbase.taskMgr.add(self.panda3d_update_task, "game_update")
        self.showbase.taskMgr.add(self.mouse_look_task, "mouse_look")

        # Inputs
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
        self.showbase.accept("m", self.toggle_mouse_lock)

        self.mouse_locked = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0

        self.init_menus()
        logger.info(LogCategory.RENDER, "Panda3D window created")

    def create_axis_helper(self):
        """Create simple axis lines to prove rendering works."""
        try:
            segs = LineSegs()
            segs.setThickness(3)
            # X red
            segs.setColor(1, 0, 0, 1)
            segs.moveTo(0, 0, 0)
            segs.drawTo(10, 0, 0)
            # Y green
            segs.setColor(0, 1, 0, 1)
            segs.moveTo(0, 0, 0)
            segs.drawTo(0, 10, 0)
            # Z blue
            segs.setColor(0, 0, 1, 1)
            segs.moveTo(0, 0, 0)
            segs.drawTo(0, 0, 10)
            node = segs.create()
            self.showbase.render.attachNewNode(node)
            logger.info(LogCategory.RENDER, "Axis helper created")
        except Exception as e:
            logger.warning(LogCategory.RENDER, f"Axis helper failed: {e}")

    def init_menus(self):
        logger.info(LogCategory.MENU, "Init menus")
        from ui.menu import MainMenu, SettingsMenu, PauseMenu, LocationMapMenu, LoadingScreen

        self.menus['main'] = MainMenu(self, on_new_game=self.on_new_game, on_load_game=self.on_load_game, on_settings=self.on_settings_from_main, on_exit=self.on_exit)
        self.menus['settings'] = SettingsMenu(self, on_back=self.on_settings_back)
        self.menus['pause'] = PauseMenu(self, on_resume=self.on_resume, on_save=self.quick_save, on_load=self.on_load_game, on_settings=self.on_settings_from_pause, on_exit_to_menu=self.on_exit_to_menu)
        self.menus['location_map'] = LocationMapMenu(self, location_system=self.location_system, on_select_location=self.on_location_map_select, on_back=self.on_location_map_back)
        self.menus['loading'] = LoadingScreen(self)

    def show_main_menu(self):
        logger.info(LogCategory.MENU, "Show main menu")
        self.state = GameState.MENU
        self.hide_all_menus()
        if 'main' in self.menus:
            self.menus['main'].show()
        self.unlock_mouse()
        if self.showbase:
            self.showbase.setBackgroundColor(0.05, 0.05, 0.1)

    def show_pause_menu(self):
        logger.info(LogCategory.MENU, "Show pause")
        self.state = GameState.PAUSED
        self.hide_all_menus()
        if 'pause' in self.menus:
            self.menus['pause'].show()
        self.unlock_mouse()

    def show_settings_menu(self, from_state=GameState.MENU):
        logger.info(LogCategory.MENU, f"Show settings from {from_state}")
        self._settings_return_state = from_state
        self.state = GameState.SETTINGS
        self.hide_all_menus()
        if 'settings' in self.menus:
            self.menus['settings'].show()
        self.unlock_mouse()

    def show_location_map(self):
        logger.info(LogCategory.MENU, "Show location map")
        self.state = GameState.LOCATION_MAP
        self.hide_all_menus()
        if 'location_map' in self.menus:
            self.menus['location_map'].show()
        self.unlock_mouse()

    def show_loading_screen(self, text="Loading...", percent=0):
        logger.debug(LogCategory.MENU, f"Loading screen {text} {percent}%")
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
        if not self.showbase or not self.showbase.win:
            return
        try:
            self.showbase.win.movePointer(0, self.showbase.win.getXSize()//2, self.showbase.win.getYSize()//2)
            self.last_mouse_x = self.showbase.win.getXSize()//2
            self.last_mouse_y = self.showbase.win.getYSize()//2
            self.mouse_locked = True
            logger.debug(LogCategory.UI, "Mouse locked")
        except Exception as e:
            logger.warning(LogCategory.UI, f"Mouse lock failed: {e}")

    def unlock_mouse(self):
        self.mouse_locked = False
        logger.debug(LogCategory.UI, "Mouse unlocked")

    def toggle_mouse_lock(self):
        if self.mouse_locked:
            self.unlock_mouse()
        else:
            self.lock_mouse()

    def mouse_look_task(self, task):
        if not self.showbase or not self.headless and self.state != GameState.PLAYING:
            return task.cont
        if not self.mouse_locked:
            return task.cont
        try:
            if self.showbase.win and self.showbase.win.getPointer(0):
                x = self.showbase.win.getPointer(0).getX()
                y = self.showbase.win.getPointer(0).getY()
                dx = x - self.last_mouse_x
                dy = y - self.last_mouse_y
                # Update player rotation
                self.player.look(delta_yaw=dx * self.mouse_sensitivity, delta_pitch=-dy * self.mouse_sensitivity)
                # Reset pointer to center
                self.showbase.win.movePointer(0, self.showbase.win.getXSize()//2, self.showbase.win.getYSize()//2)
                self.last_mouse_x = self.showbase.win.getXSize()//2
                self.last_mouse_y = self.showbase.win.getYSize()//2
        except Exception as e:
            pass
        return task.cont

    def on_new_game(self, seed, location_id="cordon"):
        logger.info(LogCategory.MENU, f"New Game seed={seed} location={location_id}")
        self.world_seed = seed
        self.player = Player(seed=seed, start_pos=np.array([0, 30, 0], dtype=np.float32))
        self.clear_world_nodes()
        self.show_loading_screen("Initializing world...", 10)

        def load_thread():
            try:
                logger.info(LogCategory.LOCATION, f"Loader thread for {location_id}")
                self.load_location(location_id)
                logger.info(LogCategory.LOCATION, f"Location {location_id} loaded, switching to PLAYING")
                if self.showbase:
                    self.showbase.taskMgr.doMethodLater(0.1, lambda task: self.start_gameplay(), "start_gameplay")
                else:
                    self.start_gameplay()
            except Exception as e:
                logger.error(LogCategory.LOCATION, f"Load failed: {e}")
                import traceback
                logger.error(LogCategory.LOCATION, traceback.format_exc())

        threading.Thread(target=load_thread, daemon=True, name="LocationLoader").start()

    def clear_world_nodes(self):
        logger.info(LogCategory.RENDER, "Clearing world nodes")
        for node in self.chunk_nodes.values():
            try:
                node.removeNode()
            except:
                pass
        self.chunk_nodes.clear()
        for node in self.entity_nodes.values():
            try:
                node.removeNode()
            except:
                pass
        self.entity_nodes.clear()
        for node in self.anomaly_nodes.values():
            try:
                node.removeNode()
            except:
                pass
        self.anomaly_nodes.clear()
        for node in self.transition_nodes.values():
            try:
                node.removeNode()
            except:
                pass
        self.transition_nodes.clear()

    def load_location(self, location_id):
        logger.info(LogCategory.LOCATION, f"load_location {location_id}")
        self.show_loading_screen(f"Loading {location_id}...", 20)

        loc = self.location_system.set_active_location(location_id)
        if not loc:
            logger.error(LogCategory.LOCATION, f"Failed to load {location_id}")
            return None

        self.show_loading_screen(f"Init {loc.definition.display_name}...", 50)

        self.chunk_system = loc.chunk_system
        self.spawn_manager = loc.spawn_manager
        self.anomaly_system = loc.anomaly_system
        self.artifact_system = loc.artifact_system
        self.radiation_map = loc.radiation_map
        self.terraforming = TerraformingSystem(self.chunk_system)

        self.show_loading_screen(f"Generating meshes {loc.definition.display_name}...", 80)

        if self.chunk_system:
            self.chunk_system.request_chunk(0, 0)
            time.sleep(0.3)
            self.chunk_system.update(0, 0)
            logger.info(LogCategory.TERRAIN, f"Chunks: {len(self.chunk_system.chunks)}")

        self.show_loading_screen(f"{loc.definition.display_name} ready!", 100)
        time.sleep(0.2)
        return loc

    def start_gameplay(self):
        logger.info(LogCategory.GENERAL, "start_gameplay")
        self.hide_all_menus()
        self.state = GameState.PLAYING
        self.lock_mouse()
        if self.showbase:
            self.showbase.setBackgroundColor(0.3, 0.5, 0.8)
        logger.info(LogCategory.GENERAL, f"Game started at {self.location_system.active_location_id}")

    def on_load_game(self):
        logger.info(LogCategory.MENU, "Load game")
        saves = self.save_manager.list_saves()
        if not saves:
            logger.warning(LogCategory.SAVE, "No saves")
            return
        latest = saves[0]
        logger.info(LogCategory.SAVE, f"Loading {latest['name']}")
        data = self.save_manager.load_game(latest['name'])
        if data:
            self.clear_world_nodes()
            self.load_save_data(data)
            self.start_gameplay()
        else:
            logger.error(LogCategory.SAVE, f"Failed to load {latest['name']}")

    def on_settings_from_main(self):
        self.show_settings_menu(from_state=GameState.MENU)

    def on_settings_from_pause(self):
        self.show_settings_menu(from_state=GameState.PAUSED)

    def on_settings_back(self):
        logger.info(LogCategory.MENU, "Back from settings")
        ret = getattr(self, '_settings_return_state', GameState.MENU)
        if ret == GameState.PAUSED:
            self.show_pause_menu()
        else:
            self.show_main_menu()

    def on_resume(self):
        logger.info(LogCategory.MENU, "Resume")
        self.hide_all_menus()
        self.state = GameState.PLAYING
        self.lock_mouse()

    def on_exit_to_menu(self):
        logger.info(LogCategory.MENU, "Exit to menu")
        self.quick_save()
        self.clear_world_nodes()
        self.show_main_menu()

    def on_location_map_select(self, loc_id):
        logger.info(LogCategory.LOCATION, f"Map select {loc_id}")
        self.menus['location_map'].hide()
        self.on_new_game(self.world_seed, loc_id)

    def on_location_map_back(self):
        logger.info(LogCategory.MENU, "Back from map")
        if self.state == GameState.PLAYING or self.location_system.active_location_id:
            self.show_pause_menu()
        else:
            self.show_main_menu()

    def on_exit(self):
        logger.info(LogCategory.GENERAL, "Exit")
        self.shutdown()
        sys.exit(0)

    def set_key(self, key, value):
        self.keys[key] = value

    def on_f3(self):
        self.hud.toggle_debug()
        logger.info(LogCategory.OPTIMIZATION, f"Profiler: {self.profiler.get_text()}")
        if self.chunk_system:
            logger.info(LogCategory.TERRAIN, f"Chunks: {len(self.chunk_system.chunks)}, nodes: {len(self.chunk_nodes)}")
        if self.spawn_manager:
            logger.info(LogCategory.SPAWN, f"Animals: {len(self.spawn_manager.animals)}")
        logger.info(LogCategory.OPTIMIZATION, f"Cache: {global_cache.stats()}")

    def on_f8(self):
        self.console.toggle()
        if self.console.is_open:
            self.unlock_mouse()
        else:
            if self.state == GameState.PLAYING:
                self.lock_mouse()

    def on_escape(self):
        logger.info(LogCategory.UI, f"Esc state={self.state}")
        if self.state == GameState.PLAYING:
            self.show_pause_menu()
        elif self.state == GameState.PAUSED:
            self.on_resume()
        elif self.state == GameState.SETTINGS:
            self.on_settings_back()
        elif self.state == GameState.LOCATION_MAP:
            self.on_location_map_back()

    def on_left_click(self):
        if self.state != GameState.PLAYING:
            logger.debug(LogCategory.UI, f"LMB ignored state={self.state}")
            return
        cam_pos = self.player.get_camera_pos()
        cam_dir = self.player.get_camera_dir()
        hit = self.physics.raycast(cam_pos, cam_pos + cam_dir*10)
        if hit["hit"]:
            pos = hit["position"]
            logger.info(LogCategory.TERRAIN, f"Dig at {pos}")
            if self.terraforming:
                self.terraforming.dig(pos[0], pos[2], radius=2.0, depth=1.0)
                # Rebuild chunk node if needed
                self.rebuild_dirty_chunks()

    def on_right_click(self):
        if self.state != GameState.PLAYING:
            return
        cam_pos = self.player.get_camera_pos()
        cam_dir = self.player.get_camera_dir()
        hit = self.physics.raycast(cam_pos, cam_pos + cam_dir*10)
        if hit["hit"]:
            pos = hit["position"]
            logger.info(LogCategory.TERRAIN, f"Build at {pos}")
            if self.terraforming:
                self.terraforming.build(pos[0], pos[2], radius=2.0, height=1.0)
                self.rebuild_dirty_chunks()

    def rebuild_dirty_chunks(self):
        if not self.chunk_system or not self.showbase:
            return
        for key, chunk in self.chunk_system.chunks.items():
            if chunk.is_dirty and key in self.chunk_nodes:
                logger.info(LogCategory.TERRAIN, f"Rebuilding dirty chunk {key}")
                try:
                    self.chunk_nodes[key].removeNode()
                    del self.chunk_nodes[key]
                except:
                    pass
                chunk.is_dirty = False

    def quick_save(self):
        logger.info(LogCategory.SAVE, "Quicksave")
        data = self.get_save_data()
        self.save_manager.save_game("quicksave", data)
        logger.info(LogCategory.SAVE, "Quicksave done")

    def render_chunks(self, cam_pos):
        """Actual terrain rendering - creates GeomNodes for visible chunks."""
        if not self.showbase or not self.chunk_system:
            return

        visible = self.chunk_system.get_visible_chunks(cam_pos, None)  # disable culling for now to ensure visibility
        # If culling returns 0, fallback to all loaded chunks within distance
        if len(visible) == 0:
            # Fallback: get all chunks within 100m
            visible = []
            for chunk in self.chunk_system.chunks.values():
                if not chunk.is_loaded or not chunk.mesh:
                    continue
                chunk_world_x = chunk.x * self.chunk_system.chunk_size + self.chunk_system.chunk_size*0.5
                chunk_world_z = chunk.z * self.chunk_system.chunk_size + self.chunk_system.chunk_size*0.5
                dist = math.sqrt((chunk_world_x-cam_pos[0])**2 + (chunk_world_z-cam_pos[2])**2)
                if dist < 200:
                    lod_mesh = chunk.mesh
                    if chunk.lod_meshes:
                        # Select LOD
                        if dist < 50:
                            lod_mesh = chunk.lod_meshes[0]
                        elif dist < 150 and len(chunk.lod_meshes) > 1:
                            lod_mesh = chunk.lod_meshes[1]
                        elif len(chunk.lod_meshes) > 2:
                            lod_mesh = chunk.lod_meshes[2]
                    visible.append((chunk, lod_mesh, 0, dist))
            visible.sort(key=lambda x: x[3])

        for chunk, lod_mesh, lod_level, dist in visible[:20]:  # limit to 20 closest for CPU
            key = chunk.get_key()
            if key in self.chunk_nodes:
                continue

            try:
                from utils.procedural_mesh import export_to_panda3d
                # Export mesh to Panda3D
                geom_node = export_to_panda3d(lod_mesh)
                node_path = self.showbase.render.attachNewNode(geom_node)
                # Set position already in mesh vertices (world space), so node at 0,0,0
                # Add some color based on biome
                # Simple material
                node_path.setTwoSided(True)
                # Color by height
                # For now set a simple color
                node_path.setColor(0.3, 0.5, 0.25, 1)
                # Enable lighting
                node_path.setShaderAuto()

                self.chunk_nodes[key] = node_path
                logger.debug(LogCategory.RENDER, f"Created node for chunk {key} verts={len(lod_mesh.vertices)} dist={dist:.1f} lod={lod_level}")

            except Exception as e:
                logger.error(LogCategory.RENDER, f"Failed to create node for chunk {key}: {e}")
                import traceback
                logger.error(LogCategory.RENDER, traceback.format_exc())

        # Hide distant chunk nodes
        visible_keys = set([c[0].get_key() for c in visible])
        for key in list(self.chunk_nodes.keys()):
            if key not in visible_keys:
                # Keep but hide if far
                chunk = self.chunk_system.chunks.get(key)
                if chunk:
                    cx = chunk.x * self.chunk_system.chunk_size + self.chunk_system.chunk_size*0.5
                    cz = chunk.z * self.chunk_system.chunk_size + self.chunk_system.chunk_size*0.5
                    dist = math.sqrt((cx-cam_pos[0])**2 + (cz-cam_pos[2])**2)
                    if dist > 300:
                        try:
                            self.chunk_nodes[key].removeNode()
                            del self.chunk_nodes[key]
                            logger.debug(LogCategory.RENDER, f"Removed distant chunk node {key}")
                        except:
                            pass

    def render_transitions(self):
        """Render transition portals as visible markers."""
        if not self.showbase:
            return
        active = self.location_system.get_active_location()
        if not active:
            return

        for trans in active.transitions:
            key = f"trans_{trans.target_location_id}"
            if key in self.transition_nodes:
                continue
            try:
                from utils.procedural_mesh import PrimitiveFactory, export_to_panda3d, transform_mesh
                import numpy as np
                # Create a cylinder marker
                marker = PrimitiveFactory.cylinder(radius=trans.radius, height=10.0, segments=12, name=f"transition_{trans.target_location_id}")
                mat = np.eye(4, dtype=np.float32)
                mat[0,3] = trans.position[0]
                mat[1,3] = trans.position[1] + 5
                mat[2,3] = trans.position[2]
                marker = transform_mesh(marker, mat)
                geom_node = export_to_panda3d(marker)
                node_path = self.showbase.render.attachNewNode(geom_node)
                node_path.setColor(0.2, 0.8, 1.0, 0.5)
                node_path.setTransparency(TransparencyAttrib.MAlpha)
                node_path.setTwoSided(True)
                self.transition_nodes[key] = node_path
                logger.debug(LogCategory.RENDER, f"Created transition marker {key} at {trans.position}")
            except Exception as e:
                logger.error(LogCategory.RENDER, f"Failed to create transition marker: {e}")

    def panda3d_update_task(self, task):
        dt = globalClock.getDt()
        dt = min(dt, 1/30.0)

        if self.state == GameState.PLAYING:
            self.update(dt)
            cam_pos = self.player.get_camera_pos()
            cam_dir = self.player.get_camera_dir()
            self.showbase.camera.setPos(cam_pos[0], cam_pos[1], cam_pos[2])
            target = cam_pos + cam_dir*10
            self.showbase.camera.lookAt(target[0], target[1], target[2])

            # Sun movement
            sun_pos = self.time_cycle.get_sun_position()
            if hasattr(self, 'sun_np'):
                self.sun_np.setPos(sun_pos[0]*0.01, sun_pos[1]*0.01, sun_pos[2]*0.01)

            # Render chunks
            if task.frame % 10 == 0:  # every 10 frames to reduce CPU
                self.render_chunks(cam_pos)
                if task.frame % 60 == 0:
                    self.render_transitions()

            # Check transitions
            transition = self.location_system.check_transitions(self.player.state.position)
            if transition:
                target_id, trans_obj = transition
                logger.info(LogCategory.LOCATION, f"Transition detected {self.location_system.active_location_id} -> {target_id}")
                self.start_location_transition(target_id)

        return task.cont

    def start_location_transition(self, target_location_id):
        if self.state == GameState.LOCATION_TRANSITION:
            return
        logger.info(LogCategory.LOCATION, f"Starting transition to {target_location_id}")
        self.state = GameState.LOCATION_TRANSITION
        self.show_loading_screen(f"Transition to {LOCATION_DEFINITIONS[target_location_id].display_name}...", 0)
        self.clear_world_nodes()

        def transition_thread():
            try:
                self.quick_save()
                self.load_location(target_location_id)
                self.player.state.position = np.array([0, 30, 0], dtype=np.float32)
                logger.info(LogCategory.LOCATION, f"Transition complete to {target_location_id}")
                if self.showbase:
                    self.showbase.taskMgr.doMethodLater(0.1, lambda task: self.finish_location_transition(), "finish_transition")
                else:
                    self.finish_location_transition()
            except Exception as e:
                logger.error(LogCategory.LOCATION, f"Transition error: {e}")
                import traceback
                logger.error(LogCategory.LOCATION, traceback.format_exc())

        threading.Thread(target=transition_thread, daemon=True, name="TransitionLoader").start()

    def finish_location_transition(self):
        logger.info(LogCategory.LOCATION, "finish transition")
        self.hide_all_menus()
        self.state = GameState.PLAYING
        self.lock_mouse()
        if self.showbase:
            self.showbase.setBackgroundColor(0.3, 0.5, 0.8)

    def update(self, dt):
        self.gc_tuner.disable_in_frame()

        new_day = self.time_cycle.update(dt)
        if new_day:
            logger.info(LogCategory.WORLD, f"New day {self.time_cycle.day_count} {self.time_cycle.get_time_string()}")
            if self.anomaly_system:
                self.anomaly_system.respawn_daily(self.chunk_system, self.time_cycle.day_count)
            if self.artifact_system:
                self.artifact_system.respawn_daily(self.anomaly_system, self.chunk_system)
            self.save_manager.autosave(self.get_save_data())

        self.weather.update(dt)

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

        self.physics.step(dt)

        if self.chunk_system:
            player_chunk_x = int(self.player.state.position[0] // self.chunk_system.chunk_size)
            player_chunk_z = int(self.player.state.position[2] // self.chunk_system.chunk_size)
            self.chunk_system.update(player_chunk_x, player_chunk_z)

            if not self.noclip:
                terrain_h = self.chunk_system.get_height_at(self.player.state.position[0], self.player.state.position[2])
                if self.player.state.position[1] < terrain_h + 1.8:
                    self.player.state.position[1] = terrain_h + 1.8
                    self.player.state.velocity[1] = 0

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

        clicks = self.geiger.update(total_rad, dt)

        if self.spawn_manager:
            self.spawn_manager.update(dt, player_pos=self.player.state.position, chunk_system=self.chunk_system)

        if self.anomaly_system:
            anom_damage, _ = self.anomaly_system.update(dt, self.player.state.position)
            if anom_damage > 0 and not self.god_mode:
                self.player.take_damage(anom_damage*dt, zone="torso")

        self.frustum_culler.update_from_camera(self.player.get_camera_pos(), self.player.get_camera_dir(), (0,1,0))

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
        return data

    def load_save_data(self, data):
        logger.info(LogCategory.SAVE, f"Loading save seed={data.get('world_seed')}")
        self.world_seed = data.get("world_seed", self.world_seed)
        if "player" in data:
            self.player.from_save_dict(data["player"])
        if "time" in data:
            self.time_cycle.time_hours = data["time"]["hours"]
            self.time_cycle.day_count = data["time"]["day"]
        if "location_system" in data:
            self.location_system.from_save_dict(data["location_system"])
            active_loc = data["location_system"].get("active_location")
            if active_loc:
                self.load_location(active_loc)

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
        logger.info(LogCategory.GENERAL, "Headless finished")
        self.shutdown()

    def shutdown(self):
        logger.info(LogCategory.GENERAL, "Shutdown")
        if self.chunk_system:
            self.chunk_system.stop_workers()
        for loc_id in list(self.location_system.locations.keys()):
            if self.location_system.locations[loc_id].is_loaded:
                try:
                    self.location_system.unload_location(loc_id)
                except:
                    pass
        self.physics.shutdown()
        get_logger().shutdown()

def main():
    parser = argparse.ArgumentParser(description="STALKERcraft v0.2.1")
    parser.add_argument("--seed", type=int, default=1337, help="World seed")
    parser.add_argument("--no-render", action="store_true", help="Headless")
    parser.add_argument("--duration", type=float, default=0, help="Headless duration")
    parser.add_argument("--location", type=str, default="cordon", help="Start location")
    parser.add_argument("--log-level", type=str, default="INFO", help="DEBUG/INFO/WARNING")
    args = parser.parse_args()

    try:
        lvl = LogLevel[args.log_level.upper()]
        get_logger().level = lvl
        logger.info(LogCategory.GENERAL, f"Log level {lvl.name}")
    except:
        pass

    logger.info(LogCategory.GENERAL, f"main() seed={args.seed} loc={args.location} no-render={args.no_render}")

    game = Game(world_seed=args.seed, headless=args.no_render, start_location=args.location)

    if args.no_render or not HAS_PANDA3D:
        dur = args.duration if args.duration>0 else 10.0
        game.run_headless(duration=dur)
    else:
        logger.info(LogCategory.GENERAL, "Starting ShowBase.run()")
        try:
            game.showbase.run()
        except KeyboardInterrupt:
            logger.warning(LogCategory.GENERAL, "KeyboardInterrupt")
            game.shutdown()
        except Exception as e:
            logger.critical(LogCategory.GENERAL, f"Critical: {e}")
            import traceback
            logger.critical(LogCategory.GENERAL, traceback.format_exc())
            game.shutdown()

if __name__ == "__main__":
    main()
