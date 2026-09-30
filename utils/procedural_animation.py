"""
Процедурная анимация — скелет, IK, синусоидальные циклы, блендинг.
Python 3.10.0 совместимость.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math
import numpy as np
from .math_utils import make_rng

@dataclass(slots=True)
class Bone:
    name: str
    parent: Optional[str]  # имя родителя или None для root
    length: float
    position: np.ndarray  # (3,) локальная позиция относительно родителя
    rotation: np.ndarray  # (3,) Euler в радианах
    children: List[str] = field(default_factory=list)

@dataclass(slots=True)
class Skeleton:
    bones: Dict[str, Bone]
    root: str
    seed: int = 0

    def get_bone_chain(self, end_bone_name):
        """Цепочка от root до end_bone."""
        chain = []
        curr = end_bone_name
        while curr is not None:
            chain.append(curr)
            b = self.bones.get(curr)
            if b is None:
                break
            curr = b.parent
        chain.reverse()
        return chain

    def compute_world_positions(self, local_rotations=None):
        """Вычисление мировых позиций костей (forward kinematics)."""
        if local_rotations is None:
            local_rotations = {}
        world_pos = {}
        world_rot = {}

        def compute_bone(name, parent_pos, parent_rot):
            bone = self.bones[name]
            # локальная ротация
            rot = local_rotations.get(name, bone.rotation)
            # мировая ротация = parent_rot + rot (упрощённо Euler)
            w_rot = parent_rot + rot if parent_rot is not None else rot
            # позиция: parent_pos + rotated(local_pos)
            # упрощённо без кватернионов — поворот вокруг Y
            # Для простоты используем матрицу поворота Y
            # Но для скелета достаточно сложить
            if parent_pos is None:
                w_pos = bone.position.copy()
            else:
                # повернуть bone.position на parent_rot
                # только Y для упрощения
                cos_y = math.cos(parent_rot[1])
                sin_y = math.sin(parent_rot[1])
                x = bone.position[0]*cos_y - bone.position[2]*sin_y
                z = bone.position[0]*sin_y + bone.position[2]*cos_y
                w_pos = parent_pos + np.array([x, bone.position[1], z], dtype=np.float32)
            world_pos[name] = w_pos
            world_rot[name] = w_rot
            for child_name in bone.children:
                compute_bone(child_name, w_pos, w_rot)

        compute_bone(self.root, None, np.zeros(3, dtype=np.float32))
        return world_pos, world_rot

# ---------- IK Solver — FABRIK ----------

class FABRIKSolver:
    """FABRIK IK для цепочки костей."""

    @staticmethod
    def solve(chain_positions, target, tolerance=0.01, max_iters=20):
        """
        chain_positions: List[np.ndarray] (N,3) — мировые позиции суставов от root до end
        target: (3,) цель для end effector
        Возвращает новые позиции.
        """
        n = len(chain_positions)
        if n < 2:
            return chain_positions

        # длины сегментов
        lengths = []
        for i in range(n-1):
            lengths.append(np.linalg.norm(chain_positions[i+1]-chain_positions[i]))
        total_len = sum(lengths)

        # если цель недостижима — вытянуть в сторону цели
        root = chain_positions[0].copy()
        dist_to_target = np.linalg.norm(target - root)
        if dist_to_target > total_len:
            # вытянуть
            new_positions = [root.copy()]
            dir_vec = (target - root) / (dist_to_target+1e-8)
            for i in range(n-1):
                new_pos = new_positions[-1] + dir_vec * lengths[i]
                new_positions.append(new_pos)
            return new_positions

        # иначе итерации FABRIK
        positions = [p.copy() for p in chain_positions]

        for _ in range(max_iters):
            # backward
            positions[-1] = target.copy()
            for i in range(n-2, -1, -1):
                dir_vec = positions[i] - positions[i+1]
                l = np.linalg.norm(dir_vec)
                if l < 1e-8:
                    continue
                dir_vec /= l
                positions[i] = positions[i+1] + dir_vec * lengths[i]

            # forward
            positions[0] = root.copy()
            for i in range(n-1):
                dir_vec = positions[i+1] - positions[i]
                l = np.linalg.norm(dir_vec)
                if l < 1e-8:
                    continue
                dir_vec /= l
                positions[i+1] = positions[i] + dir_vec * lengths[i]

            if np.linalg.norm(positions[-1]-target) < tolerance:
                break

        return positions

# ---------- Процедурные циклы анимации ----------

class ProceduralAnimationGenerator:
    """Генератор ключевых кадров процедурно."""

    @staticmethod
    def generate_walk_cycle(skeleton, speed=1.0, stride_length=0.8, seed=0, frames=30):
        """
        Генерация цикла ходьбы через синусоиды.
        Возвращает List[Dict[bone_name, rotation(3,)]] — кадры.
        """
        rng = make_rng(seed)
        keyframes = []
        for f in range(frames):
            t = (f / frames) * 2*math.pi  # 0..2pi
            local_rots = {}
            # ноги: противофаза
            left_leg_phase = math.sin(t * speed)
            right_leg_phase = math.sin(t * speed + math.pi)

            # бедро вперёд-назад
            left_leg_phase_rad = left_leg_phase * 0.6  # ~35 градусов
            right_leg_phase_rad = right_leg_phase * 0.6

            # колено сгибается при подъёме
            left_knee = max(0, -left_leg_phase) * 0.8
            right_knee = max(0, -right_leg_phase) * 0.8

            # руки в противофазе ногам
            left_arm_phase = math.sin(t * speed + math.pi) * 0.5
            right_arm_phase = math.sin(t * speed) * 0.5

            # применяем к костям если они есть
            for bone_name in skeleton.bones:
                if "left_leg" in bone_name.lower() or "l_leg" in bone_name.lower() or "leg_l" in bone_name.lower():
                    if "upper" in bone_name.lower() or "thigh" in bone_name.lower() or bone_name.lower().endswith("leg_l") or "left" in bone_name.lower() and "upper" not in bone_name.lower():
                        # упрощённо — все левые ноги
                        pass
                # универсально: ищем по имени
                lname = bone_name.lower()
                if "thigh_l" in lname or "upperleg_l" in lname or (("leg" in lname and "_l" in lname) and "shin" not in lname and "foot" not in lname):
                    local_rots[bone_name] = np.array([left_leg_phase_rad, 0, 0], dtype=np.float32)
                elif "thigh_r" in lname or "upperleg_r" in lname or (("leg" in lname and "_r" in lname) and "shin" not in lname and "foot" not in lname):
                    local_rots[bone_name] = np.array([right_leg_phase_rad, 0, 0], dtype=np.float32)
                elif "shin_l" in lname or "lowerleg_l" in lname or "calf_l" in lname:
                    local_rots[bone_name] = np.array([left_knee, 0, 0], dtype=np.float32)
                elif "shin_r" in lname or "lowerleg_r" in lname or "calf_r" in lname:
                    local_rots[bone_name] = np.array([right_knee, 0, 0], dtype=np.float32)
                elif "upperarm_l" in lname or "arm_l" in lname and "forearm" not in lname:
                    local_rots[bone_name] = np.array([left_arm_phase, 0, 0], dtype=np.float32)
                elif "upperarm_r" in lname or "arm_r" in lname and "forearm" not in lname:
                    local_rots[bone_name] = np.array([right_arm_phase, 0, 0], dtype=np.float32)
                elif "spine" in lname or "torso" in lname:
                    # лёгкое покачивание
                    local_rots[bone_name] = np.array([0, math.sin(t*speed*0.5)*0.05, math.sin(t*speed)*0.03], dtype=np.float32)

            keyframes.append(local_rots)
        return keyframes

    @staticmethod
    def generate_idle_cycle(skeleton, seed=0, frames=60):
        """Idle — дыхание, микро-движения."""
        keyframes = []
        rng = make_rng(seed)
        for f in range(frames):
            t = f / frames * 2*math.pi
            local_rots = {}
            # дыхание — торс слегка расширяется (ротация)
            breath = math.sin(t*0.5) * 0.02
            for bone_name in skeleton.bones:
                lname = bone_name.lower()
                if "spine" in lname or "torso" in lname or "chest" in lname:
                    local_rots[bone_name] = np.array([breath, 0, 0], dtype=np.float32)
                elif "head" in lname:
                    # голова слегка покачивается
                    local_rots[bone_name] = np.array([math.sin(t*0.3)*0.02, math.sin(t*0.2)*0.03, 0], dtype=np.float32)
            keyframes.append(local_rots)
        return keyframes

    @staticmethod
    def generate_run_cycle(skeleton, speed=2.0, seed=0, frames=20):
        """Бег — быстрее, амплитуда больше."""
        return ProceduralAnimationGenerator.generate_walk_cycle(skeleton, speed=speed, stride_length=1.2, seed=seed, frames=frames)

    @staticmethod
    def generate_attack_cycle(skeleton, seed=0, frames=15):
        """Атака — выпад вперёд."""
        keyframes = []
        for f in range(frames):
            t = f / frames  # 0..1
            # атака: 0-0.3 замах, 0.3-0.6 удар, 0.6-1 возврат
            if t < 0.3:
                phase = t / 0.3
                arm_rot = -phase * 1.2  # назад
            elif t < 0.6:
                phase = (t-0.3)/0.3
                arm_rot = -1.2 + phase*2.5  # вперёд
            else:
                phase = (t-0.6)/0.4
                arm_rot = 1.3 - phase*1.3  # назад в исходное

            local_rots = {}
            for bone_name in skeleton.bones:
                lname = bone_name.lower()
                if "arm_r" in lname or "upperarm_r" in lname:
                    local_rots[bone_name] = np.array([arm_rot, 0, 0], dtype=np.float32)
            keyframes.append(local_rots)
        return keyframes

# ---------- Блендинг анимаций ----------

def blend_animations(anim_a, anim_b, t):
    """
    Бленд двух анимаций: anim_a, anim_b — Dict[bone_name, rot(3,)]
    t: 0..1
    """
    result = {}
    all_bones = set(anim_a.keys()) | set(anim_b.keys())
    for bone in all_bones:
        rot_a = anim_a.get(bone, np.zeros(3, dtype=np.float32))
        rot_b = anim_b.get(bone, np.zeros(3, dtype=np.float32))
        # lerp
        blended = rot_a * (1-t) + rot_b * t
        result[bone] = blended
    return result

def blend_keyframe_sequences(seq_a, seq_b, blend_factor, frame_a, frame_b):
    """Бленд двух последовательностей по кадрам."""
    # seq_a, seq_b — List[Dict]
    anim_a = seq_a[frame_a % len(seq_a)]
    anim_b = seq_b[frame_b % len(seq_b)]
    return blend_animations(anim_a, anim_b, blend_factor)

# ---------- Генераторы скелетов ----------

def generate_humanoid_skeleton(seed=0, height=1.8):
    """Генерация гуманоидного скелета."""
    rng = make_rng(seed)
    bones = {}

    # root — hips
    hips = Bone(name="hips", parent=None, length=0.0, position=np.array([0,0,0], dtype=np.float32), rotation=np.zeros(3, dtype=np.float32), children=["spine", "thigh_l", "thigh_r"])
    bones["hips"] = hips

    spine = Bone(name="spine", parent="hips", length=0.4*height, position=np.array([0,0.3*height,0], dtype=np.float32), rotation=np.zeros(3), children=["chest"])
    bones["spine"] = spine

    chest = Bone(name="chest", parent="spine", length=0.2*height, position=np.array([0,0.3*height,0], dtype=np.float32), rotation=np.zeros(3), children=["head", "upperarm_l", "upperarm_r"])
    bones["chest"] = chest

    head = Bone(name="head", parent="chest", length=0.15*height, position=np.array([0,0.25*height,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["head"] = head

    # руки
    upperarm_l = Bone(name="upperarm_l", parent="chest", length=0.25*height, position=np.array([-0.25*height,0.1*height,0], dtype=np.float32), rotation=np.zeros(3), children=["forearm_l"])
    bones["upperarm_l"] = upperarm_l
    forearm_l = Bone(name="forearm_l", parent="upperarm_l", length=0.25*height, position=np.array([-0.25*height,0,0], dtype=np.float32), rotation=np.zeros(3), children=["hand_l"])
    bones["forearm_l"] = forearm_l
    hand_l = Bone(name="hand_l", parent="forearm_l", length=0.1*height, position=np.array([-0.15*height,0,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["hand_l"] = hand_l

    upperarm_r = Bone(name="upperarm_r", parent="chest", length=0.25*height, position=np.array([0.25*height,0.1*height,0], dtype=np.float32), rotation=np.zeros(3), children=["forearm_r"])
    bones["upperarm_r"] = upperarm_r
    forearm_r = Bone(name="forearm_r", parent="upperarm_r", length=0.25*height, position=np.array([0.25*height,0,0], dtype=np.float32), rotation=np.zeros(3), children=["hand_r"])
    bones["forearm_r"] = forearm_r
    hand_r = Bone(name="hand_r", parent="forearm_r", length=0.1*height, position=np.array([0.15*height,0,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["hand_r"] = hand_r

    # ноги
    thigh_l = Bone(name="thigh_l", parent="hips", length=0.4*height, position=np.array([-0.1*height,-0.1*height,0], dtype=np.float32), rotation=np.zeros(3), children=["shin_l"])
    bones["thigh_l"] = thigh_l
    shin_l = Bone(name="shin_l", parent="thigh_l", length=0.4*height, position=np.array([0,-0.4*height,0], dtype=np.float32), rotation=np.zeros(3), children=["foot_l"])
    bones["shin_l"] = shin_l
    foot_l = Bone(name="foot_l", parent="shin_l", length=0.1*height, position=np.array([0,-0.4*height,0.05*height], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["foot_l"] = foot_l

    thigh_r = Bone(name="thigh_r", parent="hips", length=0.4*height, position=np.array([0.1*height,-0.1*height,0], dtype=np.float32), rotation=np.zeros(3), children=["shin_r"])
    bones["thigh_r"] = thigh_r
    shin_r = Bone(name="shin_r", parent="thigh_r", length=0.4*height, position=np.array([0,-0.4*height,0], dtype=np.float32), rotation=np.zeros(3), children=["foot_r"])
    bones["shin_r"] = shin_r
    foot_r = Bone(name="foot_r", parent="shin_r", length=0.1*height, position=np.array([0,-0.4*height,0.05*height], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["foot_r"] = foot_r

    return Skeleton(bones=bones, root="hips", seed=seed)

def generate_quadruped_skeleton(seed=0, animal_type="wolf", size=1.0):
    """Скелет четвероногого."""
    bones = {}
    # spine
    hips = Bone(name="hips", parent=None, length=0, position=np.zeros(3, dtype=np.float32), rotation=np.zeros(3), children=["spine_mid"])
    bones["hips"] = hips
    spine_mid = Bone(name="spine_mid", parent="hips", length=0.4*size, position=np.array([0.4*size,0,0], dtype=np.float32), rotation=np.zeros(3), children=["spine_front"])
    bones["spine_mid"] = spine_mid
    spine_front = Bone(name="spine_front", parent="spine_mid", length=0.4*size, position=np.array([0.4*size,0,0], dtype=np.float32), rotation=np.zeros(3), children=["head", "upperarm_l", "upperarm_r"])
    bones["spine_front"] = spine_front
    head = Bone(name="head", parent="spine_front", length=0.3*size, position=np.array([0.4*size,0.1*size,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["head"] = head

    # передние ноги
    upperarm_l = Bone(name="upperarm_l", parent="spine_front", length=0.25*size, position=np.array([0.1*size,-0.2*size,0.15*size], dtype=np.float32), rotation=np.zeros(3), children=["forearm_l"])
    bones["upperarm_l"] = upperarm_l
    forearm_l = Bone(name="forearm_l", parent="upperarm_l", length=0.25*size, position=np.array([0,-0.25*size,0], dtype=np.float32), rotation=np.zeros(3), children=["foot_front_l"])
    bones["forearm_l"] = forearm_l
    foot_front_l = Bone(name="foot_front_l", parent="forearm_l", length=0.1*size, position=np.array([0,-0.25*size,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["foot_front_l"] = foot_front_l

    upperarm_r = Bone(name="upperarm_r", parent="spine_front", length=0.25*size, position=np.array([0.1*size,-0.2*size,-0.15*size], dtype=np.float32), rotation=np.zeros(3), children=["forearm_r"])
    bones["upperarm_r"] = upperarm_r
    forearm_r = Bone(name="forearm_r", parent="upperarm_r", length=0.25*size, position=np.array([0,-0.25*size,0], dtype=np.float32), rotation=np.zeros(3), children=["foot_front_r"])
    bones["forearm_r"] = forearm_r
    foot_front_r = Bone(name="foot_front_r", parent="forearm_r", length=0.1*size, position=np.array([0,-0.25*size,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["foot_front_r"] = foot_front_r

    # задние ноги
    thigh_l = Bone(name="thigh_l", parent="hips", length=0.3*size, position=np.array([-0.1*size,-0.2*size,0.15*size], dtype=np.float32), rotation=np.zeros(3), children=["shin_l"])
    bones["thigh_l"] = thigh_l
    shin_l = Bone(name="shin_l", parent="thigh_l", length=0.3*size, position=np.array([0,-0.3*size,0], dtype=np.float32), rotation=np.zeros(3), children=["foot_back_l"])
    bones["shin_l"] = shin_l
    foot_back_l = Bone(name="foot_back_l", parent="shin_l", length=0.1*size, position=np.array([0,-0.3*size,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["foot_back_l"] = foot_back_l

    thigh_r = Bone(name="thigh_r", parent="hips", length=0.3*size, position=np.array([-0.1*size,-0.2*size,-0.15*size], dtype=np.float32), rotation=np.zeros(3), children=["shin_r"])
    bones["thigh_r"] = thigh_r
    shin_r = Bone(name="shin_r", parent="thigh_r", length=0.3*size, position=np.array([0,-0.3*size,0], dtype=np.float32), rotation=np.zeros(3), children=["foot_back_r"])
    bones["shin_r"] = shin_r
    foot_back_r = Bone(name="foot_back_r", parent="shin_r", length=0.1*size, position=np.array([0,-0.3*size,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["foot_back_r"] = foot_back_r

    # хвост
    tail_1 = Bone(name="tail_1", parent="hips", length=0.2*size, position=np.array([-0.2*size,0,0], dtype=np.float32), rotation=np.zeros(3), children=["tail_2"])
    bones["tail_1"] = tail_1
    tail_2 = Bone(name="tail_2", parent="tail_1", length=0.2*size, position=np.array([-0.2*size,0,0], dtype=np.float32), rotation=np.zeros(3), children=[])
    bones["tail_2"] = tail_2

    return Skeleton(bones=bones, root="hips", seed=seed)

# ---------- Веса вершин для скининга ----------

def generate_bone_weights_for_humanoid(mesh, skeleton):
    """Генерация весов вершин по близости к костям (упрощённо)."""
    # mesh: MeshData
    # Для каждой вершины находим ближайшую кость
    world_pos, _ = skeleton.compute_world_positions()
    bone_names = list(world_pos.keys())
    bone_positions = [world_pos[name] for name in bone_names]

    weights = np.zeros((len(mesh.vertices), 4), dtype=np.float32)
    indices = np.zeros((len(mesh.vertices), 4), dtype=np.int32)

    for i, v in enumerate(mesh.vertices):
        # расстояния до всех костей
        dists = []
        for j, bp in enumerate(bone_positions):
            d = np.linalg.norm(v - bp)
            dists.append((d, j))
        dists.sort(key=lambda x: x[0])
        # берём 4 ближайших
        total_w = 0.0
        for k in range(min(4, len(dists))):
            d, b_idx = dists[k]
            w = 1.0 / (d + 0.1)
            weights[i, k] = w
            indices[i, k] = b_idx
            total_w += w
        if total_w > 1e-8:
            weights[i] /= total_w

    return weights, indices, bone_names
