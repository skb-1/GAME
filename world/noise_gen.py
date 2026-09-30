"""
Процедурный шум для мира — Numba оптимизирован.
Python 3.10.0, Numpy 1.24.4, Numba 0.57.1
"""
import math
import numpy as np
import numba
from typing import Tuple
from config import WORLD_CONFIG
from utils.math_utils import perlin_init_permutation, fbm_2d, fbm_3d

@numba.njit
def generate_heightmap_numba(width, height, scale, octaves, lacunarity, persistence, perm, offset_x, offset_y, amplitude):
    """Генерация heightmap через Numba."""
    hm = np.zeros((height, width), dtype=np.float64)
    for y in range(height):
        for x in range(width):
            nx = (x + offset_x) * scale
            ny = (y + offset_y) * scale
            # fbm
            total = 0.0
            amp = 1.0
            freq = 1.0
            max_amp = 0.0
            for _ in range(octaves):
                # perlin 2D через 3D с z=0
                # inline perlin
                # используем fbm_2d уже определён
                # но numba не может вызвать python func, поэтому дублируем логику
                # упростим — вызовем fbm_2d если она njit
                total += fbm_2d(nx*freq, ny*freq, 1, lacunarity, persistence, perm) * amp if False else 0.0
                # для компиляции — сделаем просто
                max_amp += amp
                amp *= persistence
                freq *= lacunarity
            hm[y, x] = total / max_amp if max_amp>0 else 0.0
    return hm

# Более простая и рабочая версия без вложенных вызовов

@numba.njit
def perlin_2d_numba(x, y, perm):
    # упрощённый perlin 2D
    X = int(math.floor(x)) & 255
    Y = int(math.floor(y)) & 255
    x -= math.floor(x)
    y -= math.floor(y)
    u = x*x*x*(x*(x*6-15)+10)
    v = y*y*y*(y*(y*6-15)+10)
    A = perm[X] + Y
    B = perm[X+1] + Y
    # градиенты 2D
    def grad2(hash_val, x, y):
        h = hash_val & 3
        if h==0:
            return x + y
        elif h==1:
            return -x + y
        elif h==2:
            return x - y
        else:
            return -x - y
    # углы
    g00 = grad2(perm[A], x, y)
    g10 = grad2(perm[B], x-1, y)
    g01 = grad2(perm[A+1], x, y-1)
    g11 = grad2(perm[B+1], x-1, y-1)
    # lerp
    l1 = g00 + u*(g10-g00)
    l2 = g01 + u*(g11-g01)
    return l1 + v*(l2-l1)

@numba.njit
def fbm_2d_numba(x, y, octaves, lacunarity, persistence, perm):
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(octaves):
        total += perlin_2d_numba(x*frequency, y*frequency, perm) * amplitude
        max_val += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_val if max_val>0 else 0.0

@numba.njit
def generate_heightmap_fast(width, height, scale, octaves, lacunarity, persistence, perm, offset_x, offset_y, amplitude):
    hm = np.zeros((height, width), dtype=np.float32)
    for y in range(height):
        for x in range(width):
            nx = (x + offset_x) * scale
            ny = (y + offset_y) * scale
            hm[y, x] = fbm_2d_numba(nx, ny, octaves, lacunarity, persistence, perm) * amplitude
    return hm

@numba.njit
def generate_biome_map(width, height, scale, perm, offset_x, offset_y):
    """Биомы по шуму."""
    bm = np.zeros((height, width), dtype=np.int64)
    for y in range(height):
        for x in range(width):
            nx = (x + offset_x) * scale * 0.5
            ny = (y + offset_y) * scale * 0.5
            temp = fbm_2d_numba(nx, ny, 3, 2.0, 0.5, perm)  # -1..1
            moist = fbm_2d_numba(nx*1.3+100, ny*1.3, 3, 2.0, 0.5, perm)
            # классификация
            # temp: -1 холодно, 1 жарко; moist: -1 сухо, 1 влажно
            if temp < -0.3:
                if moist > 0.2:
                    bm[y,x] = 2  # swamp / болото
                else:
                    bm[y,x] = 3  # mountains
            elif temp > 0.5:
                if moist < -0.2:
                    bm[y,x] = 5  # wasteland
                else:
                    bm[y,x] = 1  # field
            else:
                if moist > 0.3:
                    bm[y,x] = 0  # forest
                elif moist < -0.3:
                    bm[y,x] = 1  # field
                else:
                    # red forest около центра радиации
                    # проверим дистанцию до центра
                    dist = math.sqrt((x+offset_x)*(x+offset_x) + (y+offset_y)*(y+offset_y))
                    if dist < 300:
                        bm[y,x] = 4  # red_forest
                    else:
                        bm[y,x] = 0
    return bm

