
from dataclasses import dataclass

@dataclass(slots=True)
class Durability:
    max_durability: float
    current: float
    wear_rate: float = 0.01

    def use(self, amount=1.0):
        self.current = max(0.0, self.current - amount*self.wear_rate)
        return self.current > 0

    def repair(self, amount):
        self.current = min(self.max_durability, self.current + amount)

    def get_percent(self):
        return (self.current / self.max_durability)*100 if self.max_durability>0 else 0
