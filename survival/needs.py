
from dataclasses import dataclass

@dataclass(slots=True)
class SurvivalNeeds:
    hunger: float = 1.0  # 0..1
    thirst: float = 1.0
    fatigue: float = 0.0  # 0..1, 1 = устал
    temperature: float = 36.6
    radiation: float = 0.0  # мЗв
    infection: float = 0.0
    pain: float = 0.0

    def update(self, dt):
        # голод/жажда убывают
        self.hunger = max(0.0, self.hunger - dt*0.0001)  # медленно
        self.thirst = max(0.0, self.thirst - dt*0.00015)
        self.fatigue = min(1.0, self.fatigue + dt*0.00005)
        # температура зависит от окружения — упрощённо
        # радиация спадает медленно если есть антирад
        if self.radiation > 0:
            self.radiation = max(0.0, self.radiation - dt*0.001)

    def add_radiation(self, amount):
        self.radiation += amount

    def eat(self, amount):
        self.hunger = min(1.0, self.hunger + amount)

    def drink(self, amount):
        self.thirst = min(1.0, self.thirst + amount)

    def to_dict(self):
        return {"hunger": self.hunger, "thirst": self.thirst, "fatigue": self.fatigue, "temperature": self.temperature, "radiation": self.radiation, "infection": self.infection, "pain": self.pain}

    def from_dict(self, data):
        self.hunger = data.get("hunger", 1.0)
        self.thirst = data.get("thirst", 1.0)
        self.fatigue = data.get("fatigue", 0.0)
        self.temperature = data.get("temperature", 36.6)
        self.radiation = data.get("radiation", 0.0)
        self.infection = data.get("infection", 0.0)
        self.pain = data.get("pain", 0.0)
