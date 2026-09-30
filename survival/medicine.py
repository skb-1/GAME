
from typing import Dict

class MedicineSystem:
    def __init__(self):
        self.items = {
            "bandage": {"heal": 10, "stop_bleed": 0.5, "infection": -0.1},
            "tourniquet": {"heal": 0, "stop_bleed": 1.0, "pain": 0.2},
            "painkiller": {"pain": -0.5, "heal": 5},
            "antirad": {"radiation": -100, "heal": 0},
            "antibiotic": {"infection": -0.5},
            "syringe": {"heal": 30, "pain": -0.3},
        }

    def use(self, item_name, body_zones, needs):
        if item_name not in self.items:
            return False
        eff = self.items[item_name]
        if "heal" in eff:
            # лечим все зоны немного
            for zone in body_zones.zones.values():
                zone.hp = min(zone.max_hp, zone.hp + eff["heal"]*0.1)
        if "stop_bleed" in eff:
            for zone in body_zones.zones.values():
                zone.bleeding = max(0.0, zone.bleeding - eff["stop_bleed"])
        if "pain" in eff:
            needs.pain = max(0.0, min(1.0, needs.pain + eff["pain"]))
            for zone in body_zones.zones.values():
                zone.pain = max(0.0, min(1.0, zone.pain + eff["pain"]))
        if "radiation" in eff:
            needs.radiation = max(0.0, needs.radiation + eff["radiation"])
        if "infection" in eff:
            needs.infection = max(0.0, needs.infection + eff["infection"])
        return True
