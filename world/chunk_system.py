"""
Чанковая система — загрузка/выгрузка, LOD, терраформинг.
Python 3.10.0
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List
import threading
import time
import numpy as np
import queue

from config import WORLD_CONFIG, OPTIMIZATION_CONFIG
from .noise_gen import WorldNoiseGenerator, heightmap_to_mesh_data
from utils.procedural_mesh import MeshData, generate_lod_levels
from utils.asset_cache import global_cache
from utils.optimization import LODSystem

@dataclass(slots=True)
class Chunk:
    x: int
    z: int
    heightmap: Optional[np.ndarray] = None
    mesh: Optional[MeshData] = None
    lod_meshes: List[MeshData] = field(default_factory=list)
    biome_map: Optional[np.ndarray] = None
    is_loaded: bool = False
    is_dirty: bool = False  # нужна перестройка меша
    last_access: float = 0.0
    entities: List[str] = field(default_factory=list)  # id сущностей
    modified: bool = False  # был ли терраформинг

    def get_key(self):
        return f"{self.x}_{self.z}"

class ChunkSystem:
    """Система чанков с асинхронной генерацией."""

    def __init__(self, world_seed=1337):
        self.world_seed = world_seed
        self.noise_gen = WorldNoiseGenerator(seed=world_seed)
        self.chunks: Dict[str, Chunk] = {}
        self.lod_system = LODSystem()
        self.load_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self.chunk_size = WORLD_CONFIG["chunk_size"]
        self.view_distance = WORLD_CONFIG["view_distance_chunks"]

    def start_workers(self, num_workers=2):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop_workers(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)

    def _worker_loop(self):
        while self.running:
            try:
                task = self.load_queue.get(timeout=0.5)
                if task is None:
                    continue
                chunk_x, chunk_z = task
                # генерация
                chunk = self._generate_chunk_sync(chunk_x, chunk_z)
                self.result_queue.put(chunk)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ChunkSystem] Worker error: {e}")

    def _generate_chunk_sync(self, chunk_x, chunk_z):
        """Синхронная генерация чанка."""
        # проверка кэша
        key = f"{chunk_x}_{chunk_z}"
        cached_mesh = global_cache.load_mesh(f"terrain_{chunk_x}_{chunk_z}", self.world_seed, category="terrain")
        if cached_mesh is not None:
            # восстанавливаем чанк из кэша (heightmap нет, но меш есть)
            chunk = Chunk(x=chunk_x, z=chunk_z, mesh=cached_mesh, is_loaded=True, last_access=time.time())
            # LOD
            chunk.lod_meshes = generate_lod_levels(cached_mesh, levels=3)
            return chunk

        # heightmap
        hm = self.noise_gen.get_heightmap(chunk_x, chunk_z, chunk_size=self.chunk_size, resolution=32)
        biome = self.noise_gen.get_biome_map(chunk_x, chunk_z, chunk_size=self.chunk_size, resolution=16)
        mesh = heightmap_to_mesh_data(hm, chunk_x, chunk_z, chunk_size=self.chunk_size, world_seed=self.world_seed)
        # LOD
        lods = generate_lod_levels(mesh, levels=3)
        # кэш
        global_cache.save_mesh(mesh, category="terrain")

        chunk = Chunk(x=chunk_x, z=chunk_z, heightmap=hm, mesh=mesh, lod_meshes=lods, biome_map=biome, is_loaded=True, last_access=time.time())
        return chunk

    def request_chunk(self, chunk_x, chunk_z):
        key = f"{chunk_x}_{chunk_z}"
        if key in self.chunks:
            self.chunks[key].last_access = time.time()
            return self.chunks[key]
        # добавить в очередь — проверяем что уже нет в очереди
        try:
            queued_keys = [f"{qx}_{qz}" for (qx,qz) in list(self.load_queue.queue)]
        except:
            queued_keys = []
        if key not in queued_keys:
            self.load_queue.put((chunk_x, chunk_z))
        # временный чанк-заглушка
        placeholder = Chunk(x=chunk_x, z=chunk_z, is_loaded=False, last_access=time.time())
        self.chunks[key] = placeholder
        return placeholder

    def update(self, player_chunk_x, player_chunk_z):
        """Обновление — загрузка вокруг игрока, выгрузка далёких."""
        # обработка результатов
        while not self.result_queue.empty():
            try:
                chunk = self.result_queue.get_nowait()
                key = chunk.get_key()
                self.chunks[key] = chunk
            except queue.Empty:
                break

        # запросить чанки в радиусе
        for dx in range(-self.view_distance, self.view_distance+1):
            for dz in range(-self.view_distance, self.view_distance+1):
                cx = player_chunk_x + dx
                cz = player_chunk_z + dz
                dist = abs(dx)+abs(dz)
                if dist <= self.view_distance:
                    self.request_chunk(cx, cz)

        # выгрузка далёких
        max_chunks = OPTIMIZATION_CONFIG["max_chunks_in_memory"]
        if len(self.chunks) > max_chunks:
            # сортируем по last_access
            sorted_chunks = sorted(self.chunks.items(), key=lambda kv: kv[1].last_access)
            to_unload = len(self.chunks) - max_chunks
            for i in range(to_unload):
                key, chunk = sorted_chunks[i]
                # не выгружать близкие к игроку
                if abs(chunk.x - player_chunk_x) <= self.view_distance and abs(chunk.z - player_chunk_z) <= self.view_distance:
                    continue
                del self.chunks[key]

    def get_visible_chunks(self, player_pos, frustum_culler=None):
        """Получить видимые чанки с учётом LOD."""
        visible = []
        px, py, pz = player_pos
        for chunk in self.chunks.values():
            if not chunk.is_loaded or not chunk.mesh:
                continue
            # дистанция
            chunk_world_x = chunk.x * self.chunk_size + self.chunk_size*0.5
            chunk_world_z = chunk.z * self.chunk_size + self.chunk_size*0.5
            dist = math.sqrt((chunk_world_x-px)**2 + (chunk_world_z-pz)**2)
            # LOD
            lod_mesh, lod_level = self.lod_system.select_mesh(chunk.lod_meshes if chunk.lod_meshes else [chunk.mesh], dist)
            # frustum culling
            if frustum_culler:
                center = (chunk_world_x, 0, chunk_world_z)
                radius = self.chunk_size*0.8
                if not frustum_culler.is_sphere_visible(center, radius):
                    continue
            visible.append((chunk, lod_mesh, lod_level, dist))
        # сортировка по дистанции (ближе первые)
        visible.sort(key=lambda x: x[3])
        return visible

    def terraform(self, chunk_x, chunk_z, world_x, world_z, radius, delta_height):
        """Терраформинг — деформация heightmap в точке."""
        key = f"{chunk_x}_{chunk_z}"
        chunk = self.chunks.get(key)
        if chunk is None or chunk.heightmap is None:
            return False
        # найдём индексы в heightmap
        # heightmap: (res+1, res+1), локальные координаты 0..chunk_size
        local_x = world_x - chunk_x*self.chunk_size
        local_z = world_z - chunk_z*self.chunk_size
        res = chunk.heightmap.shape[0]-1
        # преобразуем в индексы
        ix = int((local_x / self.chunk_size) * res)
        iz = int((local_z / self.chunk_size) * res)
        # радиус в индексах
        r_idx = int((radius / self.chunk_size) * res) + 1
        # применяем
        for dz in range(-r_idx, r_idx+1):
            for dx in range(-r_idx, r_idx+1):
                nx = ix+dx
                nz = iz+dz
                if 0 <= nx < chunk.heightmap.shape[1] and 0 <= nz < chunk.heightmap.shape[0]:
                    dist = math.sqrt(dx*dx + dz*dz)
                    if dist <= r_idx:
                        # falloff
                        falloff = 1.0 - (dist / (r_idx+1e-8))
                        chunk.heightmap[nz, nx] += delta_height * falloff
        chunk.is_dirty = True
        chunk.modified = True
        # перестроить меш
        new_mesh = heightmap_to_mesh_data(chunk.heightmap, chunk_x, chunk_z, chunk_size=self.chunk_size, world_seed=self.world_seed)
        chunk.mesh = new_mesh
        chunk.lod_meshes = generate_lod_levels(new_mesh, levels=3)
        # обновить кэш
        global_cache.save_mesh(new_mesh, category="terrain")
        return True

    def get_height_at(self, world_x, world_z):
        """Высота террейна в точке."""
        chunk_x = int(world_x // self.chunk_size)
        chunk_z = int(world_z // self.chunk_size)
        key = f"{chunk_x}_{chunk_z}"
        chunk = self.chunks.get(key)
        if chunk and chunk.heightmap is not None:
            local_x = world_x - chunk_x*self.chunk_size
            local_z = world_z - chunk_z*self.chunk_size
            res = chunk.heightmap.shape[0]-1
            fx = (local_x / self.chunk_size) * res
            fz = (local_z / self.chunk_size) * res
            ix = int(fx)
            iz = int(fz)
            # билинейная интерполяция
            if 0 <= ix < res and 0 <= iz < res:
                tx = fx - ix
                tz = fz - iz
                h00 = chunk.heightmap[iz, ix]
                h10 = chunk.heightmap[iz, ix+1]
                h01 = chunk.heightmap[iz+1, ix]
                h11 = chunk.heightmap[iz+1, ix+1]
                h0 = h00*(1-tx) + h10*tx
                h1 = h01*(1-tx) + h11*tx
                h = h0*(1-tz) + h1*tz
                return h
        # fallback — шум
        # генерируем быстро
        hm = self.noise_gen.get_heightmap(chunk_x, chunk_z, chunk_size=self.chunk_size, resolution=4)
        return float(np.mean(hm))

import math
