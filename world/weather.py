
import random
import math

class WeatherSystem:
    def __init__(self, seed=0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.current_weather = "clear"  # clear, rain, fog, storm, emission
        self.time_in_weather = 0.0
        self.weather_duration = self.rng.uniform(300, 900)  # сек
        self.wind_strength = 0.0
        self.rain_intensity = 0.0
        self.fog_density = 0.0

    def update(self, dt):
        self.time_in_weather += dt
        if self.time_in_weather > self.weather_duration:
            self.change_weather()
        # обновляем параметры
        if self.current_weather == "rain":
            self.rain_intensity = 0.5 + math.sin(self.time_in_weather*0.01)*0.3
            self.wind_strength = 0.3
        elif self.current_weather == "storm":
            self.rain_intensity = 1.0
            self.wind_strength = 1.0
        elif self.current_weather == "fog":
            self.fog_density = 0.6
            self.wind_strength = 0.1
        elif self.current_weather == "emission":
            self.fog_density = 0.9
            self.wind_strength = 0.0
        else:
            self.rain_intensity *= 0.99
            self.fog_density *= 0.99
            self.wind_strength *= 0.99

    def change_weather(self):
        choices = ["clear", "clear", "clear", "rain", "fog", "storm"]
        # emission редко
        if self.rng.random() < 0.02:
            choices.append("emission")
        self.current_weather = self.rng.choice(choices)
        self.time_in_weather = 0.0
        self.weather_duration = self.rng.uniform(200, 800)

    def set_weather(self, weather_type):
        self.current_weather = weather_type
        self.time_in_weather = 0.0

    def get_sky_color(self):
        if self.current_weather == "clear":
            return (0.5, 0.7, 1.0)
        elif self.current_weather == "rain":
            return (0.4, 0.4, 0.5)
        elif self.current_weather == "fog":
            return (0.6, 0.6, 0.6)
        elif self.current_weather == "storm":
            return (0.2, 0.2, 0.3)
        elif self.current_weather == "emission":
            return (0.8, 0.3, 0.1)
        return (0.5, 0.7, 1.0)
