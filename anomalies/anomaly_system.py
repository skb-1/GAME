
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math
import numpy as np
from utils.math_utils import make_rng
from utils.procedural_mesh import MeshData, PrimitiveFactory, Modifier, merge_meshes, transform_mesh
from utils.asset_cache import global_cache
from config import ANOMALY_CONFIG

@dataclass(slots=True)
class Anomaly:
    anomaly_id: str
    anomaly_type: str
    position: np.ndarray
    radius: float
    damage: float
    radiation: float
    active: bool = True
    seed: int = 0
    lifetime: float = 0.0

    def update(self, dt, player_pos=None):
        self.lifetime += dt
        # пульсация
        # урон если игрок внутри
        if player_pos is not None:
            dist = np.linalg.norm(self.position - np.array(player_pos))
            if dist < self.radius:
                # урон
                return self.damage * dt
        return 0.0

    def to_dict(self):
        return {"id": self.anomaly_id, "type": self.anomaly_type, "pos": self.position.tolist(), "radius": self.radius, "damage": self.damage, "radiation": self.radiation, "active": self.active, "seed": self.seed}

    @staticmethod
    def from_dict(data):
        return Anomaly(
            anomaly_id=data["id"],
            anomaly_type=data["type"],
            position=np.array(data["pos"], dtype=np.float32),
            radius=data["radius"],
            damage=data["damage"],
            radiation=data["radiation"],
            active=data["active"],
            seed=data["seed"]
        )

