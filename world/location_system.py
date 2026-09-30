"""
Система локаций Сталкера — разделение карты на отдельные локации с переходами.
Оптимизация CPU: только активная локация полностью загружена, остальные выгружены.

Локации по мотивам S.T.A.L.K.E.R.:
- Кордон, Свалка, Агропром, Тёмная долина, Бар, Дикая территория, Янтарь,
  Армейские склады, Рыжий лес, Припять, Завод Юпитер, Затон, Скадовск, Саркофаг

Каждая локация:
- Свой seed (world_seed + offset)
- Свой размер, радиация, биомы, сложность
- Свои чанки, аномалии, артефакты, животные
- Точки переходов (порталы) в другие локации

Переходы снижают потребление CPU в 5-10 раз vs одна большая карта.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import time
from utils.math_utils import make_rng
from utils.logger import get_logger, LogCategory

@dataclass(slots=True)
class LocationTransition:
    """Точка перехода между локациями."""
    target_location_id: str
    position: np.ndarray  # позиция в текущей локации
    radius: float = 5.0
    name: str = "Переход"
    requires_item: Optional[str] = None  # например ключ
    radiation_required: float = 0.0  # минимальная радиация? или защита

    def is_player_near(self, player_pos, radius_multiplier=1.0):
        dist = np.linalg.norm(self.position - np.array(player_pos))
        return dist < self.radius * radius_multiplier

@dataclass(slots=True)
class LocationDefinition:
    """Определение локации."""
    location_id: str
    name: str
    display_name: str
    description: str
    size_chunks: Tuple[int, int]  # (width, height) в чанках
    radiation_level: float  # 0..1 базовый уровень
    difficulty: int  # 1..10
    biome_weights: Dict[str, float]  # веса биомов
    seed_offset: int
    connections: List[str]  # id связанных локаций
    has_trader: bool = False
    has_anomalies: bool = True
    has_mutants: bool = True
    is_underground: bool = False
    music_track: Optional[str] = None

    def get_world_size_meters(self, chunk_size=32):
        return (self.size_chunks[0]*chunk_size, self.size_chunks[1]*chunk_size)

# ---------- Определения всех локаций ----------

LOCATION_DEFINITIONS: Dict[str, LocationDefinition] = {
    "cordon": LocationDefinition(
        location_id="cordon",
        name="cordon",
        display_name="Кордон",
        description="Южная окраина Зоны. Относительно безопасно, много новичков. База военных на юге.",
        size_chunks=(20, 20),
        radiation_level=0.1,
        difficulty=1,
        biome_weights={"field": 0.5, "forest": 0.4, "wasteland": 0.1},
        seed_offset=0,
        connections=["garbage", "dark_valley"],
        has_trader=True,
        has_anomalies=True,
    ),
    "garbage": LocationDefinition(
        location_id="garbage",
        name="garbage",
        display_name="Свалка",
        description="Огромная свалка техники и мусора. Много аномалий, бандиты.",
        size_chunks=(18, 18),
        radiation_level=0.3,
        difficulty=2,
        biome_weights={"wasteland": 0.6, "field": 0.2, "forest": 0.2},
        seed_offset=100,
        connections=["cordon", "agroprom", "dark_valley", "bar"],
        has_anomalies=True,
    ),
    "agroprom": LocationDefinition(
        location_id="agroprom",
        name="agroprom",
        display_name="НИИ Агропром",
        description="Заброшенный НИИ, подземелья с кровососами. База Долга.",
        size_chunks=(16, 16),
        radiation_level=0.4,
        difficulty=3,
        biome_weights={"forest": 0.4, "swamp": 0.3, "wasteland": 0.3},
        seed_offset=200,
        connections=["garbage", "yantar", "bar"],
        has_anomalies=True,
        has_mutants=True,
    ),
    "dark_valley": LocationDefinition(
        location_id="dark_valley",
        name="dark_valley",
        display_name="Тёмная долина",
        description="База бандитов и фабрика. Высокая концентрация аномалий.",
        size_chunks=(16, 16),
        radiation_level=0.35,
        difficulty=3,
        biome_weights={"wasteland": 0.5, "forest": 0.3, "swamp": 0.2},
        seed_offset=300,
        connections=["cordon", "garbage", "army_warehouses"],
        has_anomalies=True,
    ),
    "bar": LocationDefinition(
        location_id="bar",
        name="bar",
        display_name="Бар '100 Рентген'",
        description="Безопасная зона, бар сталкеров. Торговцы, задания.",
        size_chunks=(14, 14),
        radiation_level=0.05,
        difficulty=1,
        biome_weights={"field": 0.6, "forest": 0.4},
        seed_offset=400,
        connections=["garbage", "agroprom", "wild_territory", "army_warehouses"],
        has_trader=True,
        has_anomalies=False,
        has_mutants=False,
    ),
    "wild_territory": LocationDefinition(
        location_id="wild_territory",
        name="wild_territory",
        display_name="Дикая территория",
        description="Завод Росток, много аномалий и мутантов. Опасно.",
        size_chunks=(18, 18),
        radiation_level=0.5,
        difficulty=4,
        biome_weights={"wasteland": 0.7, "forest": 0.2, "swamp": 0.1},
        seed_offset=500,
        connections=["bar", "yantar", "army_warehouses"],
        has_anomalies=True,
    ),
    "yantar": LocationDefinition(
        location_id="yantar",
        name="yantar",
        display_name="Янтарь",
        description="Завод с пси-излучением. Лаборатория X16. Очень опасно без защиты.",
        size_chunks=(16, 16),
        radiation_level=0.7,
        difficulty=6,
        biome_weights={"swamp": 0.5, "wasteland": 0.4, "forest": 0.1},
        seed_offset=600,
        connections=["agroprom", "wild_territory", "red_forest"],
        has_anomalies=True,
        has_mutants=True,
        is_underground=False,
    ),
    "army_warehouses": LocationDefinition(
        location_id="army_warehouses",
        name="army_warehouses",
        display_name="Армейские склады",
        description="Бывшая военная база, теперь база Свободы. Много мутантов.",
        size_chunks=(20, 20),
        radiation_level=0.4,
        difficulty=4,
        biome_weights={"field": 0.4, "forest": 0.5, "wasteland": 0.1},
        seed_offset=700,
        connections=["dark_valley", "bar", "wild_territory", "red_forest"],
        has_anomalies=True,
    ),
    "red_forest": LocationDefinition(
        location_id="red_forest",
        name="red_forest",
        display_name="Рыжий лес",
        description="Лес, погибший от радиации. Высокая радиация, много аномалий. Путь к ЧАЭС.",
        size_chunks=(22, 22),
        radiation_level=0.85,
        difficulty=7,
        biome_weights={"red_forest": 0.8, "wasteland": 0.2},
        seed_offset=800,
        connections=["yantar", "army_warehouses", "pripyat", "jupiter"],
        has_anomalies=True,
        has_mutants=True,
    ),
    "pripyat": LocationDefinition(
        location_id="pripyat",
        name="pripyat",
        display_name="Припять",
        description="Мёртвый город. Многоэтажки, высокая радиация, монолитовцы и мутанты.",
        size_chunks=(24, 24),
        radiation_level=0.9,
        difficulty=8,
        biome_weights={"wasteland": 0.8, "red_forest": 0.2},
        seed_offset=900,
        connections=["red_forest", "jupiter", "sarcophagus"],
        has_anomalies=True,
        has_mutants=True,
    ),
    "jupiter": LocationDefinition(
        location_id="jupiter",
        name="jupiter",
        display_name="Завод 'Юпитер'",
        description="Заброшенный завод, рядом Затон. Много аномалий, артефактов.",
        size_chunks=(20, 20),
        radiation_level=0.6,
        difficulty=6,
        biome_weights={"wasteland": 0.6, "swamp": 0.2, "forest": 0.2},
        seed_offset=1000,
        connections=["red_forest", "pripyat", "zaton", "sarcophagus"],
        has_anomalies=True,
    ),
    "zaton": LocationDefinition(
        location_id="zaton",
        name="zaton",
        display_name="Затон",
        description="Болотистая местность с кораблями. База Скадовск.",
        size_chunks=(20, 20),
        radiation_level=0.45,
        difficulty=5,
        biome_weights={"swamp": 0.7, "wasteland": 0.2, "forest": 0.1},
        seed_offset=1100,
        connections=["jupiter", "skadovsk"],
        has_trader=True,
        has_anomalies=True,
    ),
    "skadovsk": LocationDefinition(
        location_id="skadovsk",
        name="skadovsk",
        display_name="Скадовск",
        description="Корабль-бар на болотах. Безопасная зона.",
        size_chunks=(10, 10),
        radiation_level=0.05,
        difficulty=1,
        biome_weights={"swamp": 0.5, "field": 0.5},
        seed_offset=1200,
        connections=["zaton"],
        has_trader=True,
        has_anomalies=False,
        has_mutants=False,
    ),
    "sarcophagus": LocationDefinition(
        location_id="sarcophagus",
        name="sarcophagus",
        display_name="Саркофаг ЧАЭС",
        description="Сердце Зоны. 4-й энергоблок, саркофаг. Максимальная радиация, уникальные аномалии и мутанты. Финальная локация.",
        size_chunks=(16, 16),
        radiation_level=1.0,
        difficulty=10,
        biome_weights={"wasteland": 1.0},
        seed_offset=1300,
        connections=["pripyat", "jupiter"],
        has_anomalies=True,
        has_mutants=True,
        is_underground=True,
    ),
}

@dataclass(slots=True)
class LocationInstance:
    """Экземпляр загруженной локации."""
    definition: LocationDefinition
    world_seed: int
    is_loaded: bool = False
    is_active: bool = False
    chunk_system: Optional[object] = None
    spawn_manager: Optional[object] = None
    anomaly_system: Optional[object] = None
    artifact_system: Optional[object] = None
    radiation_map: Optional[object] = None
    transitions: List[LocationTransition] = field(default_factory=list)
    load_time: float = 0.0
    entity_count: int = 0
    visit_count: int = 0

    def get_effective_seed(self):
        return self.world_seed + self.definition.seed_offset

class LocationSystem:
    """Система управления локациями."""

    def __init__(self, world_seed=1337, chunk_size=32):
        self.world_seed = world_seed
        self.chunk_size = chunk_size
        self.logger = get_logger()
        self.locations: Dict[str, LocationInstance] = {}
        self.active_location_id: Optional[str] = None
        self.previous_location_id: Optional[str] = None
        self.transition_in_progress = False

        # Инициализируем все локации как незагруженные
        for loc_id, loc_def in LOCATION_DEFINITIONS.items():
            self.locations[loc_id] = LocationInstance(
                definition=loc_def,
                world_seed=world_seed,
            )
            # Генерируем переходы
            self._generate_transitions_for_location(loc_id)

        self.logger.log_location(f"LocationSystem инициализирован, {len(self.locations)} локаций, seed={world_seed}")

    def _generate_transitions_for_location(self, location_id):
        """Генерация точек перехода для локации."""
        loc = self.locations[location_id]
        rng = make_rng(loc.get_effective_seed() + 9999)
        transitions = []

        size_x, size_z = loc.definition.get_world_size_meters(self.chunk_size)
        # Для каждой связанной локации — точка перехода на краю карты
        for i, target_id in enumerate(loc.definition.connections):
            # Позиция на краю, равномерно распределённая
            angle = (i / len(loc.definition.connections)) * 2 * 3.14159
            # На краю карты
            edge_x = (size_x * 0.4) * np.cos(angle)
            edge_z = (size_z * 0.4) * np.sin(angle)
            # Высота — позже из chunk_system
            pos = np.array([edge_x, 0, edge_z], dtype=np.float32)

            trans = LocationTransition(
                target_location_id=target_id,
                position=pos,
                radius=8.0,
                name=f"Переход в {LOCATION_DEFINITIONS[target_id].display_name}",
            )
            transitions.append(trans)

        loc.transitions = transitions
        self.logger.log_location(f"Сгенерировано {len(transitions)} переходов для {location_id}: {[t.target_location_id for t in transitions]}")

    def get_location(self, location_id) -> Optional[LocationInstance]:
        return self.locations.get(location_id)

    def get_active_location(self) -> Optional[LocationInstance]:
        if self.active_location_id:
            return self.locations.get(self.active_location_id)
        return None

    def load_location(self, location_id, force_reload=False):
        """Загрузка локации (ленивая, только когда игрок входит)."""
        if location_id not in self.locations:
            self.logger.error(LogCategory.LOCATION, f"Локация {location_id} не найдена!")
            return None

        loc = self.locations[location_id]

        if loc.is_loaded and not force_reload:
            self.logger.log_location(f"Локация {location_id} уже загружена")
            return loc

        start = time.time()
        self.logger.log_location(f"Загрузка локации {location_id} ({loc.definition.display_name})...")

        # Импорты здесь чтобы избежать циклов
        from world.chunk_system import ChunkSystem
        from spawn.spawn_manager import SpawnManager
        from anomalies.anomaly_system import AnomalySystem
        from anomalies.artifact_system import ArtifactSystem
        from radiation.radiation_map import RadiationMap

        effective_seed = loc.get_effective_seed()

        # Чанковая система для этой локации
        loc.chunk_system = ChunkSystem(world_seed=effective_seed)
        loc.chunk_system.start_workers()
        # Запросить центральные чанки
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                loc.chunk_system.request_chunk(dx, dz)

        # Спавн, аномалии и т.д.
        loc.spawn_manager = SpawnManager(world_seed=effective_seed, chunk_system=loc.chunk_system)
        loc.anomaly_system = AnomalySystem(world_seed=effective_seed)
        loc.artifact_system = ArtifactSystem(world_seed=effective_seed)
        loc.radiation_map = RadiationMap(world_seed=effective_seed)

        # Настройка радиации по уровню локации
        # Увеличиваем hotspots в зависимости от radiation_level
        loc.radiation_map.hotspots = []  # очищаем
        # Добавляем hotspots пропорционально уровню радиации
        num_hotspots = int(loc.definition.radiation_level * 20) + 5
        rng = make_rng(effective_seed)
        import math
        for _ in range(num_hotspots):
            angle = rng.uniform(0, 2*math.pi)
            r = rng.uniform(0, loc.definition.size_chunks[0]*self.chunk_size*0.4)
            x = math.cos(angle)*r
            z = math.sin(angle)*r
            intensity = rng.uniform(5, 50) * loc.definition.radiation_level
            radius = rng.uniform(20, 80)
            loc.radiation_map.hotspots.append({
                "pos": np.array([x, z], dtype=np.float32),
                "intensity": intensity,
                "radius": radius
            })

        # Спавн начальных аномалий
        loc.anomaly_system.respawn_daily(loc.chunk_system, 0)

        # Спавн животных по биомам локации
        # Количество зависит от биома и сложности
        for _ in range(5 + loc.definition.difficulty):
            # случайная позиция
            x = rng.uniform(-loc.definition.size_chunks[0]*self.chunk_size*0.3, loc.definition.size_chunks[0]*self.chunk_size*0.3)
            z = rng.uniform(-loc.definition.size_chunks[1]*self.chunk_size*0.3, loc.definition.size_chunks[1]*self.chunk_size*0.3)
            # выбор животного по весам биомов
            # Упрощённо — из всех типов
            animal_types = ["wolf", "boar", "deer", "hare", "raven", "snake", "bear"]
            # В сложных локациях больше мутантов
            if loc.definition.difficulty > 5:
                animal_types = ["wolf", "bear", "boar", "snake"]
            atype = rng.choice(animal_types)
            loc.spawn_manager.spawn_animal(atype, position=np.array([x, 10, z], dtype=np.float32))

        loc.is_loaded = True
        loc.load_time = time.time() - start
        loc.visit_count += 1

        self.logger.log_location(f"Локация {location_id} загружена за {loc.load_time:.2f}с, чанков={len(loc.chunk_system.chunks)}, аномалий={len(loc.anomaly_system.anomalies)}, животных={len(loc.spawn_manager.animals)}")

        return loc

    def unload_location(self, location_id):
        """Выгрузка локации для экономии RAM/CPU."""
        if location_id not in self.locations:
            return

        loc = self.locations[location_id]
        if not loc.is_loaded:
            return

        if loc.is_active:
            self.logger.warning(LogCategory.LOCATION, f"Попытка выгрузить активную локацию {location_id}!")
            return

        self.logger.log_location(f"Выгрузка локации {location_id}...")

        if loc.chunk_system:
            loc.chunk_system.stop_workers()
            loc.chunk_system = None
        loc.spawn_manager = None
        loc.anomaly_system = None
        loc.artifact_system = None
        loc.radiation_map = None
        loc.is_loaded = False

        # Очистка кэша
        from utils.asset_cache import global_cache
        # Не очищаем весь кэш, только статистику
        self.logger.log_location(f"Локация {location_id} выгружена, RAM освобождена")

    def set_active_location(self, location_id):
        """Сделать локацию активной (игрок входит)."""
        if location_id not in self.locations:
            self.logger.error(LogCategory.LOCATION, f"Локация {location_id} не найдена!")
            return None

        # Выгружаем предыдущую активную если она не связана напрямую (оптимизация)
        # Оставляем в памяти соседние локации для быстрого перехода
        if self.active_location_id and self.active_location_id != location_id:
            prev_loc = self.locations[self.active_location_id]
            # Если новая локация не связана с предыдущей — выгружаем предыдущую
            if location_id not in prev_loc.definition.connections:
                # Выгружаем все кроме соседей новой локации
                new_loc_def = self.locations[location_id].definition
                keep_ids = set(new_loc_def.connections + [location_id])
                for loc_id, loc in self.locations.items():
                    if loc.is_loaded and loc_id not in keep_ids:
                        self.unload_location(loc_id)

            prev_loc.is_active = False
            self.previous_location_id = self.active_location_id

        # Загружаем новую если не загружена
        loc = self.load_location(location_id)

        loc.is_active = True
        self.active_location_id = location_id

        self.logger.log_location(f"Активная локация: {location_id} ({loc.definition.display_name}), предыдущая: {self.previous_location_id}")

        return loc

    def check_transitions(self, player_pos):
        """Проверка близости к переходам, возвращает target_location_id если игрок рядом."""
        active = self.get_active_location()
        if not active:
            return None

        for trans in active.transitions:
            if trans.is_player_near(player_pos):
                self.logger.log_location(f"Игрок рядом с переходом {trans.name} -> {trans.target_location_id}, дистанция {np.linalg.norm(trans.position - np.array(player_pos)):.1f}м")
                return trans.target_location_id, trans

        return None

    def get_location_info(self, location_id):
        """Информация для UI."""
        loc = self.locations.get(location_id)
        if not loc:
            return None
        return {
            "id": loc.definition.location_id,
            "display_name": loc.definition.display_name,
            "description": loc.definition.description,
            "radiation": loc.definition.radiation_level,
            "difficulty": loc.definition.difficulty,
            "size": loc.definition.size_chunks,
            "connections": loc.definition.connections,
            "is_loaded": loc.is_loaded,
            "is_active": loc.is_active,
            "visit_count": loc.visit_count,
            "transitions": [{"target": t.target_location_id, "name": t.name, "pos": t.position.tolist()} for t in loc.transitions]
        }

    def get_all_locations_info(self):
        return {loc_id: self.get_location_info(loc_id) for loc_id in self.locations}

    def get_map_graph(self):
        """Граф локаций для карты."""
        graph = {}
        for loc_id, loc_def in LOCATION_DEFINITIONS.items():
            graph[loc_id] = {
                "name": loc_def.display_name,
                "connections": loc_def.connections,
                "radiation": loc_def.radiation_level,
                "difficulty": loc_def.difficulty,
            }
        return graph

    def to_save_dict(self):
        return {
            "active_location": self.active_location_id,
            "previous_location": self.previous_location_id,
            "locations": {
                loc_id: {
                    "is_loaded": loc.is_loaded,
                    "visit_count": loc.visit_count,
                } for loc_id, loc in self.locations.items()
            }
        }

    def from_save_dict(self, data):
        self.active_location_id = data.get("active_location")
        self.previous_location_id = data.get("previous_location")
        for loc_id, loc_data in data.get("locations", {}).items():
            if loc_id in self.locations:
                self.locations[loc_id].visit_count = loc_data.get("visit_count", 0)
                # is_loaded не восстанавливаем — перезагрузим при необходимости
