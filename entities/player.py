
"""
Игрок — процедурный гуманоид, выживание DayZ-стиль.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np
import math
from utils.math_utils import make_rng
from utils.procedural_mesh import generate_humanoid_full, MeshData
from utils.procedural_animation import generate_humanoid_skeleton, ProceduralAnimationGenerator, blend_animations
from survival.body_zones import BodyZones
from survival.needs import SurvivalNeeds
from items.inventory import Inventory
from config import SURVIVAL_CONFIG

@dataclass(slots=True)
class PlayerState:
    position: np.ndarray
    velocity: np.ndarray
    rotation: float  # yaw
    pitch: float
    is_crouching: bool
    is_running: bool
    is_sleeping: bool
    stamina: float
    health: float

class Player:
    def __init__(self, seed=0, start_pos=None):
        self.seed = seed
        self.rng = make_rng(seed)
        if start_pos is None:
            start_pos = np.array([0, 10, 0], dtype=np.float32)
        self.state = PlayerState(
            position=np.array(start_pos, dtype=np.float32),
            velocity=np.zeros(3, dtype=np.float32),
            rotation=0.0,
            pitch=0.0,
            is_crouching=False,
            is_running=False,
            is_sleeping=False,
            stamina=SURVIVAL_CONFIG["stamina_max"],
            health=SURVIVAL_CONFIG["max_hp"]
        )
        # процедурный гуманоид
        self.mesh = generate_humanoid_full(seed=seed, height=1.8)
        self.skeleton = generate_humanoid_skeleton(seed=seed, height=1.8)
        # анимации
        self.idle_anim = ProceduralAnimationGenerator.generate_idle_cycle(self.skeleton, seed=seed, frames=60)
        self.walk_anim = ProceduralAnimationGenerator.generate_walk_cycle(self.skeleton, speed=1.0, seed=seed, frames=30)
        self.run_anim = ProceduralAnimationGenerator.generate_run_cycle(self.skeleton, speed=2.0, seed=seed, frames=20)
        self.current_anim_frame = 0
        self.anim_blend = 0.0

        self.body_zones = BodyZones()
        self.needs = SurvivalNeeds()
        self.inventory = Inventory(max_weight=30.0, max_slots=20)

        self.physics_body_id = None

    def move(self, forward_input, right_input, dt, is_running=False, is_crouching=False):
        # forward_input: -1..1, right_input: -1..1
        self.state.is_running = is_running
        self.state.is_crouching = is_crouching

        # скорость
        base_speed = 3.0
        if is_running:
            base_speed = 6.0
            self.state.stamina = max(0.0, self.state.stamina - dt*10.0)
            if self.state.stamina <= 0:
                base_speed = 3.0
        else:
            self.state.stamina = min(SURVIVAL_CONFIG["stamina_max"], self.state.stamina + dt*5.0)

        if is_crouching:
            base_speed *= 0.5

        # направление по yaw
        yaw_rad = math.radians(self.state.rotation)
        forward_dir = np.array([math.sin(yaw_rad), 0, math.cos(yaw_rad)], dtype=np.float32)
        right_dir = np.array([math.cos(yaw_rad), 0, -math.sin(yaw_rad)], dtype=np.float32)

        move_vec = forward_dir*forward_input + right_dir*right_input
        if np.linalg.norm(move_vec) > 1e-6:
            move_vec = move_vec / np.linalg.norm(move_vec) * base_speed
            self.state.velocity[0] = move_vec[0]
            self.state.velocity[2] = move_vec[2]
        else:
            self.state.velocity[0] *= 0.9
            self.state.velocity[2] *= 0.9

        # гравитация
        self.state.velocity[1] -= 9.81*dt

        # позиция
        self.state.position += self.state.velocity*dt

        # анимация
        if np.linalg.norm(move_vec) > 0.1:
            if is_running:
                self.current_anim_frame = (self.current_anim_frame + dt*20) % len(self.run_anim)
            else:
                self.current_anim_frame = (self.current_anim_frame + dt*10) % len(self.walk_anim)
        else:
            self.current_anim_frame = (self.current_anim_frame + dt*5) % len(self.idle_anim)

    def look(self, delta_yaw, delta_pitch):
        self.state.rotation += delta_yaw
        self.state.pitch = max(-89.0, min(89.0, self.state.pitch + delta_pitch))

    def get_camera_pos(self):
        # камера на голове
        head_offset = np.array([0, 1.6, 0], dtype=np.float32)
        if self.state.is_crouching:
            head_offset[1] = 1.0
        return self.state.position + head_offset

    def get_camera_dir(self):
        yaw_rad = math.radians(self.state.rotation)
        pitch_rad = math.radians(self.state.pitch)
        dir_x = math.sin(yaw_rad)*math.cos(pitch_rad)
        dir_y = math.sin(pitch_rad)
        dir_z = math.cos(yaw_rad)*math.cos(pitch_rad)
        return np.array([dir_x, dir_y, dir_z], dtype=np.float32)

    def take_damage(self, amount, zone="torso"):
        self.body_zones.apply_damage(zone, amount)
        self.state.health = self.body_zones.get_total_health()
        # эффекты: боль, кровотечение
        return self.state.health <= 0

    def update(self, dt, world=None):
        self.needs.update(dt)
        # влияние потребностей на здоровье
        if self.needs.hunger < 0.2 or self.needs.thirst < 0.2:
            self.state.health -= dt*0.5
        # радиация
        if self.needs.radiation > 100:
            self.state.health -= dt * (self.needs.radiation/1000.0)

        # сон
        if self.state.is_sleeping:
            self.needs.fatigue = max(0.0, self.needs.fatigue - dt*0.1)
            self.state.health = min(SURVIVAL_CONFIG["max_hp"], self.state.health + dt*0.2)

    def get_anim_frame(self):
        # бленд между idle и walk/run
        vel = np.linalg.norm(self.state.velocity[[0,2]])
        if vel < 0.1:
            return self.idle_anim[int(self.current_anim_frame) % len(self.idle_anim)]
        elif self.state.is_running:
            return self.run_anim[int(self.current_anim_frame) % len(self.run_anim)]
        else:
            return self.walk_anim[int(self.current_anim_frame) % len(self.walk_anim)]

    def to_save_dict(self):
        return {
            "position": self.state.position.tolist(),
            "rotation": self.state.rotation,
            "pitch": self.state.pitch,
            "health": self.state.health,
            "stamina": self.state.stamina,
            "seed": self.seed,
            "body_zones": self.body_zones.to_dict(),
            "needs": self.needs.to_dict(),
            "inventory": self.inventory.to_dict(),
        }

    def from_save_dict(self, data):
        self.state.position = np.array(data["position"], dtype=np.float32)
        self.state.rotation = data["rotation"]
        self.state.pitch = data["pitch"]
        self.state.health = data["health"]
        self.state.stamina = data["stamina"]
        self.body_zones.from_dict(data["body_zones"])
        self.needs.from_dict(data["needs"])
        self.inventory.from_dict(data["inventory"])
