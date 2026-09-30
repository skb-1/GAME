
from typing import Dict
import numpy as np
from config import BIOME_TYPES

BIOME_PROPERTIES = {
    "forest": {"tree_density": 0.8, "grass_density": 0.7, "animal_types": ["wolf", "deer", "hare", "bear"], "radiation": 0.1},
    "field": {"tree_density": 0.1, "grass_density": 0.9, "animal_types": ["hare", "deer", "raven"], "radiation": 0.05},
    "swamp": {"tree_density": 0.4, "grass_density": 0.5, "animal_types": ["boar", "snake", "raven"], "radiation": 0.3},
    "mountains": {"tree_density": 0.2, "grass_density": 0.3, "animal_types": ["wolf", "bear", "raven"], "radiation": 0.15},
    "red_forest": {"tree_density": 0.9, "grass_density": 0.4, "animal_types": ["wolf", "boar", "snake"], "radiation": 0.8},
    "wasteland": {"tree_density": 0.05, "grass_density": 0.1, "animal_types": ["raven", "snake"], "radiation": 0.6},
}

def get_biome_properties(biome_id_or_name):
    if isinstance(biome_id_or_name, int):
        name = BIOME_TYPES[biome_id_or_name % len(BIOME_TYPES)]
    else:
        name = biome_id_or_name
    return BIOME_PROPERTIES.get(name, BIOME_PROPERTIES["forest"])

def get_biome_name(biome_id):
    return BIOME_TYPES[biome_id % len(BIOME_TYPES)]
