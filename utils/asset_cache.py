"""
Кэширование процедурных мешей и текстур на диск и в память.
Оптимизация под 8 ГБ ОЗУ: weakref + mmap + npz.
Python 3.10.0 совместимость.
"""
import os
import hashlib
import pickle
import zlib
import weakref
import gc
from typing import Dict, Optional, Any
import numpy as np

from config import ASSET_CACHE_DIR

class AssetCache:
    """Кэш для мешей и текстур."""

    def __init__(self, cache_dir=ASSET_CACHE_DIR, max_memory_items=512):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.max_memory_items = max_memory_items
        # weakref кэш в памяти
        self._memory_cache: Dict[str, Any] = {}
        self._weak_cache = weakref.WeakValueDictionary()
        self._access_order = []  # LRU

    def _key_to_filename(self, key, ext=".npz"):
        # хэш ключа для безопасного имени файла
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        safe_key = "".join(c if c.isalnum() or c in "_-" else "_" for c in key)[:50]
        return os.path.join(self.cache_dir, f"{safe_key}_{h}{ext}")

    def _make_key(self, category, name, seed, extra=""):
        return f"{category}_{name}_{seed}_{extra}"

    def save_mesh(self, mesh, category="mesh", extra=""):
        """Сохранить MeshData в кэш."""
        from .procedural_mesh import export_to_dict
        key = self._make_key(category, mesh.name, mesh.seed, extra)
        data = export_to_dict(mesh)
        # сохранить в npz
        filename = self._key_to_filename(key, ext=".npz")
        try:
            np.savez_compressed(filename, **{k: v for k,v in data.items() if isinstance(v, np.ndarray)}, name=np.array(data["name"]), seed=np.array(data["seed"]))
            # также pickle для сложных структур? npz достаточно
        except Exception as e:
            print(f"[AssetCache] Ошибка сохранения меша {key}: {e}")
        # в память
        self._memory_cache[key] = mesh
        self._access_order.append(key)
        self._enforce_limit()
        return key

    def load_mesh(self, name, seed, category="mesh", extra=""):
        """Загрузить меш из кэша (память или диск)."""
        key = self._make_key(category, name, seed, extra)
        # память
        if key in self._memory_cache:
            # LRU обновить
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return self._memory_cache[key]
        # диск
        filename = self._key_to_filename(key, ext=".npz")
        if os.path.exists(filename):
            try:
                npz = np.load(filename, allow_pickle=True)
                # восстановить MeshData
                from .procedural_mesh import MeshData
                vertices = npz["vertices"]
                normals = npz["normals"]
                uvs = npz["uvs"]
                indices = npz["indices"]
                mesh_name = str(npz["name"]) if "name" in npz else name
                mesh_seed = int(npz["seed"]) if "seed" in npz else seed
                mesh = MeshData(vertices=vertices, normals=normals, uvs=uvs, indices=indices, name=mesh_name, seed=mesh_seed)
                self._memory_cache[key] = mesh
                self._access_order.append(key)
                self._enforce_limit()
                return mesh
            except Exception as e:
                print(f"[AssetCache] Ошибка загрузки меша {key}: {e}")
                return None
        return None

    def save_texture(self, material, category="texture", extra=""):
        """Сохранить материал."""
        key = self._make_key(category, material.name, material.seed, extra)
        filename = self._key_to_filename(key, ext=".npz")
        try:
            from .procedural_texture import material_to_numpy_cache
            cache_dict = material_to_numpy_cache(material)
            np.savez_compressed(filename, **{k: v for k,v in cache_dict.items() if isinstance(v, np.ndarray)}, name=np.array(cache_dict["name"]), seed=np.array(cache_dict["seed"]))
        except Exception as e:
            print(f"[AssetCache] Ошибка сохранения текстуры {key}: {e}")
        self._memory_cache[key] = material
        self._access_order.append(key)
        self._enforce_limit()
        return key

    def load_texture(self, name, seed, category="texture", extra=""):
        key = self._make_key(category, name, seed, extra)
        if key in self._memory_cache:
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return self._memory_cache[key]
        filename = self._key_to_filename(key, ext=".npz")
        if os.path.exists(filename):
            try:
                npz = np.load(filename, allow_pickle=True)
                from .procedural_texture import PBRMaterial
                albedo = npz["albedo"]
                roughness = npz["roughness"]
                metallic = npz["metallic"]
                normal_encoded = npz["normal_encoded"]
                # восстановить normal из encoded
                normal = normal_encoded*2.0 - 1.0
                height = npz["height"] if "height" in npz else None
                mat_name = str(npz["name"]) if "name" in npz else name
                mat_seed = int(npz["seed"]) if "seed" in npz else seed
                mat = PBRMaterial(name=mat_name, albedo=albedo, roughness=roughness, metallic=metallic, normal=normal, normal_encoded=normal_encoded, height=height, seed=mat_seed)
                self._memory_cache[key] = mat
                self._access_order.append(key)
                self._enforce_limit()
                return mat
            except Exception as e:
                print(f"[AssetCache] Ошибка загрузки текстуры {key}: {e}")
                return None
        return None

    def _enforce_limit(self):
        """Ограничить память по LRU."""
        while len(self._memory_cache) > self.max_memory_items:
            oldest = self._access_order.pop(0)
            if oldest in self._memory_cache:
                del self._memory_cache[oldest]

    def clear_memory(self):
        self._memory_cache.clear()
        self._access_order.clear()
        gc.collect()

    def clear_disk(self, category=None):
        """Очистить диск."""
        for fname in os.listdir(self.cache_dir):
            if category is None or category in fname:
                try:
                    os.remove(os.path.join(self.cache_dir, fname))
                except:
                    pass
        self.clear_memory()

    def stats(self):
        return {
            "memory_items": len(self._memory_cache),
            "disk_files": len(os.listdir(self.cache_dir)),
            "max_memory": self.max_memory_items,
        }

# Глобальный инстанс
global_cache = AssetCache()
