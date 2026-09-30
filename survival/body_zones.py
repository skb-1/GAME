
from dataclasses import dataclass, field
from typing import Dict

@dataclass(slots=True)
class ZoneState:
    hp: float
    max_hp: float
    bleeding: float  # 0..1
    fracture: bool
    pain: float

class BodyZones:
    def __init__(self):
        self.zones: Dict[str, ZoneState] = {
            "head": ZoneState(hp=30, max_hp=30, bleeding=0.0, fracture=False, pain=0.0),
            "torso": ZoneState(hp=100, max_hp=100, bleeding=0.0, fracture=False, pain=0.0),
            "left_arm": ZoneState(hp=50, max_hp=50, bleeding=0.0, fracture=False, pain=0.0),
            "right_arm": ZoneState(hp=50, max_hp=50, bleeding=0.0, fracture=False, pain=0.0),
            "left_leg": ZoneState(hp=60, max_hp=60, bleeding=0.0, fracture=False, pain=0.0),
            "right_leg": ZoneState(hp=60, max_hp=60, bleeding=0.0, fracture=False, pain=0.0),
        }

    def apply_damage(self, zone, amount):
        if zone in self.zones:
            z = self.zones[zone]
            z.hp = max(0.0, z.hp - amount)
            if amount > 15:
                z.bleeding = min(1.0, z.bleeding + amount*0.01)
                z.pain = min(1.0, z.pain + amount*0.02)
            if amount > 30 and zone in ["left_leg", "right_leg", "left_arm", "right_arm"]:
                z.fracture = True

    def get_total_health(self):
        total = sum(z.hp for z in self.zones.values())
        max_total = sum(z.max_hp for z in self.zones.values())
        return (total / max_total) * 100.0 if max_total>0 else 0.0

    def update(self, dt):
        for z in self.zones.values():
            if z.bleeding > 0:
                z.hp = max(0.0, z.hp - z.bleeding*dt*0.5)
                z.bleeding = max(0.0, z.bleeding - dt*0.01)

    def to_dict(self):
        return {k: {"hp": v.hp, "bleeding": v.bleeding, "fracture": v.fracture, "pain": v.pain} for k,v in self.zones.items()}

    def from_dict(self, data):
        for k,v in data.items():
            if k in self.zones:
                self.zones[k].hp = v["hp"]
                self.zones[k].bleeding = v["bleeding"]
                self.zones[k].fracture = v["fracture"]
                self.zones[k].pain = v["pain"]
