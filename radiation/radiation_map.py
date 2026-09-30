
import math
import numpy as np
from utils.math_utils import make_rng
from config import RADIATION_CONFIG

class RadiationMap:
    def __init__(self, world_seed=0):
        self.world_seed = world_seed
        self.rng = make_rng(world_seed)
        self.center = np.array(RADIATION_CONFIG["chernobyl_center"], dtype=np.float32)
        self.max_radius = RADIATION_CONFIG["max_radius"]
        self.background = RADIATION_CONFIG["background"]
        # точки сильного заражения
        self.hotspots = []
        for _ in range(15):
            angle = self.rng.uniform(0, 2*math.pi)
            r = self.rng.uniform(0, self.max_radius*0.8)
            x = self.center[0] + math.cos(angle)*r
            y = self.center[1] + math.sin(angle)*r
            intensity = self.rng.uniform(10, 100)
            radius = self.rng.uniform(30, 100)
            self.hotspots.append({"pos": np.array([x,y], dtype=np.float32), "intensity": intensity, "radius": radius})

    def get_radiation_at(self, world_x, world_z):
        # дистанция до центра ЧАЭС
        dx = world_x - self.center[0]
        dz = world_z - self.center[1]
        dist_to_center = math.sqrt(dx*dx + dz*dz)
        # базовая радиация убывает с расстоянием
        base = self.background
        if dist_to_center < self.max_radius:
            # экспоненциальное убывание
            base += 50.0 * math.exp(-dist_to_center / (self.max_radius*0.3))

        # hotspots
        for hs in self.hotspots:
            dx_h = world_x - hs["pos"][0]
            dz_h = world_z - hs["pos"][1]
            dist_h = math.sqrt(dx_h*dx_h + dz_h*dz_h)
            if dist_h < hs["radius"]:
                base += hs["intensity"] * (1.0 - dist_h/hs["radius"])

        return base

    def get_radiation_at_3d(self, pos):
        return self.get_radiation_at(pos[0], pos[2])

    def to_dict(self):
        return {"hotspots": [{"pos": hs["pos"].tolist(), "intensity": hs["intensity"], "radius": hs["radius"]} for hs in self.hotspots]}

    def from_dict(self, data):
        self.hotspots = []
        for hs in data.get("hotspots", []):
            self.hotspots.append({"pos": np.array(hs["pos"], dtype=np.float32), "intensity": hs["intensity"], "radius": hs["radius"]})
