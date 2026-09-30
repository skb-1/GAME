
from typing import List, Dict, Optional
from .item_defs import get_item_def
from .durability import Durability

class InventoryItem:
    def __init__(self, item_name, count=1, seed=0):
        self.item_name = item_name
        self.count = count
        self.seed = seed
        self.defn = get_item_def(item_name)
        if "durability" in self.defn:
            self.durability = Durability(max_durability=self.defn["durability"], current=self.defn["durability"])
        else:
            self.durability = None

    def to_dict(self):
        return {"name": self.item_name, "count": self.count, "seed": self.seed, "durability": self.durability.current if self.durability else None}

    def from_dict(self, data):
        self.item_name = data["name"]
        self.count = data["count"]
        self.seed = data.get("seed", 0)
        if data.get("durability") is not None and self.durability:
            self.durability.current = data["durability"]

class Inventory:
    def __init__(self, max_weight=30.0, max_slots=20):
        self.max_weight = max_weight
        self.max_slots = max_slots
        self.items: List[InventoryItem] = []

    def get_weight(self):
        total = 0.0
        for item in self.items:
            total += item.defn.get("weight", 0.5) * item.count
        return total

    def add_item(self, item_name, count=1, seed=0):
        # проверка стаков
        defn = get_item_def(item_name)
        if "stack" in defn:
            for existing in self.items:
                if existing.item_name == item_name and existing.count < defn["stack"]:
                    space = defn["stack"] - existing.count
                    add = min(space, count)
                    existing.count += add
                    count -= add
                    if count <= 0:
                        return True
        # новые слоты
        if len(self.items) >= self.max_slots:
            return False
        if self.get_weight() + defn.get("weight",0.5)*count > self.max_weight:
            return False
        if count>0:
            self.items.append(InventoryItem(item_name, count, seed))
        return True

    def remove_item(self, item_name, count=1):
        for i, item in enumerate(self.items):
            if item.item_name == item_name:
                if item.count >= count:
                    item.count -= count
                    if item.count <= 0:
                        self.items.pop(i)
                    return True
                else:
                    count -= item.count
                    self.items.pop(i)
        return False

    def has_item(self, item_name, count=1):
        total = sum(item.count for item in self.items if item.item_name == item_name)
        return total >= count

    def to_dict(self):
        return {"items": [it.to_dict() for it in self.items], "max_weight": self.max_weight, "max_slots": self.max_slots}

    def from_dict(self, data):
        self.max_weight = data.get("max_weight", 30.0)
        self.max_slots = data.get("max_slots", 20)
        self.items = []
        for it_data in data.get("items", []):
            it = InventoryItem(it_data["name"], it_data["count"], it_data.get("seed",0))
            it.from_dict(it_data)
            self.items.append(it)