class AnomalySystem:
    def __init__(self, world_seed=0):
        self.world_seed = world_seed
        self.rng = make_rng(world_seed)
        self.anomalies: Dict[str, Anomaly] = {}
        self.next_id = 0

    def generate_anomaly_mesh(self, anomaly_type, seed=0):
        cached = global_cache.load_mesh(f"anomaly_{anomaly_type}", seed, category="anomaly")
        if cached:
            return cached
        # процедурный визуал — шейдерные эффекты + частицы (меш)
        if anomaly_type == "electra":
            # электрическая — сфера с шипами
            base = PrimitiveFactory.sphere(radius=1.0, segments=12, rings=10, seed=seed, name=f"anomaly_{anomaly_type}")
            base = Modifier.noise_displace(base, amplitude=0.3, frequency=2.0, octaves=3, seed=seed)
        elif anomaly_type == "zharka":
            base = PrimitiveFactory.sphere(radius=1.2, segments=10, rings=8, seed=seed, name=f"anomaly_{anomaly_type}")
            base = Modifier.noise_displace(base, amplitude=0.4, frequency=1.5, octaves=2, seed=seed)
            base = Modifier.twist(base, angle_deg=45, axis='y')
        elif anomaly_type == "kholodets":
            base = PrimitiveFactory.sphere(radius=1.0, segments=10, rings=8, seed=seed, name=f"anomaly_{anomaly_type}")
            # желе — деформация
            base = Modifier.noise_displace(base, amplitude=0.2, frequency=3.0, octaves=2, seed=seed)
        elif anomaly_type == "tramplin":
            base = PrimitiveFactory.cylinder(radius=1.5, height=0.2, segments=12, seed=seed, name=f"anomaly_{anomaly_type}")
        elif anomaly_type == "voronka":
            base = PrimitiveFactory.cone(radius=2.0, height=1.0, segments=16, seed=seed, name=f"anomaly_{anomaly_type}")
        elif anomaly_type == "graviconcentrat":
            base = PrimitiveFactory.sphere(radius=1.5, segments=14, rings=12, seed=seed, name=f"anomaly_{anomaly_type}")
            base = Modifier.noise_displace(base, amplitude=0.5, frequency=1.0, octaves=3, seed=seed)
        elif anomaly_type == "kisel":
            base = PrimitiveFactory.box(size_x=2.0, size_y=0.3, size_z=2.0, seed=seed, name=f"anomaly_{anomaly_type}")
            base = Modifier.noise_displace(base, amplitude=0.3, frequency=2.0, octaves=2, seed=seed)
        elif anomaly_type == "zhguchiy_pukh":
            # пух — много маленьких сфер
            meshes = []
            for i in range(10):
                s = PrimitiveFactory.sphere(radius=0.1, segments=6, rings=4, seed=seed+i, name=f"pukh_{i}")
                offset = self.rng.uniform(-1,1, size=3)
                mat = np.eye(4, dtype=np.float32)
                mat[0,3]=offset[0]
                mat[1,3]=offset[1]
                mat[2,3]=offset[2]
                s = transform_mesh(s, mat)
                meshes.append(s)
            base = merge_meshes(meshes, name=f"anomaly_{anomaly_type}")
        else:
            base = PrimitiveFactory.sphere(radius=1.0, segments=10, rings=8, seed=seed, name=f"anomaly_{anomaly_type}")

        global_cache.save_mesh(base, category="anomaly")
        return base

    def spawn_anomaly(self, anomaly_type, position, radius=None, seed=None):
        if seed is None:
            seed = self.rng.integers(0, 1000000)
        if radius is None:
            radius = self.rng.uniform(1.5, 4.0)
        damage_map = {"electra": 20, "zharka": 30, "kholodets": 15, "tramplin": 25, "voronka": 40, "graviconcentrat": 50, "kisel": 10, "zhguchiy_pukh": 12}
        radiation = ANOMALY_CONFIG["radiation_per_type"].get(anomaly_type, 10.0)
        anomaly_id = f"anom_{self.next_id}_{anomaly_type}"
        self.next_id += 1
        anomaly = Anomaly(
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            position=np.array(position, dtype=np.float32),
            radius=radius,
            damage=damage_map.get(anomaly_type, 10),
            radiation=radiation,
            seed=seed
        )
        self.anomalies[anomaly_id] = anomaly
        return anomaly

    def respawn_daily(self, chunk_system, day_count):
        # каждый игровой день — новые аномалии
        # очищаем старые с шансом
        to_remove = []
        for aid, anom in self.anomalies.items():
            if self.rng.random() < 0.3:  # 30% исчезают
                to_remove.append(aid)
        for aid in to_remove:
            del self.anomalies[aid]

        # спавним новые
        # по биомам, рандомно
        num_new = self.rng.integers(5, 15)
        for _ in range(num_new):
            # случайный чанк
            cx = self.rng.integers(-20, 20)
            cz = self.rng.integers(-20, 20)
            # мировая позиция внутри чанка
            x = cx*32 + self.rng.uniform(0,32)
            z = cz*32 + self.rng.uniform(0,32)
            y = chunk_system.get_height_at(x, z) + 0.5 if chunk_system else 0.0
            atype = self.rng.choice(ANOMALY_CONFIG["types"])
            self.spawn_anomaly(atype, (x,y,z))

    def update(self, dt, player_pos=None):
        total_damage = 0.0
        total_rad = 0.0
        for anom in self.anomalies.values():
            dmg = anom.update(dt, player_pos)
            total_damage += dmg
            if player_pos is not None:
                dist = np.linalg.norm(anom.position - np.array(player_pos))
                if dist < anom.radius*2:
                    # радиация
                    total_rad += anom.radiation * dt * max(0.0, 1.0 - dist/(anom.radius*2))
        return total_damage, total_rad

    def check_artifact_to_anomaly(self, artifact_type, position, conditions):
        # если выброшенный артефакт в правильных условиях — зарождает аномалию
        # conditions: dict с температурой, радиацией и т.д.
        mapping = {
            "electra": "electra",
            "zharka": "zharka",
            "kholodets": "kholodets",
            "gravi": "graviconcentrat",
            "kisel": "kisel",
        }
        # упрощённо: если условия подходят — спавн аномалии
        anom_type = mapping.get(artifact_type)
        if anom_type:
            # проверка: радиация > 20, например
            if conditions.get("radiation", 0) > 20:
                self.spawn_anomaly(anom_type, position)
                return True
        return False

    def to_dict(self):
        return {aid: anom.to_dict() for aid, anom in self.anomalies.items()}

    def from_dict(self, data):
        self.anomalies = {}
        for aid, adata in data.items():
            self.anomalies[aid] = Anomaly.from_dict(adata)
