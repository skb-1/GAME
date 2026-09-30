"""
AI животных — Behavior Trees + Utility AI.
Python 3.10.0
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Tuple
import math
import numpy as np
import random
from utils.math_utils import make_rng

# ---------- Utility AI ----------

@dataclass(slots=True)
class UtilityAction:
    name: str
    score_func: Callable[[Dict], float]  # функция оценки полезности от состояния
    action_func: Callable[[Dict], None]  # выполнение

    def get_score(self, state):
        try:
            return self.score_func(state)
        except:
            return 0.0

class UtilityAI:
    def __init__(self, actions: List[UtilityAction]):
        self.actions = actions

    def select_action(self, state):
        best = None
        best_score = -1.0
        for action in self.actions:
            score = action.get_score(state)
            if score > best_score:
                best_score = score
                best = action
        return best, best_score

# ---------- Behavior Tree ----------

class BTNode:
    def tick(self, blackboard):
        raise NotImplementedError

class BTSequence(BTNode):
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, blackboard):
        for child in self.children:
            status = child.tick(blackboard)
            if status != "success":
                return status
        return "success"

class BTSelector(BTNode):
    def __init__(self, children: List[BTNode]):
        self.children = children

    def tick(self, blackboard):
        for child in self.children:
            status = child.tick(blackboard)
            if status == "success":
                return "success"
        return "failure"

class BTCondition(BTNode):
    def __init__(self, condition_func):
        self.condition_func = condition_func

    def tick(self, blackboard):
        try:
            return "success" if self.condition_func(blackboard) else "failure"
        except:
            return "failure"

class BTAction(BTNode):
    def __init__(self, action_func):
        self.action_func = action_func

    def tick(self, blackboard):
        try:
            return self.action_func(blackboard)
        except Exception as e:
            print(f"[BTAction] error: {e}")
            return "failure"

# ---------- Animal State ----------

@dataclass(slots=True)
class AnimalState:
    animal_type: str
    position: np.ndarray
    health: float
    hunger: float  # 0..1, 1 = сыт
    thirst: float
    fear: float
    aggression: float
    target_position: Optional[np.ndarray] = None
    target_entity: Optional[str] = None
    is_pack: bool = False
    pack_members: List[str] = field(default_factory=list)
    memory_player: Dict = field(default_factory=dict)  # память об игроке
    time_of_day: float = 12.0
    last_eat_time: float = 0.0
    territory_center: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    territory_radius: float = 100.0

# ---------- Конкретные поведения ----------

def create_wolf_bt():
    """BT для волка — стайность, охота."""

    def is_player_near(bb):
        # bb: blackboard dict
        state = bb.get('state')
        player_pos = bb.get('player_pos')
        if state is None or player_pos is None:
            return False
        dist = np.linalg.norm(state.position - player_pos)
        return dist < 30.0

    def is_hungry(bb):
        state = bb.get('state')
        return state.hunger < 0.3 if state else False

    def is_injured(bb):
        state = bb.get('state')
        return state.health < 0.5 if state else False

    def action_flee(bb):
        state = bb.get('state')
        player_pos = bb.get('player_pos')
        if state and player_pos is not None:
            dir_away = state.position - player_pos
            dir_away = dir_away / (np.linalg.norm(dir_away)+1e-8)
            state.target_position = state.position + dir_away*20.0
            state.fear = min(1.0, state.fear+0.2)
        return "success"

    def action_hunt(bb):
        state = bb.get('state')
        player_pos = bb.get('player_pos')
        if state and player_pos is not None:
            # тактика окружения если стая
            if state.is_pack and len(state.pack_members) > 1:
                # окружаем
                # вычисляем угол для окружения
                pack_idx = bb.get('pack_index', 0)
                angle = (pack_idx / max(1, len(state.pack_members))) * 2*math.pi
                offset = np.array([math.cos(angle)*5, 0, math.sin(angle)*5], dtype=np.float32)
                state.target_position = player_pos + offset
            else:
                state.target_position = player_pos
        return "success"

    def action_eat(bb):
        state = bb.get('state')
        if state:
            state.hunger = min(1.0, state.hunger+0.5)
            state.target_position = None
        return "success"

    def action_patrol(bb):
        state = bb.get('state')
        if state:
            # случайная точка в территории
            rng = bb.get('rng')
            if rng is None:
                rng = random
            angle = rng.uniform(0, 2*math.pi)
            r = rng.uniform(0, state.territory_radius)
            state.target_position = state.territory_center + np.array([math.cos(angle)*r, 0, math.sin(angle)*r], dtype=np.float32)
        return "success"

    # Дерево:
    # Selector:
    #   Sequence: injured -> flee
    #   Sequence: player near and hungry/aggressive -> hunt
    #   Sequence: hungry -> eat (если есть еда) или patrol
    #   Patrol
    root = BTSelector([
        BTSequence([
            BTCondition(is_injured),
            BTAction(action_flee)
        ]),
        BTSequence([
            BTCondition(is_player_near),
            BTCondition(lambda bb: bb.get('state').aggression > 0.5 if bb.get('state') else False),
            BTAction(action_hunt)
        ]),
        BTSequence([
            BTCondition(is_hungry),
            BTAction(action_eat)
        ]),
        BTAction(action_patrol)
    ])
    return root

def create_deer_bt():
    """Олень — пугливый, травоядный."""

    def is_predator_near(bb):
        state = bb.get('state')
        player_pos = bb.get('player_pos')
        predator_positions = bb.get('predator_positions', [])
        if state is None:
            return False
        # проверяем игрока и хищников
        if player_pos is not None:
            if np.linalg.norm(state.position - player_pos) < 25.0:
                return True
        for pred_pos in predator_positions:
            if np.linalg.norm(state.position - pred_pos) < 30.0:
                return True
        return False

    def action_flee_fast(bb):
        state = bb.get('state')
        threat_pos = bb.get('player_pos')
        if state and threat_pos is not None:
            dir_away = state.position - threat_pos
            dir_away = dir_away / (np.linalg.norm(dir_away)+1e-8)
            state.target_position = state.position + dir_away*40.0
        return "success"

    def action_graze(bb):
        state = bb.get('state')
        if state:
            state.hunger = min(1.0, state.hunger+0.1)
        return "success"

    root = BTSelector([
        BTSequence([
            BTCondition(is_predator_near),
            BTAction(action_flee_fast)
        ]),
        BTAction(action_graze)
    ])
    return root

def create_bear_bt():
    """Медведь — территориальный, агрессивный если ранен или голоден."""

    def is_territory_invaded(bb):
        state = bb.get('state')
        player_pos = bb.get('player_pos')
        if state is None or player_pos is None:
            return False
        dist_to_center = np.linalg.norm(player_pos - state.territory_center)
        return dist_to_center < state.territory_radius*0.5

    def action_charge(bb):
        state = bb.get('state')
        player_pos = bb.get('player_pos')
        if state and player_pos is not None:
            state.target_position = player_pos
            state.aggression = 1.0
        return "success"

    root = BTSelector([
        BTSequence([
            BTCondition(is_territory_invaded),
            BTAction(action_charge)
        ]),
        BTAction(lambda bb: "success")
    ])
    return root

# ---------- Фабрика BT по типу ----------

def get_bt_for_animal(animal_type):
    if animal_type == "wolf":
        return create_wolf_bt()
    elif animal_type == "deer" or animal_type == "hare":
        return create_deer_bt()
    elif animal_type == "bear" or animal_type == "boar":
        return create_bear_bt()
    else:
        # дефолт — патруль
        return BTAction(lambda bb: "success")

# ---------- Animal AI Controller ----------

class AnimalAIController:
    def __init__(self, animal_type, seed=0, position=None, territory_center=None):
        self.animal_type = animal_type
        self.seed = seed
        self.rng = make_rng(seed)
        self.bt = get_bt_for_animal(animal_type)
        self.state = AnimalState(
            animal_type=animal_type,
            position=np.array(position, dtype=np.float32) if position is not None else np.zeros(3, dtype=np.float32),
            health=100.0,
            hunger=self.rng.uniform(0.5, 1.0),
            thirst=self.rng.uniform(0.5, 1.0),
            fear=0.0,
            aggression=self.rng.uniform(0.2, 0.8),
            territory_center=np.array(territory_center, dtype=np.float32) if territory_center is not None else np.zeros(3, dtype=np.float32),
            territory_radius=self.rng.uniform(50, 150)
        )
        # Utility AI для выбора высокоуровневой цели
        self.utility_ai = self._create_utility_ai()
        self.blackboard = {
            'state': self.state,
            'rng': self.rng,
            'player_pos': None,
            'predator_positions': [],
            'pack_index': 0,
        }
        self.time_since_last_decision = 0.0

    def _create_utility_ai(self):
        def score_hunt(state):
            # голод + агрессия
            return (1.0 - state['hunger']) * 0.6 + state['aggression']*0.4

        def score_flee(state):
            return state['fear']*0.8 + (1.0 - state['health']/100.0)*0.5

        def score_rest(state):
            return state['hunger']*0.3 + (state['health']/100.0)*0.3

        actions = [
            UtilityAction("hunt", lambda s: (1.0 - s['hunger'])*0.6 + s['aggression']*0.4, lambda s: None),
            UtilityAction("flee", lambda s: s['fear']*0.8 + (1.0 - s['health']/100.0)*0.5, lambda s: None),
            UtilityAction("patrol", lambda s: 0.3, lambda s: None),
        ]
        return UtilityAI(actions)

    def update(self, dt, player_pos=None, predator_positions=None, pack_members=None):
        self.time_since_last_decision += dt
        # обновляем blackboard
        self.blackboard['player_pos'] = np.array(player_pos, dtype=np.float32) if player_pos is not None else None
        self.blackboard['predator_positions'] = predator_positions if predator_positions else []
        if pack_members:
            self.state.is_pack = True
            self.state.pack_members = pack_members

        # принимаем решение каждые 0.5 сек
        if self.time_since_last_decision > 0.5:
            # Utility выбор
            state_dict = {
                'hunger': self.state.hunger,
                'health': self.state.health,
                'fear': self.state.fear,
                'aggression': self.state.aggression,
            }
            best_action, score = self.utility_ai.select_action(state_dict)
            # BT тик
            self.bt.tick(self.blackboard)
            self.time_since_last_decision = 0.0

        # движение к цели
        if self.state.target_position is not None:
            dir_vec = self.state.target_position - self.state.position
            dist = np.linalg.norm(dir_vec)
            if dist > 0.5:
                dir_norm = dir_vec / (dist+1e-8)
                speed = 3.0  # м/с, зависит от типа
                if self.animal_type == "wolf":
                    speed = 5.0
                elif self.animal_type == "deer":
                    speed = 6.0
                elif self.animal_type == "bear":
                    speed = 4.0
                elif self.animal_type == "hare":
                    speed = 7.0
                self.state.position += dir_norm * speed * dt
            else:
                self.state.target_position = None

        # потребности со временем
        self.state.hunger = max(0.0, self.state.hunger - dt*0.001)
        self.state.thirst = max(0.0, self.state.thirst - dt*0.0015)

        # реакция на звук, запах, свет — упрощённо
        # если игрок близко — увеличиваем fear или aggression
        if player_pos is not None:
            dist_to_player = np.linalg.norm(self.state.position - np.array(player_pos))
            if dist_to_player < 10.0:
                # запоминаем игрока
                self.state.memory_player['last_seen'] = {
                    'pos': np.array(player_pos),
                    'time': 0.0,
                }
                if self.animal_type in ["deer", "hare"]:
                    self.state.fear = min(1.0, self.state.fear + dt*0.5)
                elif self.animal_type in ["wolf", "bear", "boar"]:
                    self.state.aggression = min(1.0, self.state.aggression + dt*0.3)

        return self.state.position.copy()

    def take_damage(self, amount, from_pos=None):
        self.state.health -= amount
        self.state.fear = min(1.0, self.state.fear + 0.3)
        self.state.aggression = min(1.0, self.state.aggression + 0.2)
        if from_pos is not None:
            # убегать или атаковать
            if self.state.health < 30:
                dir_away = self.state.position - np.array(from_pos)
                dir_away = dir_away / (np.linalg.norm(dir_away)+1e-8)
                self.state.target_position = self.state.position + dir_away*30.0
            else:
                self.state.target_position = np.array(from_pos)

    def is_alive(self):
        return self.state.health > 0
