"""
Математические утилиты для процедурной генерации.
Совместимо с Python 3.10.0, Numpy 1.24.4, Numba 0.57.1
"""
from typing import Tuple, Optional
import math
import numpy as np
import numba

# ---------- Векторные операции на Numba ----------

@numba.njit
def vec3_normalize(v):
    length = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if length < 1e-8:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)
    return v / length

@numba.njit
def vec3_cross(a, b):
    return np.array([
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    ], dtype=np.float64)

@numba.njit
def vec3_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

# ---------- Шум Перлина 2D/3D на Numba (детерминированный) ----------

@numba.njit
def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)

@numba.njit
def _lerp(a, b, t):
    return a + t * (b - a)

@numba.njit
def _grad(hash_val, x, y, z):
    h = hash_val & 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h in (12, 14) else z)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

@numba.njit
def perlin_init_permutation(seed):
    """Инициализация таблицы перестановок по seed, детерминированно."""
    np.random.seed(seed)
    p = np.arange(256, dtype=np.int64)
    np.random.shuffle(p)
    perm = np.empty(512, dtype=np.int64)
    for i in range(512):
        perm[i] = p[i & 255]
    return perm

@numba.njit
def perlin_noise_3d(x, y, z, perm):
    """Классический Perlin noise 3D."""
    X = int(math.floor(x)) & 255
    Y = int(math.floor(y)) & 255
    Z = int(math.floor(z)) & 255

    x -= math.floor(x)
    y -= math.floor(y)
    z -= math.floor(z)

    u = _fade(x)
    v = _fade(y)
    w = _fade(z)

    A = perm[X] + Y
    AA = perm[A] + Z
    AB = perm[A + 1] + Z
    B = perm[X + 1] + Y
    BA = perm[B] + Z
    BB = perm[B + 1] + Z

    return _lerp(
        _lerp(
            _lerp(_grad(perm[AA], x, y, z),
                  _grad(perm[BA], x - 1, y, z), u),
            _lerp(_grad(perm[AB], x, y - 1, z),
                  _grad(perm[BB], x - 1, y - 1, z), u), v),
        _lerp(
            _lerp(_grad(perm[AA + 1], x, y, z - 1),
                  _grad(perm[BA + 1], x - 1, y, z - 1), u),
            _lerp(_grad(perm[AB + 1], x, y - 1, z - 1),
                  _grad(perm[BB + 1], x - 1, y - 1, z - 1), u), v), w)

@numba.njit
def fbm_3d(x, y, z, octaves, lacunarity, persistence, perm):
    """Fractal Brownian Motion."""
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(octaves):
        total += perlin_noise_3d(x * frequency, y * frequency, z * frequency, perm) * amplitude
        max_val += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_val if max_val > 0 else 0.0

@numba.njit
def fbm_2d(x, y, octaves, lacunarity, persistence, perm):
    return fbm_3d(x, y, 0.0, octaves, lacunarity, persistence, perm)

# ---------- Матрицы трансформации ----------

def translation_matrix(tx, ty, tz):
    m = np.eye(4, dtype=np.float32)
    m[0, 3] = tx
    m[1, 3] = ty
    m[2, 3] = tz
    return m

def rotation_matrix_x(angle_rad):
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    m = np.eye(4, dtype=np.float32)
    m[1, 1] = c
    m[1, 2] = -s
    m[2, 1] = s
    m[2, 2] = c
    return m

def rotation_matrix_y(angle_rad):
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = c
    m[0, 2] = s
    m[2, 0] = -s
    m[2, 2] = c
    return m

def rotation_matrix_z(angle_rad):
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m

def scale_matrix(sx, sy, sz):
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = sx
    m[1, 1] = sy
    m[2, 2] = sz
    return m

# ---------- Slerp для кватернионов (упрощённо) ----------

def lerp(a, b, t):
    return a + (b - a) * t

def smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0 + 1e-8), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

# ---------- Генерация случайных чисел детерминированно ----------

def make_rng(seed):
    """Создаёт numpy Generator детерминированно."""
    return np.random.default_rng(seed)

# ---------- Marching Cubes lookup (упрощённый) ----------

# Для полной реализации нужен 256-entry table. Здесь упрощённая версия
# для heightmap-based terrain. Полный marching cubes будет в world/noise_gen.py

def compute_normals(vertices, indices):
    """Вычисление нормалей по вершинам и индексам треугольников."""
    normals = np.zeros_like(vertices, dtype=np.float32)
    # vertices: (N,3), indices: (M,3) или (M,)
    if indices.ndim == 1:
        indices = indices.reshape(-1, 3)
    for tri in indices:
        i0, i1, i2 = tri
        if i0 >= len(vertices) or i1 >= len(vertices) or i2 >= len(vertices):
            continue
        v0 = vertices[i0]
        v1 = vertices[i1]
        v2 = vertices[i2]
        e1 = v1 - v0
        e2 = v2 - v0
        n = np.cross(e1, e2)
        norm = np.linalg.norm(n)
        if norm > 1e-8:
            n /= norm
            normals[i0] += n
            normals[i1] += n
            normals[i2] += n
    # нормализация
    for i in range(len(normals)):
        l = np.linalg.norm(normals[i])
        if l > 1e-8:
            normals[i] /= l
        else:
            normals[i] = np.array([0, 1, 0], dtype=np.float32)
    return normals
