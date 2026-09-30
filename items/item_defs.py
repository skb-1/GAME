
ITEM_DEFINITIONS = {
    "pickaxe": {"type": "tool", "weight": 2.0, "durability": 100, "damage": 10},
    "shovel": {"type": "tool", "weight": 1.5, "durability": 80, "damage": 5},
    "axe": {"type": "tool", "weight": 2.2, "durability": 90, "damage": 15},
    "building_tool": {"type": "tool", "weight": 1.0, "durability": 120, "damage": 2},
    "rifle": {"type": "weapon", "weight": 4.0, "durability": 200, "damage": 50, "ammo": "7.62"},
    "pistol": {"type": "weapon", "weight": 1.2, "durability": 150, "damage": 25, "ammo": "9mm"},
    "knife": {"type": "weapon", "weight": 0.3, "durability": 80, "damage": 20},
    "geiger_counter": {"type": "device", "weight": 0.5, "durability": 100},
    "respirator": {"type": "armor", "weight": 0.4, "durability": 50, "rad_protection": 0.5},
    "gas_mask": {"type": "armor", "weight": 0.8, "durability": 80, "rad_protection": 0.8},
    "chem_suit": {"type": "armor", "weight": 5.0, "durability": 100, "rad_protection": 0.9},
    "exoskeleton": {"type": "armor", "weight": 15.0, "durability": 200, "rad_protection": 0.95},
    "bandage": {"type": "medicine", "weight": 0.1, "stack": 10},
    "antirad": {"type": "medicine", "weight": 0.1, "stack": 5},
    "food_can": {"type": "food", "weight": 0.5, "hunger": 0.3, "stack": 5},
    "water_bottle": {"type": "drink", "weight": 0.5, "thirst": 0.4, "stack": 5},
    "artifact_electra": {"type": "artifact", "weight": 0.3, "radiation": 5, "value": 1000},
    "artifact_zharka": {"type": "artifact", "weight": 0.4, "radiation": 8, "value": 1500},
    "artifact_gravi": {"type": "artifact", "weight": 0.5, "radiation": 12, "value": 3000},
}

def get_item_def(item_name):
    return ITEM_DEFINITIONS.get(item_name, {"type": "misc", "weight": 0.5, "durability": 50})
