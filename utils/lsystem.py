"""
L-system для генерации деревьев, растений, кустов.
Python 3.10.0, детерминирован по seed.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import math
import numpy as np
from .math_utils import make_rng
from .procedural_mesh import MeshData, PrimitiveFactory, merge_meshes, transform_mesh

@dataclass(slots=True)
class LSystemRule:
    predecessor: str
    successor: str
    probability: float = 1.0

@dataclass(slots=True)
class LSystem:
    axiom: str
    rules: Dict[str, List[LSystemRule]]
    angle: float  # угол поворота в градусах
    iterations: int
    seed: int = 0

    def generate_string(self):
        rng = make_rng(self.seed)
        current = self.axiom
        for _ in range(self.iterations):
            next_str = []
            for char in current:
                if char in self.rules:
                    rule_list = self.rules[char]
                    # выбор по вероятности
                    if len(rule_list) == 1:
                        next_str.append(rule_list[0].successor)
                    else:
                        probs = [r.probability for r in rule_list]
                        probs = np.array(probs) / sum(probs)
                        choice = rng.choice(rule_list, p=probs)
                        next_str.append(choice.successor)
                else:
                    next_str.append(char)
            current = "".join(next_str)
        return current

# ---------- Turtle Graphics для 3D ----------

@dataclass(slots=True)
class TurtleState:
    position: np.ndarray  # (3,)
    direction: np.ndarray  # (3,) forward
    up: np.ndarray  # (3,)
    thickness: float

class Turtle3D:
    def __init__(self, start_pos=None, start_dir=None, start_up=None, angle_deg=25.0, seed=0):
        if start_pos is None:
            start_pos = np.array([0,0,0], dtype=np.float32)
        if start_dir is None:
            start_dir = np.array([0,1,0], dtype=np.float32)  # вверх
        if start_up is None:
            start_up = np.array([0,0,1], dtype=np.float32)
        self.position = start_pos.copy()
        self.direction = start_dir.copy()
        self.up = start_up.copy()
        self.thickness = 0.1
        self.angle = math.radians(angle_deg)
        self.stack = []
        self.seed = seed
        self.rng = make_rng(seed)
        self.branches = []  # List[Tuple[start, end, thickness]]

    def _rotate_direction(self, axis, angle):
        """Поворот direction вокруг axis."""
        # Rodrigues
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        axis = axis / (np.linalg.norm(axis)+1e-8)
        # v_rot = v*cos + (axis x v)*sin + axis*(axis·v)*(1-cos)
        dot = np.dot(axis, self.direction)
        cross = np.cross(axis, self.direction)
        new_dir = self.direction*cos_a + cross*sin_a + axis*dot*(1-cos_a)
        self.direction = new_dir / (np.linalg.norm(new_dir)+1e-8)
        # up тоже повернуть
        cross_up = np.cross(axis, self.up)
        dot_up = np.dot(axis, self.up)
        new_up = self.up*cos_a + cross_up*sin_a + axis*dot_up*(1-cos_a)
        self.up = new_up / (np.linalg.norm(new_up)+1e-8)

    def forward(self, length):
        new_pos = self.position + self.direction * length
        self.branches.append((self.position.copy(), new_pos.copy(), self.thickness))
        self.position = new_pos

    def turn_left(self):
        # поворот вокруг up
        self._rotate_direction(self.up, self.angle)

    def turn_right(self):
        self._rotate_direction(self.up, -self.angle)

    def pitch_down(self):
        # поворот вокруг side = cross(direction, up)
        side = np.cross(self.direction, self.up)
        side = side / (np.linalg.norm(side)+1e-8)
        self._rotate_direction(side, self.angle)

    def pitch_up(self):
        side = np.cross(self.direction, self.up)
        side = side / (np.linalg.norm(side)+1e-8)
        self._rotate_direction(side, -self.angle)

    def roll_left(self):
        self._rotate_direction(self.direction, self.angle)

    def roll_right(self):
        self._rotate_direction(self.direction, -self.angle)

    def push(self):
        self.stack.append((self.position.copy(), self.direction.copy(), self.up.copy(), self.thickness))

    def pop(self):
        if self.stack:
            self.position, self.direction, self.up, self.thickness = self.stack.pop()

    def shrink_thickness(self, factor=0.7):
        self.thickness *= factor

# ---------- Генерация деревьев ----------

def generate_tree_lsystem(species="oak", seed=0, iterations=4):
    """Создать L-system для вида дерева."""
    if species == "oak":
        # Дуб — широкие ветви
        axiom = "X"
        rules = {
            "X": [LSystemRule("X", "F-[[X]+X]+F[+FX]-X", 1.0)],
            "F": [LSystemRule("F", "FF", 1.0)]
        }
        angle = 25.0
    elif species == "pine":
        # Сосна — узкая, вверх
        axiom = "X"
        rules = {
            "X": [LSystemRule("X", "F[+X]F[-X]+X", 1.0)],
            "F": [LSystemRule("F", "FF", 1.0)]
        }
        angle = 20.0
    elif species == "birch":
        axiom = "F"
        rules = {
            "F": [LSystemRule("F", "F[+F]F[-F]F", 1.0)]
        }
        angle = 25.7
    elif species == "red_forest":
        # Рыжий лес — искажённое, мутировавшее
        axiom = "X"
        rules = {
            "X": [LSystemRule("X", "F-[[X]+X]+F[+FX]-X", 0.7), LSystemRule("X", "F[+X]F[-X]F", 0.3)],
            "F": [LSystemRule("F", "FF", 0.8), LSystemRule("F", "F[+F]F", 0.2)]
        }
        angle = 35.0
    else:
        axiom = "F"
        rules = {"F": [LSystemRule("F", "F[+F]F[-F]F", 1.0)]}
        angle = 25.0

    return LSystem(axiom=axiom, rules=rules, angle=angle, iterations=iterations, seed=seed)

def lsystem_to_branches(lsys_string, angle_deg=25.0, seed=0, step_length=1.0, thickness_decay=0.7):
    """Интерпретировать строку L-system в ветки."""
    turtle = Turtle3D(angle_deg=angle_deg, seed=seed)
    for char in lsys_string:
        if char == 'F':
            turtle.forward(step_length * turtle.rng.uniform(0.8, 1.2))
        elif char == '+':
            turtle.turn_left()
        elif char == '-':
            turtle.turn_right()
        elif char == '&':
            turtle.pitch_down()
        elif char == '^':
            turtle.pitch_up()
        elif char == '\\':
            turtle.roll_left()
        elif char == '/':
            turtle.roll_right()
        elif char == '[':
            turtle.push()
            turtle.shrink_thickness(thickness_decay)
        elif char == ']':
            turtle.pop()
        elif char == 'X':
            # X — ничего, но может быть лист
            pass
    return turtle.branches

def branches_to_mesh(branches, seed=0, name="tree"):
    """Конвертировать ветки в меши цилиндров + сферы для листьев."""
    if not branches:
        return None
    meshes = []
    rng = make_rng(seed)
    for i, (start, end, thickness) in enumerate(branches):
        # длина
        vec = end - start
        length = np.linalg.norm(vec)
        if length < 1e-6:
            continue
        # цилиндр от start до end
        # создаём цилиндр и трансформируем
        # цилиндр по Y, нужно повернуть в направлении vec
        cyl = PrimitiveFactory.cylinder(radius=thickness, height=length, segments=6, caps=False, seed=seed+i, name=f"branch_{i}")
        # матрица трансформации: перенос в середину + поворот
        mid = (start + end) * 0.5
        # поворот: Y -> vec
        # вычисляем кватернион/матрицу
        # упрощённо: найдём ось вращения и угол
        y_axis = np.array([0,1,0], dtype=np.float32)
        dir_norm = vec / (length+1e-8)
        # ось = cross(y, dir)
        axis = np.cross(y_axis, dir_norm)
        axis_len = np.linalg.norm(axis)
        if axis_len < 1e-6:
            # уже сонаправлены
            if np.dot(y_axis, dir_norm) < 0:
                # противоположно — поворот 180 вокруг X
                rot_mat = np.array([[-1,0,0,0],[0,-1,0,0],[0,0,1,0],[0,0,0,1]], dtype=np.float32)
            else:
                rot_mat = np.eye(4, dtype=np.float32)
        else:
            axis = axis / axis_len
            angle = math.acos(np.clip(np.dot(y_axis, dir_norm), -1, 1))
            # матрица поворота вокруг axis
            c = math.cos(angle)
            s = math.sin(angle)
            t = 1 - c
            x, y, z = axis
            rot_mat = np.array([
                [t*x*x + c, t*x*y - s*z, t*x*z + s*y, 0],
                [t*x*y + s*z, t*y*y + c, t*y*z - s*x, 0],
                [t*x*z - s*y, t*y*z + s*x, t*z*z + c, 0],
                [0,0,0,1]
            ], dtype=np.float32)
        # трансляция
        trans_mat = np.eye(4, dtype=np.float32)
        trans_mat[0,3]=mid[0]
        trans_mat[1,3]=mid[1]
        trans_mat[2,3]=mid[2]
        final_mat = trans_mat @ rot_mat
        cyl_transformed = transform_mesh(cyl, final_mat)
        meshes.append(cyl_transformed)

        # листья на концах с некоторой вероятностью
        if rng.random() < 0.3 and thickness < 0.05:
            leaf = PrimitiveFactory.sphere(radius=thickness*3, segments=6, rings=4, seed=seed+i+1000, name=f"leaf_{i}")
            mat_leaf = np.eye(4, dtype=np.float32)
            mat_leaf[0,3]=end[0]
            mat_leaf[1,3]=end[1]
            mat_leaf[2,3]=end[2]
            leaf = transform_mesh(leaf, mat_leaf)
            meshes.append(leaf)

    if not meshes:
        return None
    return merge_meshes(meshes, name=name)

def generate_tree_mesh(species="oak", seed=0, height=5.0, iterations=4):
    """Полная генерация дерева."""
    lsys = generate_tree_lsystem(species=species, seed=seed, iterations=iterations)
    lstr = lsys.generate_string()
    # масштабируем step_length по высоте и длине строки
    # оценим количество F
    f_count = lstr.count('F')
    if f_count == 0:
        f_count = 1
    step_len = height / (f_count * 0.3 + 1e-8)
    branches = lsystem_to_branches(lstr, angle_deg=lsys.angle, seed=seed, step_length=step_len, thickness_decay=0.7)
    mesh = branches_to_mesh(branches, seed=seed, name=f"tree_{species}_{seed}")
    return mesh

def generate_bush_lsystem(seed=0):
    """Куст — маленький L-system."""
    lsys = LSystem(
        axiom="F",
        rules={"F": [LSystemRule("F", "F[+F]F[-F][F]", 1.0)]},
        angle=35.0,
        iterations=3,
        seed=seed
    )
    lstr = lsys.generate_string()
    branches = lsystem_to_branches(lstr, angle_deg=35.0, seed=seed, step_length=0.3, thickness_decay=0.8)
    mesh = branches_to_mesh(branches, seed=seed, name=f"bush_{seed}")
    return mesh
