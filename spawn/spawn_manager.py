
import math
import numpy as np
from typing import Dict, List, Optional
from utils.math_utils import make_rng
from entities.animal_ai import AnimalAIController
from config import ANIMAL_CONFIG, BIOME_TYPES
from world.biome import get_biome_properties

class SpawnManager:
    def __init__(self, world_seed=0, chunk_system=None):
        self.world_seed = world_seed
        self.rng = make_rng(world_seed)
        self.chunk_system = chunk_system
        self.animals: Dict[str, AnimalAIController] = {}
        self.next_id = 0
        self.max_animals = 100

    def spawn_animal(self, animal_type, position=None, territory_center=None):
        if len(self.animals) >= self.max_animals:
            return None
        if position is None:
            # случайная позиция около игрока? Пока 0,0
            position = self.rng.uniform(-100, 100, size=3)
            position[1] = 10.0
        aid = f"animal_{self.next_id}_{animal_type}"
        self.next_id += 1
        controller = AnimalAIController(animal_type=animal_type, seed=self.rng.integers(0,1000000), position=position, territory_center=territory_center if territory_center is not None else position)
        self.animals[aid] = controller
        return aid

    def update(self, dt, player_pos=None, chunk_system=None):
        # обновление всех животных
        to_remove = []
        for aid, animal in self.animals.items():
            # дистанция до игрока — деспавн если далеко
            if player_pos is not None:
                dist = np.linalg.norm(animal.state.position - np.array(player_pos))
                if dist > 500.0:  # despawn distance
                    to_remove.append(aid)
                    continue
            # собрать позиции хищников для травоядных
            predator_positions = []
            for other_id, other in self.animals.items():
                if other_id != aid and other.animal_type in ["wolf", "bear"]:
                    predator_positions.append(other.state.position)
            animal.update(dt, player_pos=player_pos, predator_positions=predator_positions)

            if not animal.is_alive():
                to_remove.append(aid)

        for aid in to_remove:
            if aid in self.animals:
                del self.animals[aid]

        # спавн новых по биомам
        if player_pos is not None and chunk_system is not None:
            # проверяем чанки вокруг игрока
            player_chunk_x = int(player_pos[0] // chunk_system.chunk_size)
            player_chunk_z = int(player_pos[2] // chunk_system.chunk_size)
            for dx in range(-2,3):
                for dz in range(-2,3):
                    cx = player_chunk_x + dx
                    cz = player_chunk_z + dz
                    key = f"{cx}_{cz}"
                    chunk = chunk_system.chunks.get(key)
                    if chunk and chunk.biome_map is not None:
                        # биом
                        biome_id = int(np.mean(chunk.biome_map))
                        biome_name = BIOME_TYPES[biome_id % len(BIOME_TYPES)]
                        props = get_biome_properties(biome_name)
                        # шанс спавна
                        if self.rng.random() < 0.01 and len(self.animals) < self.max_animals:
                            animal_type = self.rng.choice(props["animal_types"])
                            x = cx*chunk_system.chunk_size + self.rng.uniform(0, chunk_system.chunk_size)
                            z = cz*chunk_system.chunk_size + self.rng.uniform(0, chunk_system.chunk_size)
                            y = chunk_system.get_height_at(x,z) + 1.0
                            self.spawn_animal(animal_type, position=np.array([x,y,z]), territory_center=np.array([x,y,z]))

    def kill_all(self):
        self.animals.clear()

    def get_animals_in_radius(self, pos, radius):
        result = []
        for aid, animal in self.animals.items():
            if np.linalg.norm(animal.state.position - np.array(pos)) < radius:
                result.append((aid, animal))
        return result

    def to_dict(self):
        return {aid: {"type": ctrl.animal_type, "pos": ctrl.state.position.tolist(), "health": ctrl.state.health, "hunger": ctrl.state.hunger, "seed": ctrl.seed} for aid, ctrl in self.animals.items()}

    def from_dict(self, data):
        self.animals = {}
        for aid, adata in data.items():
            ctrl = AnimalAIController(animal_type=adata["type"], seed=adata["seed"], position=np.array(adata["pos"]))
            ctrl.state.health = adata["health"]
            ctrl.state.hunger = adata["hunger"]
            self.animals[aid] = ctrl
