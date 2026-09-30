
"""
Генератор процедурных моделей предметов.
"""
import numpy as np
from utils.procedural_mesh import MeshData, PrimitiveFactory, merge_meshes, transform_mesh, Modifier, generate_humanoid_part
from utils.math_utils import make_rng
from utils.asset_cache import global_cache

class ItemModelGenerator:
    @staticmethod
    def generate_tool(tool_type="pickaxe", seed=0):
        cached = global_cache.load_mesh(tool_type, seed, category="item")
        if cached:
            return cached
        if tool_type == "pickaxe":
            handle = PrimitiveFactory.cylinder(radius=0.03, height=0.8, segments=8, seed=seed, name="pickaxe_handle")
            head = PrimitiveFactory.box(size_x=0.4, size_y=0.05, size_z=0.05, seed=seed+1, name="pickaxe_head")
            # повернуть head
            mat_head = np.eye(4, dtype=np.float32)
            mat_head[1,3]=0.4
            head = transform_mesh(head, mat_head)
            final = merge_meshes([handle, head], name="pickaxe")
        elif tool_type == "shovel":
            handle = PrimitiveFactory.cylinder(radius=0.03, height=0.9, segments=8, seed=seed, name="shovel_handle")
            blade = PrimitiveFactory.box(size_x=0.2, size_y=0.02, size_z=0.25, seed=seed+1, name="shovel_blade")
            mat_blade = np.eye(4, dtype=np.float32)
            mat_blade[1,3]=0.5
            blade = transform_mesh(blade, mat_blade)
            final = merge_meshes([handle, blade], name="shovel")
        elif tool_type == "axe":
            handle = PrimitiveFactory.cylinder(radius=0.035, height=0.7, segments=8, seed=seed, name="axe_handle")
            blade = PrimitiveFactory.box(size_x=0.25, size_y=0.15, size_z=0.02, seed=seed+1, name="axe_blade")
            mat_blade = np.eye(4, dtype=np.float32)
            mat_blade[1,3]=0.35
            blade = transform_mesh(blade, mat_blade)
            final = merge_meshes([handle, blade], name="axe")
        else:
            final = PrimitiveFactory.box(size_x=0.2, size_y=0.2, size_z=0.5, seed=seed, name=tool_type)

        global_cache.save_mesh(final, category="item")
        return final

    @staticmethod
    def generate_weapon(weapon_type="rifle", seed=0):
        from utils.procedural_mesh import generate_weapon_mesh
        cached = global_cache.load_mesh(weapon_type, seed, category="item")
        if cached:
            return cached
        mesh = generate_weapon_mesh(weapon_type, seed=seed)
        global_cache.save_mesh(mesh, category="item")
        return mesh

    @staticmethod
    def generate_artifact(artifact_type="electra", seed=0):
        cached = global_cache.load_mesh(f"artifact_{artifact_type}", seed, category="item")
        if cached:
            return cached
        rng = make_rng(seed)
        # артефакт — искажённая сфера/кристалл
        base = PrimitiveFactory.sphere(radius=0.15, segments=12, rings=10, seed=seed, name=f"artifact_{artifact_type}")
        base = Modifier.noise_displace(base, amplitude=0.05, frequency=2.5, octaves=3, seed=seed)
        base = Modifier.twist(base, angle_deg=rng.uniform(-30,30), axis='y')
        # свечение — добавим вторую сферу чуть больше, полупрозрачную (в меше — просто вторая)
        glow = PrimitiveFactory.sphere(radius=0.18, segments=8, rings=6, seed=seed+1, name=f"artifact_{artifact_type}_glow")
        glow = Modifier.noise_displace(glow, amplitude=0.02, frequency=3.0, octaves=2, seed=seed+1)
        final = merge_meshes([base, glow], name=f"artifact_{artifact_type}")
        global_cache.save_mesh(final, category="item")
        return final

    @staticmethod
    def generate_geiger_counter(seed=0):
        cached = global_cache.load_mesh("geiger", seed, category="item")
        if cached:
            return cached
        body = PrimitiveFactory.box(size_x=0.12, size_y=0.08, size_z=0.04, seed=seed, name="geiger_body")
        antenna = PrimitiveFactory.cylinder(radius=0.01, height=0.15, segments=6, seed=seed+1, name="geiger_antenna")
        mat_ant = np.eye(4, dtype=np.float32)
        mat_ant[1,3]=0.1
        antenna = transform_mesh(antenna, mat_ant)
        final = merge_meshes([body, antenna], name="geiger")
        global_cache.save_mesh(final, category="item")
        return final

    @staticmethod
    def generate_by_name(name, seed=0):
        if name in ["pickaxe", "shovel", "axe", "building_tool"]:
            return ItemModelGenerator.generate_tool(name, seed)
        elif name in ["rifle", "pistol", "knife"]:
            return ItemModelGenerator.generate_weapon(name, seed)
        elif "artifact" in name:
            atype = name.split("_")[-1] if "_" in name else "electra"
            return ItemModelGenerator.generate_artifact(atype, seed)
        elif "geiger" in name:
            return ItemModelGenerator.generate_geiger_counter(seed)
        else:
            cached = global_cache.load_mesh(name, seed, category="item")
            if cached:
                return cached
            m = PrimitiveFactory.box(size_x=0.2, size_y=0.2, size_z=0.2, seed=seed, name=name)
            global_cache.save_mesh(m, category="item")
            return m
