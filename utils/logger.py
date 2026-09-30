"""
Подробное логгирование всего процесса игры.
Python 3.10.0 совместимость.

Уровни:
- DEBUG: детальная отладка (шум, меши, чанки)
- INFO: общая информация (загрузка локаций, спавн)
- WARNING: предупреждения (низкий FPS, RAM)
- ERROR: ошибки
- CRITICAL: критические сбои

Категории:
- RENDER, PHYSICS, WORLD, ENTITY, ANOMALY, RADIATION, SAVE, UI, AUDIO, OPTIMIZATION, LOCATION, MENU

Вывод в терминал с цветами (Windows/Linux) + в файл game.log
"""
import os
import sys
import time
import threading
from datetime import datetime
from typing import Optional
from enum import Enum

class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class LogCategory(Enum):
    GENERAL = "GENERAL"
    RENDER = "RENDER"
    PHYSICS = "PHYSICS"
    WORLD = "WORLD"
    ENTITY = "ENTITY"
    ANOMALY = "ANOMALY"
    RADIATION = "RADIATION"
    SAVE = "SAVE"
    UI = "UI"
    MENU = "MENU"
    AUDIO = "AUDIO"
    OPTIMIZATION = "OPTIMIZATION"
    LOCATION = "LOCATION"
    TERRAIN = "TERRAIN"
    SPAWN = "SPAWN"
    INVENTORY = "INVENTORY"
    CONSOLE = "CONSOLE"

# ANSI цвета для терминала
COLORS = {
    LogLevel.DEBUG: "\033[36m",      # cyan
    LogLevel.INFO: "\033[32m",       # green
    LogLevel.WARNING: "\033[33m",    # yellow
    LogLevel.ERROR: "\033[31m",      # red
    LogLevel.CRITICAL: "\033[35m\033[1m",  # magenta bold
}

CATEGORY_COLORS = {
    LogCategory.RENDER: "\033[94m",
    LogCategory.PHYSICS: "\033[95m",
    LogCategory.WORLD: "\033[92m",
    LogCategory.LOCATION: "\033[93m",
    LogCategory.MENU: "\033[96m",
    LogCategory.ENTITY: "\033[91m",
}

RESET = "\033[0m"

class GameLogger:
    def __init__(self, log_file="game.log", level=LogLevel.DEBUG, enable_file=True, enable_console=True, enable_colors=True):
        self.level = level
        self.enable_file = enable_file
        self.enable_console = enable_console
        self.enable_colors = enable_colors and sys.stdout.isatty()
        self.log_file = log_file
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.log_count = {lvl: 0 for lvl in LogLevel}

        # Очищаем старый лог
        if self.enable_file:
            try:
                with open(self.log_file, "w", encoding="utf-8") as f:
                    f.write(f"=== STALKERcraft Log Started {datetime.now()} ===\n")
                    f.write(f"Python {sys.version}\n")
                    f.write(f"Platform {sys.platform}\n")
                    f.write("="*60 + "\n")
            except Exception as e:
                print(f"[Logger] Не удалось создать лог файл: {e}")
                self.enable_file = False

        self.info(LogCategory.GENERAL, f"Логгер инициализирован, уровень={level.name}, файл={log_file}")

    def _format_message(self, level: LogLevel, category: LogCategory, message: str, detailed: bool = True):
        elapsed = time.time() - self.start_time
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        thread_name = threading.current_thread().name

        if detailed:
            formatted = f"[{timestamp}] [{elapsed:8.2f}s] [{level.name:8s}] [{category.value:12s}] [{thread_name:12s}] {message}"
        else:
            formatted = f"[{level.name}] [{category.value}] {message}"

        return formatted

    def _write(self, level: LogLevel, category: LogCategory, message: str):
        if level.value < self.level.value:
            return

        with self.lock:
            self.log_count[level] += 1
            formatted = self._format_message(level, category, message)

            # Консоль с цветами
            if self.enable_console:
                if self.enable_colors:
                    level_color = COLORS.get(level, "")
                    cat_color = CATEGORY_COLORS.get(category, "")
                    colored = f"{level_color}{formatted}{RESET}"
                    # Добавляем цвет категории если есть
                    print(colored)
                else:
                    print(formatted)

            # Файл
            if self.enable_file:
                try:
                    with open(self.log_file, "a", encoding="utf-8") as f:
                        f.write(formatted + "\n")
                except Exception as e:
                    print(f"[Logger] Ошибка записи в файл: {e}")

    def debug(self, category: LogCategory, message: str):
        self._write(LogLevel.DEBUG, category, message)

    def info(self, category: LogCategory, message: str):
        self._write(LogLevel.INFO, category, message)

    def warning(self, category: LogCategory, message: str):
        self._write(LogLevel.WARNING, category, message)

    def error(self, category: LogCategory, message: str):
        self._write(LogLevel.ERROR, category, message)

    def critical(self, category: LogCategory, message: str):
        self._write(LogLevel.CRITICAL, category, message)

    # Удобные методы для конкретных систем
    def log_render(self, message, level=LogLevel.DEBUG):
        self._write(level, LogCategory.RENDER, message)

    def log_physics(self, message, level=LogLevel.DEBUG):
        self._write(level, LogCategory.PHYSICS, message)

    def log_world(self, message, level=LogLevel.INFO):
        self._write(level, LogCategory.WORLD, message)

    def log_location(self, message, level=LogLevel.INFO):
        self._write(level, LogCategory.LOCATION, message)

    def log_entity(self, message, level=LogLevel.DEBUG):
        self._write(level, LogCategory.ENTITY, message)

    def log_menu(self, message, level=LogLevel.INFO):
        self._write(level, LogCategory.MENU, message)

    def log_optimization(self, message, level=LogLevel.DEBUG):
        self._write(level, LogCategory.OPTIMIZATION, message)

    def log_terrain(self, message, level=LogLevel.DEBUG):
        self._write(level, LogCategory.TERRAIN, message)

    def log_spawn(self, message, level=LogLevel.INFO):
        self._write(level, LogCategory.SPAWN, message)

    def log_anomaly(self, message, level=LogLevel.INFO):
        self._write(level, LogCategory.ANOMALY, message)

    def get_stats(self):
        return dict(self.log_count)

    def shutdown(self):
        self.info(LogCategory.GENERAL, f"Логгер завершает работу. Статистика: {self.log_count}")
        self.info(LogCategory.GENERAL, f"Время работы: {time.time()-self.start_time:.2f}с")

# Глобальный логгер
_global_logger: Optional[GameLogger] = None

def get_logger():
    global _global_logger
    if _global_logger is None:
        _global_logger = GameLogger()
    return _global_logger

def init_logger(log_file="game.log", level=LogLevel.DEBUG):
    global _global_logger
    _global_logger = GameLogger(log_file=log_file, level=level)
    return _global_logger

# Удобные короткие функции
def log_debug(cat, msg):
    get_logger().debug(cat, msg)

def log_info(cat, msg):
    get_logger().info(cat, msg)

def log_warning(cat, msg):
    get_logger().warning(cat, msg)

def log_error(cat, msg):
    get_logger().error(cat, msg)
