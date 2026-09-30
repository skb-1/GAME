
from dataclasses import dataclass
import numpy as np
from utils.math_utils import make_rng
from config import ANOMALY_CONFIG

@dataclass(slots=True)
class Artifact:
    artifact_id: str
    artifact_type: str
    position: np.ndarray
    value: float
    radiation: float
    seed: int
    is_active: bool = True

    def to_dict(self):
        return {"id": self.artifact_id, "type": self.artifact_type, "pos": self.position.tolist(), "value": self.value, "radiation": self.radiation, "seed": self.seed, "active": self.is_active}

    @staticmethod
    def from_dict(data):
        return Artifact(
            artifact_id=data["id"],
            artifact_type=data["type"],
            position=np.array(data["pos"], dtype=np.float32),
            value=data["value"],
            radiation=data["radiation"],
            seed=data["seed"],
            is_active=data.get("active", True)
        )

class ArtifactSystem:
    def __init__(self, world_seed=0):
        self.world_seed = world_seed
        self.rng = make_rng(world_seed)
        self.artifacts = {}
        self.next_id = 0

    def spawn_artifact(self, artifact_type, position, seed=None):
        if seed is None:
            seed = self.rng.integers(0, 1000000)
        value_map = {"electra": 1000, "zharka": 1500, "kholodets": 1200, "gravi": 3000, "kisel": 800, "pukh": 600}
        rad_map = {"electra": 5, "zharka": 8, "kholodets": 4, "gravi": 12, "kisel": 3, "pukh": 2}
        aid = f"art_{self.next_id}_{artifact_type}"
        self.next_id += 1
        art = Artifact(
            artifact_id=aid,
            artifact_type=artifact_type,
            position=np.array(position, dtype=np.float32),
            value=value_map.get(artifact_type, 500),
            radiation=rad_map.get(artifact_type, 3),
            seed=seed
        )
        self.artifacts[aid] = art
        return art

    def respawn_daily(self, anomaly_system, chunk_system):
        # артефакты спавнятся около аномалий
        to_remove = []
        for aid in self.artifacts:
            if self.rng.random() < 0.4:
                to_remove.append(aid)
        for aid in to_remove:
            del self.artifacts[aid]

        # новые около аномалий
        for anom in anomaly_system.anomalies.values():
            if self.rng.random() < 0.5:
                # тип артефакта привязан к аномалии
                mapping = {
                    "electra": "electra",
                    "zharka": "zharka",
                    "kholodets": "kholodets",
                    "tramplin": "gravi",
                    "voronka": "gravi",
                    "graviconcentrat": "gravi",
                    "kisel": "kisel",
                    "zhguchiy_pukh": "pukh"
                }
                atype = mapping.get(anom.anomaly_type, "electra")
                offset = self.rng.uniform(-2,2, size=3)
                pos = anom.position + offset
                self.spawn_artifact(atype, pos)

    def update(self, dt, player_pos=None):
        # артефакты могут излучать радиацию
        total_rad = 0.0
        if player_pos is not None:
            for art in self.artifacts.values():
                dist = np.linalg.norm(art.position - np.array(player_pos))
                if dist < 5.0:
                    total_rad += art.radiation * dt * max(0.0, 1.0 - dist/5.0)
        return total_rad

    def to_dict(self):
        return {aid: art.to_dict() for aid, art in self.artifacts.items()}

    def from_dict(self, data):
        self.artifacts = {}
        for aid, adata in data.items():
            self.artifacts[aid] = Artifact.from_dict(adata)
