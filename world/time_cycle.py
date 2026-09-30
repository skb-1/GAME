
import math

class TimeCycle:
    def __init__(self, start_hour=8.0, day_length_minutes=24):
        self.day_length_minutes = day_length_minutes
        self.day_length_seconds = day_length_minutes * 60.0
        self.time_hours = start_hour  # 0..24
        self.day_count = 0

    def update(self, dt):
        # dt в секундах реального времени, переводим в игровые часы
        # 24 игровых минуты = сутки => 1 реал сек = (24*60 / (24*60))? Упростим: 1 реал сек = 1 игровая минута?
        # По ТЗ: 24 игровых минуты = сутки => 1440 игровых минут = 24 часа? Нет, 24 игровые минуты = 24 игровых часа
        # Значит 1 игровая минута = 1 реальная секунда? Тогда сутки = 24 сек? Это быстро.
        # Сделаем: day_length_minutes = 24 => сутки за 24*60=1440 реал сек = 24 мин реального времени
        # Так что 1 реал сек = 1 игровая минута = 1/60 игрового часа
        game_hours_per_real_sec = 24.0 / self.day_length_seconds
        self.time_hours += dt * game_hours_per_real_sec
        if self.time_hours >= 24.0:
            self.time_hours -= 24.0
            self.day_count += 1
            return True  # новый день
        return False

    def get_sun_position(self):
        # солнце по кругу
        # 0 часов — полночь, 12 — полдень
        angle = (self.time_hours / 24.0) * 2*math.pi - math.pi/2
        x = math.cos(angle) * 1000
        y = math.sin(angle) * 1000
        z = 0
        return (x, y, z)

    def get_sun_intensity(self):
        # 0 ночью, 1 днём
        # синус
        angle = (self.time_hours / 24.0) * 2*math.pi - math.pi/2
        intensity = math.sin(angle)
        return max(0.0, intensity)

    def is_night(self):
        return self.time_hours < 6.0 or self.time_hours > 20.0

    def set_time(self, hour):
        self.time_hours = hour % 24.0

    def get_time_string(self):
        h = int(self.time_hours)
        m = int((self.time_hours - h)*60)
        return f"{h:02d}:{m:02d} Day {self.day_count}"
