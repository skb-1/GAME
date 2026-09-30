"""
Оптимизация под 8 ГБ ОЗУ: пулы, LOD, culling, GC tuning.
Python 3.10.0
"""
import gc
import sys
import time
import threading
from typing import Dict, List, Optional, Callable
import weakref
import numpy as np

from config import OPTIMIZATION_CONFIG

# ---------- Object Pool ----------

class ObjectPool:
    """Пул объектов для пуль, частиц, звуков."""
    def __init__(self, factory_func, size=64, name="pool"):
        self.factory_func = factory_func
        self.size = size
        self.name = name
        self.pool = [factory_func() for _ in range(size)]
        self.in_use = [False]*size
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            for i in range(self.size):
                if not self.in_use[i]:
                    self.in_use[i] = True
                    return self.pool[i], i
        # если пул исчерпан — создаём новый (но логируем)
        obj = self.factory_func()
        return obj, -1

    def release(self, idx):
        if idx >=0 and idx < self.size:
            with self.lock:
                self.in_use[idx] = False
                # сброс объекта если есть метод reset
                if hasattr(self.pool[idx], 'reset'):
                    self.pool[idx].reset()

    def stats(self):
        used = sum(self.in_use)
        return {"name": self.name, "size": self.size, "used": used, "free": self.size-used}

# ---------- LOD System ----------

class LODSystem:
    """LOD для мешей."""
    def __init__(self, distances=None):
        if distances is None:
            distances = OPTIMIZATION_CONFIG["lod_distances"]
        self.distances = distances

    def get_lod_level(self, distance):
        """0 — высокий, 1 — средний, 2 — низкий."""
        for i, d in enumerate(self.distances):
            if distance < d:
                return i
        return len(self.distances)

    def select_mesh(self, lod_meshes, distance):
        level = self.get_lod_level(distance)
        if level >= len(lod_meshes):
            level = len(lod_meshes)-1
        return lod_meshes[level], level

# ---------- Frustum Culling (упрощённый) ----------

class FrustumCuller:
    """Простой frustum culling по сферам."""

    def __init__(self, fov=75, aspect=16/9, near=0.1, far=2000):
        self.fov = fov
        self.aspect = aspect
        self.near = near
        self.far = far
        # плоскости фрустума будут обновляться по матрице камеры
        self.planes = []  # List[Tuple[normal, distance]]

    def update_from_camera(self, cam_pos, cam_dir, cam_up):
        """Обновление плоскостей фрустума (упрощённо)."""
        # Для простоты — только дистанция и угол
        self.cam_pos = np.array(cam_pos, dtype=np.float32)
        self.cam_dir = np.array(cam_dir, dtype=np.float32) / (np.linalg.norm(cam_dir)+1e-8)
        self.cam_up = np.array(cam_up, dtype=np.float32)

    def is_sphere_visible(self, center, radius):
        """Проверка видимости сферы."""
        if not hasattr(self, 'cam_pos'):
            return True
        # дистанция
        vec = np.array(center) - self.cam_pos
        dist = np.linalg.norm(vec)
        if dist > self.far + radius:
            return False
        if dist < self.near - radius:
            return False
        # угол
        dir_to_obj = vec / (dist+1e-8)
        dot = np.dot(dir_to_obj, self.cam_dir)
        # fov/2
        fov_rad = math.radians(self.fov*0.5)
        # если объект позади камеры — не виден
        if dot < math.cos(fov_rad + 0.3):  # небольшой запас
            # но если очень близко — может быть виден
            if dist > 5.0:
                return False
        return True

    def cull_list(self, objects):
        """objects: List[Dict с 'center' и 'radius']"""
        visible = []
        for obj in objects:
            if self.is_sphere_visible(obj['center'], obj['radius']):
                visible.append(obj)
        return visible

import math

# ---------- GC Tuning ----------

class GCTuner:
    """Ручное управление GC для стабильного FPS."""
    def __init__(self, collect_interval=5.0):
        self.collect_interval = collect_interval
        self.last_collect = time.time()
        self.enabled = True

    def disable_in_frame(self):
        """Отключить GC на время кадра."""
        if self.enabled:
            gc.disable()

    def enable_after_frame(self):
        """Включить после кадра и собрать если нужно."""
        if not gc.isenabled():
            gc.enable()
        now = time.time()
        if now - self.last_collect > self.collect_interval:
            gc.collect()
            self.last_collect = now

    def freeze(self):
        """Заморозить текущие объекты (Python 3.10 gc.freeze)."""
        try:
            gc.freeze()
        except AttributeError:
            pass

# ---------- Memory Tracker ----------

class MemoryTracker:
    def __init__(self):
        try:
            import psutil
            self.psutil = psutil
            self.has_psutil = True
        except ImportError:
            self.has_psutil = False

    def get_ram_mb(self):
        if self.has_psutil:
            process = self.psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        return 0.0

    def get_vram_mb(self):
        # Panda3D VRAM — приблизительно, через PStat? Упрощённо 0
        return 0.0

# ---------- Chunk Pool для оптимизации ----------

class ChunkMemoryPool:
    """Пул памяти для чанков с mmap опционально."""
    def __init__(self, use_mmap=True):
        self.use_mmap = use_mmap
        self.chunks = {}
        self.lru = []

    def store(self, chunk_key, data):
        self.chunks[chunk_key] = data
        if chunk_key in self.lru:
            self.lru.remove(chunk_key)
        self.lru.append(chunk_key)
        # лимит
        max_chunks = OPTIMIZATION_CONFIG["max_chunks_in_memory"]
        while len(self.chunks) > max_chunks:
            oldest = self.lru.pop(0)
            if oldest in self.chunks:
                del self.chunks[oldest]

    def get(self, chunk_key):
        if chunk_key in self.chunks:
            # обновить LRU
            if chunk_key in self.lru:
                self.lru.remove(chunk_key)
            self.lru.append(chunk_key)
            return self.chunks[chunk_key]
        return None

# ---------- Профилирование F3 ----------

class ProfilerOverlay:
    """Данные для F3 overlay."""
    def __init__(self):
        self.fps = 0.0
        self.frame_time = 0.0
        self.ram_mb = 0.0
        self.vram_mb = 0.0
        self.chunk_count = 0
        self.entity_count = 0
        self.physics_time = 0.0
        self.mesh_cache_count = 0
        self.last_update = time.time()

    def update(self, fps, chunk_count, entity_count, mesh_cache_count):
        self.fps = fps
        self.chunk_count = chunk_count
        self.entity_count = entity_count
        self.mesh_cache_count = mesh_cache_count
        try:
            import psutil
            self.ram_mb = psutil.Process().memory_info().rss / 1024 / 1024
        except:
            self.ram_mb = 0.0

    def get_text(self):
        return (
            f"FPS: {self.fps:.1f} | Frame: {self.frame_time*1000:.1f}ms\n"
            f"RAM: {self.ram_mb:.1f} MB | VRAM: {self.vram_mb:.1f} MB\n"
            f"Chunks: {self.chunk_count} | Entities: {self.entity_count}\n"
            f"MeshCache: {self.mesh_cache_count} | Physics: {self.physics_time*1000:.1f}ms\n"
            f"GC: {'enabled' if gc.isenabled() else 'disabled'}"
        )
