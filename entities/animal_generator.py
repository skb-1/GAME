"""
Генератор процедурных моделей животных.
Python 3.10.0
"""
from typing import Dict, Tuple
import math
import numpy as np
from utils.procedural_mesh import MeshData, PrimitiveFactory, merge_meshes, transform_mesh, Modifier
from utils.procedural_texture import generate_material
from utils.math_utils import make_rng
from utils.asset_cache import global_cache

class AnimalModelGenerator:
    """Генератор моделей животных по видам — параметрический."""

    @staticmethod
    def generate_wolf(seed=0, size=1.0):
        """Волк — тело, голова, лапы, хвост."""
        rng = make_rng(seed)
        # проверка кэша
        cached = global_cache.load_mesh(f"wolf", seed, category="animal")
        if cached:
            return cached

        # тело — капсула
        body = PrimitiveFactory.capsule(radius=0.25*size, height=0.8*size, segments=10, rings=4, seed=seed, name="wolf_body")
        # повернуть горизонтально
        rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        body = transform_mesh(body, rot)

        # голова — сфера + конус для морды
        head_sphere = PrimitiveFactory.sphere(radius=0.22*size, segments=10, rings=8, seed=seed+1, name="wolf_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=0.6*size
        mat_head[1,3]=0.15*size
        head_sphere = transform_mesh(head_sphere, mat_head)

        snout = PrimitiveFactory.cone(radius=0.12*size, height=0.35*size, segments=8, seed=seed+2, name="wolf_snout")
        # повернуть
        rot_snout = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        trans_snout = np.eye(4, dtype=np.float32)
        trans_snout[0,3]=0.85*size
        trans_snout[1,3]=0.1*size
        snout = transform_mesh(snout, trans_snout @ rot_snout)

        # уши — конусы
        ear_l = PrimitiveFactory.cone(radius=0.08*size, height=0.18*size, segments=6, seed=seed+3, name="wolf_ear_l")
        mat_ear_l = np.eye(4, dtype=np.float32)
        mat_ear_l[0,3]=0.55*size
        mat_ear_l[1,3]=0.35*size
        mat_ear_l[2,3]=0.12*size
        ear_l = transform_mesh(ear_l, mat_ear_l)

        ear_r = PrimitiveFactory.cone(radius=0.08*size, height=0.18*size, segments=6, seed=seed+4, name="wolf_ear_r")
        mat_ear_r = np.eye(4, dtype=np.float32)
        mat_ear_r[0,3]=0.55*size
        mat_ear_r[1,3]=0.35*size
        mat_ear_r[2,3]=-0.12*size
        ear_r = transform_mesh(ear_r, mat_ear_r)

        # лапы — 4 капсулы
        legs = []
        leg_positions = [
            (0.3*size, -0.35*size, 0.18*size),
            (0.3*size, -0.35*size, -0.18*size),
            (-0.3*size, -0.35*size, 0.18*size),
            (-0.3*size, -0.35*size, -0.18*size),
        ]
        for i, (lx, ly, lz) in enumerate(leg_positions):
            leg = PrimitiveFactory.capsule(radius=0.07*size, height=0.5*size, segments=6, rings=3, seed=seed+10+i, name=f"wolf_leg_{i}")
            mat_leg = np.eye(4, dtype=np.float32)
            mat_leg[0,3]=lx
            mat_leg[1,3]=ly
            mat_leg[2,3]=lz
            leg = transform_mesh(leg, mat_leg)
            legs.append(leg)

        # хвост
        tail = PrimitiveFactory.capsule(radius=0.08*size, height=0.5*size, segments=6, rings=3, seed=seed+20, name="wolf_tail")
        rot_tail = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        trans_tail = np.eye(4, dtype=np.float32)
        trans_tail[0,3]=-0.65*size
        trans_tail[1,3]=0.05*size
        # слегка вверх
        tail = transform_mesh(tail, trans_tail @ rot_tail)
        # bend
        tail = Modifier.bend(tail, angle_deg=-15, axis='y', direction='x')

        all_meshes = [body, head_sphere, snout, ear_l, ear_r, tail] + legs
        final = merge_meshes(all_meshes, name="wolf")
        # шум для органики
        final = Modifier.noise_displace(final, amplitude=0.02*size, frequency=3.0, octaves=2, seed=seed)

        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_bear(seed=0, size=1.5):
        cached = global_cache.load_mesh(f"bear", seed, category="animal")
        if cached:
            return cached
        # медведь — крупнее, толще
        body = PrimitiveFactory.capsule(radius=0.4*size, height=0.9*size, segments=12, rings=5, seed=seed, name="bear_body")
        rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        body = transform_mesh(body, rot)

        head = PrimitiveFactory.sphere(radius=0.3*size, segments=12, rings=10, seed=seed+1, name="bear_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=0.7*size
        mat_head[1,3]=0.2*size
        head = transform_mesh(head, mat_head)

        # лапы толстые
        legs = []
        for i in range(4):
            leg = PrimitiveFactory.capsule(radius=0.15*size, height=0.6*size, segments=8, rings=4, seed=seed+10+i, name=f"bear_leg_{i}")
            lx = 0.3*size if i<2 else -0.3*size
            lz = 0.25*size if i%2==0 else -0.25*size
            mat = np.eye(4, dtype=np.float32)
            mat[0,3]=lx
            mat[1,3]=-0.5*size
            mat[2,3]=lz
            leg = transform_mesh(leg, mat)
            legs.append(leg)

        final = merge_meshes([body, head]+legs, name="bear")
        final = Modifier.noise_displace(final, amplitude=0.03*size, frequency=2.0, octaves=2, seed=seed)
        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_deer(seed=0, size=1.2):
        cached = global_cache.load_mesh(f"deer", seed, category="animal")
        if cached:
            return cached
        body = PrimitiveFactory.capsule(radius=0.25*size, height=0.9*size, segments=10, rings=4, seed=seed, name="deer_body")
        rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        body = transform_mesh(body, rot)

        head = PrimitiveFactory.sphere(radius=0.18*size, segments=10, rings=8, seed=seed+1, name="deer_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=0.65*size
        mat_head[1,3]=0.35*size
        head = transform_mesh(head, mat_head)

        # шея — цилиндр
        neck = PrimitiveFactory.cylinder(radius=0.12*size, height=0.4*size, segments=8, seed=seed+2, name="deer_neck")
        rot_neck = np.array([[0.5,0.866,0,0],[-0.866,0.5,0,0],[0,0,1,0],[0,0,0,1]], dtype=np.float32)
        trans_neck = np.eye(4, dtype=np.float32)
        trans_neck[0,3]=0.45*size
        trans_neck[1,3]=0.25*size
        neck = transform_mesh(neck, trans_neck @ rot_neck)

        # рога — ветвящиеся цилиндры (упрощённо)
        horns = []
        for side in [-1,1]:
            horn_base = PrimitiveFactory.cylinder(radius=0.03*size, height=0.3*size, segments=6, seed=seed+10+side, name=f"deer_horn_base_{side}")
            mat_horn = np.eye(4, dtype=np.float32)
            mat_horn[0,3]=0.65*size
            mat_horn[1,3]=0.55*size
            mat_horn[2,3]=side*0.08*size
            horns.append(transform_mesh(horn_base, mat_horn))
            # ответвление
            horn_branch = PrimitiveFactory.cylinder(radius=0.02*size, height=0.2*size, segments=5, seed=seed+20+side, name=f"deer_horn_branch_{side}")
            mat_branch = np.eye(4, dtype=np.float32)
            mat_branch[0,3]=0.65*size
            mat_branch[1,3]=0.7*size
            mat_branch[2,3]=side*0.1*size
            horns.append(transform_mesh(horn_branch, mat_branch))

        legs = []
        for i in range(4):
            leg = PrimitiveFactory.capsule(radius=0.05*size, height=0.7*size, segments=6, rings=3, seed=seed+30+i, name=f"deer_leg_{i}")
            lx = 0.35*size if i<2 else -0.35*size
            lz = 0.15*size if i%2==0 else -0.15*size
            mat = np.eye(4, dtype=np.float32)
            mat[0,3]=lx
            mat[1,3]=-0.45*size
            mat[2,3]=lz
            leg = transform_mesh(leg, mat)
            legs.append(leg)

        final = merge_meshes([body, head, neck]+horns+legs, name="deer")
        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_boar(seed=0, size=1.0):
        cached = global_cache.load_mesh(f"boar", seed, category="animal")
        if cached:
            return cached
        body = PrimitiveFactory.capsule(radius=0.3*size, height=0.7*size, segments=10, rings=4, seed=seed, name="boar_body")
        rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        body = transform_mesh(body, rot)
        head = PrimitiveFactory.box(size_x=0.35*size, size_y=0.25*size, size_z=0.25*size, seed=seed+1, name="boar_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=0.55*size
        head = transform_mesh(head, mat_head)
        # клыки
        tusk_l = PrimitiveFactory.cone(radius=0.03*size, height=0.15*size, segments=6, seed=seed+2, name="boar_tusk_l")
        mat_tusk_l = np.eye(4, dtype=np.float32)
        mat_tusk_l[0,3]=0.75*size
        mat_tusk_l[1,3]=-0.05*size
        mat_tusk_l[2,3]=0.08*size
        tusk_l = transform_mesh(tusk_l, mat_tusk_l)
        tusk_r = PrimitiveFactory.cone(radius=0.03*size, height=0.15*size, segments=6, seed=seed+3, name="boar_tusk_r")
        mat_tusk_r = np.eye(4, dtype=np.float32)
        mat_tusk_r[0,3]=0.75*size
        mat_tusk_r[1,3]=-0.05*size
        mat_tusk_r[2,3]=-0.08*size
        tusk_r = transform_mesh(tusk_r, mat_tusk_r)

        legs = []
        for i in range(4):
            leg = PrimitiveFactory.capsule(radius=0.08*size, height=0.4*size, segments=6, rings=3, seed=seed+10+i, name=f"boar_leg_{i}")
            lx = 0.25*size if i<2 else -0.25*size
            lz = 0.15*size if i%2==0 else -0.15*size
            mat = np.eye(4, dtype=np.float32)
            mat[0,3]=lx
            mat[1,3]=-0.35*size
            mat[2,3]=lz
            leg = transform_mesh(leg, mat)
            legs.append(leg)

        final = merge_meshes([body, head, tusk_l, tusk_r]+legs, name="boar")
        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_hare(seed=0, size=0.4):
        cached = global_cache.load_mesh(f"hare", seed, category="animal")
        if cached:
            return cached
        body = PrimitiveFactory.capsule(radius=0.15*size, height=0.4*size, segments=8, rings=4, seed=seed, name="hare_body")
        rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        body = transform_mesh(body, rot)
        head = PrimitiveFactory.sphere(radius=0.12*size, segments=8, rings=6, seed=seed+1, name="hare_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=0.3*size
        head = transform_mesh(head, mat_head)
        # уши длинные
        ear_l = PrimitiveFactory.capsule(radius=0.03*size, height=0.3*size, segments=6, rings=3, seed=seed+2, name="hare_ear_l")
        mat_ear_l = np.eye(4, dtype=np.float32)
        mat_ear_l[0,3]=0.3*size
        mat_ear_l[1,3]=0.2*size
        mat_ear_l[2,3]=0.05*size
        ear_l = transform_mesh(ear_l, mat_ear_l)
        ear_r = PrimitiveFactory.capsule(radius=0.03*size, height=0.3*size, segments=6, rings=3, seed=seed+3, name="hare_ear_r")
        mat_ear_r = np.eye(4, dtype=np.float32)
        mat_ear_r[0,3]=0.3*size
        mat_ear_r[1,3]=0.2*size
        mat_ear_r[2,3]=-0.05*size
        ear_r = transform_mesh(ear_r, mat_ear_r)

        final = merge_meshes([body, head, ear_l, ear_r], name="hare")
        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_raven(seed=0, size=0.3):
        cached = global_cache.load_mesh(f"raven", seed, category="animal")
        if cached:
            return cached
        body = PrimitiveFactory.capsule(radius=0.1*size, height=0.3*size, segments=8, rings=3, seed=seed, name="raven_body")
        rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        body = transform_mesh(body, rot)
        head = PrimitiveFactory.sphere(radius=0.08*size, segments=8, rings=6, seed=seed+1, name="raven_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=0.2*size
        head = transform_mesh(head, mat_head)
        beak = PrimitiveFactory.cone(radius=0.03*size, height=0.12*size, segments=6, seed=seed+2, name="raven_beak")
        rot_beak = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
        mat_beak = np.eye(4, dtype=np.float32)
        mat_beak[0,3]=0.3*size
        beak = transform_mesh(beak, mat_beak @ rot_beak)
        # крылья — коробки
        wing_l = PrimitiveFactory.box(size_x=0.3*size, size_y=0.02*size, size_z=0.15*size, seed=seed+3, name="raven_wing_l")
        mat_wl = np.eye(4, dtype=np.float32)
        mat_wl[2,3]=0.12*size
        wing_l = transform_mesh(wing_l, mat_wl)
        wing_r = PrimitiveFactory.box(size_x=0.3*size, size_y=0.02*size, size_z=0.15*size, seed=seed+4, name="raven_wing_r")
        mat_wr = np.eye(4, dtype=np.float32)
        mat_wr[2,3]=-0.12*size
        wing_r = transform_mesh(wing_r, mat_wr)

        final = merge_meshes([body, head, beak, wing_l, wing_r], name="raven")
        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_snake(seed=0, size=0.8):
        cached = global_cache.load_mesh(f"snake", seed, category="animal")
        if cached:
            return cached
        # змея — цепочка сфер/капсул с изгибом
        segments = 8
        meshes = []
        for i in range(segments):
            r = 0.08*size * (1.0 - i*0.08)
            seg = PrimitiveFactory.sphere(radius=r, segments=8, rings=6, seed=seed+i, name=f"snake_seg_{i}")
            # позиция по синусоиде
            x = i*0.15*size
            y = math.sin(i*0.8)*0.05*size
            mat = np.eye(4, dtype=np.float32)
            mat[0,3]=x
            mat[1,3]=y
            seg = transform_mesh(seg, mat)
            meshes.append(seg)
        # голова больше
        head = PrimitiveFactory.sphere(radius=0.12*size, segments=10, rings=8, seed=seed+100, name="snake_head")
        mat_head = np.eye(4, dtype=np.float32)
        mat_head[0,3]=segments*0.15*size + 0.1*size
        head = transform_mesh(head, mat_head)

        final = merge_meshes(meshes+[head], name="snake")
        global_cache.save_mesh(final, category="animal")
        return final

    @staticmethod
    def generate_by_type(animal_type, seed=0, size=1.0):
        if animal_type == "wolf":
            return AnimalModelGenerator.generate_wolf(seed=seed, size=size)
        elif animal_type == "bear":
            return AnimalModelGenerator.generate_bear(seed=seed, size=size)
        elif animal_type == "deer":
            return AnimalModelGenerator.generate_deer(seed=seed, size=size)
        elif animal_type == "boar":
            return AnimalModelGenerator.generate_boar(seed=seed, size=size)
        elif animal_type == "hare":
            return AnimalModelGenerator.generate_hare(seed=seed, size=size)
        elif animal_type == "raven":
            return AnimalModelGenerator.generate_raven(seed=seed, size=size)
        elif animal_type == "snake":
            return AnimalModelGenerator.generate_snake(seed=seed, size=size)
        else:
            return AnimalModelGenerator.generate_wolf(seed=seed, size=size)