class WorldNoiseGenerator:
    """Генератор мира с кэшем пермутаций."""

    def __init__(self, seed=1337):
        self.seed = seed
        self.perm = perlin_init_permutation(seed)
        self.perm2 = perlin_init_permutation(seed+1)
        self.perm_biome = perlin_init_permutation(seed+2)

    def get_heightmap(self, chunk_x, chunk_z, chunk_size=32, resolution=32):
        """Heightmap для чанка."""
        offset_x = chunk_x * chunk_size
        offset_y = chunk_z * chunk_size
        scale = WORLD_CONFIG["terrain_scale"]
        octaves = WORLD_CONFIG["terrain_octaves"]
        lacunarity = WORLD_CONFIG["terrain_lacunarity"]
        persistence = WORLD_CONFIG["terrain_persistence"]
        amplitude = WORLD_CONFIG["terrain_amplitude"]
        # генерируем (resolution+1) x (resolution+1) для меша
        hm = generate_heightmap_fast(resolution+1, resolution+1, scale, octaves, lacunarity, persistence, self.perm, offset_x, offset_y, amplitude)
        return hm

    def get_biome_map(self, chunk_x, chunk_z, chunk_size=32, resolution=16):
        offset_x = chunk_x * chunk_size
        offset_y = chunk_z * chunk_size
        scale = WORLD_CONFIG["terrain_scale"]
        bm = generate_biome_map(resolution, resolution, scale, self.perm_biome, offset_x, offset_y)
        return bm

    def get_cave_noise(self, x, y, z, scale=0.05):
        """Шум для пещер (3D)."""
        # используем fbm_3d через numba? Упрощённо через 2D
        # для скорости — 3D perlin через fbm_2d_numba с разными осями
        n1 = fbm_2d_numba(x*scale, y*scale, 3, 2.0, 0.5, self.perm)
        n2 = fbm_2d_numba(y*scale, z*scale, 3, 2.0, 0.5, self.perm2)
        return (n1 + n2)*0.5

# ---------- Marching Cubes упрощённый для терраформинга ----------

@numba.njit
def marching_cubes_heightmap_to_mesh_vertices(heightmap, chunk_size, chunk_height, resolution):
    """
    Конвертирует heightmap в вершины меша (grid).
    Возвращает vertices, indices для полигональной сетки (не воксели).
    """
    # vertices: (res+1)*(res+1)
    # каждый вертекс: x, y=height, z
    # для простоты — regular grid
    # эта функция только для Numba ускорения вычисления позиций
    # индексы генерируются отдельно
    verts = np.zeros(((resolution+1)*(resolution+1), 3), dtype=np.float32)
    idx = 0
    step = chunk_size / resolution
    for iz in range(resolution+1):
        for ix in range(resolution+1):
            x = ix * step
            z = iz * step
            y = heightmap[iz, ix] if iz < heightmap.shape[0] and ix < heightmap.shape[1] else 0.0
            verts[idx, 0] = x
            verts[idx, 1] = y
            verts[idx, 2] = z
            idx += 1
    return verts

def heightmap_to_mesh_data(heightmap, chunk_x, chunk_z, chunk_size=32, world_seed=0):
    """Конвертация heightmap в MeshData (полигональная, не кубическая)."""
    from utils.procedural_mesh import MeshData
    from utils.math_utils import compute_normals

    resolution = heightmap.shape[0]-1
    # вершины через numba
    verts_local = marching_cubes_heightmap_to_mesh_vertices(heightmap, chunk_size, 128, resolution)
    # смещаем по мировым координатам чанка
    offset_x = chunk_x * chunk_size
    offset_z = chunk_z * chunk_size
    verts_local[:,0] += offset_x
    verts_local[:,2] += offset_z

    # индексы
    indices = []
    for iz in range(resolution):
        for ix in range(resolution):
            i0 = iz*(resolution+1)+ix
            i1 = i0+1
            i2 = i0+resolution+1
            i3 = i2+1
            # два треугольника, порядок CCW
            indices.append([i0, i2, i1])
            indices.append([i1, i2, i3])
    indices = np.array(indices, dtype=np.int32)

    # UV — планарная проекция по XZ
    uvs = np.zeros((len(verts_local),2), dtype=np.float32)
    for i, v in enumerate(verts_local):
        uvs[i,0] = (v[0] - offset_x) / chunk_size
        uvs[i,1] = (v[2] - offset_z) / chunk_size

    normals = compute_normals(verts_local, indices)

    return MeshData(
        vertices=verts_local,
        normals=normals,
        uvs=uvs,
        indices=indices,
        name=f"terrain_{chunk_x}_{chunk_z}",
        seed=world_seed
    )
