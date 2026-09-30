
import time

class SleepSystem:
    def __init__(self):
        self.is_sleeping = False
        self.sleep_start = 0.0
        self.sleep_duration = 0.0
        self.dreams = ["Тихий шёпот в темноте...", "Вы слышите счётчик Гейгера во сне", "Кошмар о выбросе", "Сон о доме"]

    def start_sleep(self, duration_hours=8.0):
        self.is_sleeping = True
        self.sleep_start = time.time()
        self.sleep_duration = duration_hours*60  # в игровых минутах? упрощённо

    def update(self, dt, player):
        if not self.is_sleeping:
            return None
        # проверка прерывания — если рядом враг
        # упрощённо — спим
        self.sleep_duration -= dt
        if self.sleep_duration <= 0:
            self.is_sleeping = False
            player.state.is_sleeping = False
            # событие сна
            import random
            dream = random.choice(self.dreams)
            return dream
        return None

    def interrupt(self):
        self.is_sleeping = False
