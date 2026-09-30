
import math
import random
import numpy as np

class GeigerCounter:
    def __init__(self, seed=0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.current_radiation = 0.0  # мкЗв/ч
        self.click_rate = 0.0
        self.is_on = True

    def update(self, radiation_level, dt):
        self.current_radiation = radiation_level
        # треск: чем выше радиация, тем чаще клики
        # формула: клики в секунду = background + k*rad
        background = 0.2
        k = 0.5
        self.click_rate = background + k*radiation_level
        # генерируем клики
        clicks = 0
        # Пуассоновский процесс упрощённо
        prob = self.click_rate * dt
        if self.rng.random() < prob:
            clicks = 1
            if radiation_level > 10:
                clicks = self.rng.randint(1, int(radiation_level*0.1)+1)
        return clicks

    def get_display_value(self):
        return self.current_radiation

    def get_sound_intensity(self):
        return min(1.0, self.current_radiation / 50.0)

    def to_dict(self):
        return {"rad": self.current_radiation, "is_on": self.is_on}

    def from_dict(self, data):
        self.current_radiation = data.get("rad", 0.0)
        self.is_on = data.get("is_on", True)
