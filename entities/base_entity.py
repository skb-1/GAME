
from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np

@dataclass(slots=True)
class BaseEntity:
    entity_id: str
    entity_type: str
    position: np.ndarray
    rotation: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    health: float = 100.0
    is_active: bool = True
    seed: int = 0

    def distance_to(self, pos):
        return float(np.linalg.norm(self.position - np.array(pos)))

    def update(self, dt):
        pass
