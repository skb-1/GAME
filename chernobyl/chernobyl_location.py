
import numpy as np
from utils.math_utils import make_rng
from utils.procedural_mesh import merge_meshes, transform_mesh, PrimitiveFactory
from .building_blocks import BuildingBlockGenerator
from utils.asset_cache import global_cache

class ChernobylLocationGenerator:
    def __init__(self, world_seed=0):
        self.world_seed = world_seed
        self.rng = make_rng(world_seed)

    def generate_sarcophagus(self, seed=0):
        cached = global_cache.load_mesh("sarcophagus", seed, category="chernobyl")
        if cached:
            return cached
        # модульная генерация из блоков
        blocks = []
        # основание
        for x in range(-2,3):
            for z in range(-2,3):
                block = BuildingBlockGenerator.sarcophagus_block(seed=seed+x*10+z)
                mat = np.eye(4, dtype=np.float32)
                mat[0,3]=x*10
                mat[2,3]=z*10
                mat[1,3]=0
                block = transform_mesh(block, mat)
                blocks.append(block)
        # стены
        for i in range(4):
            wall = BuildingBlockGenerator.wall(width=50, height=20, thickness=2, seed=seed+100+i, damaged=0.8)
            angle = i*90
            # позиция
            import math
            rad = math.radians(angle)
            mat_rot = np.array([[math.cos(rad),0,math.sin(rad),0],[0,1,0,0],[-math.sin(rad),0,math.cos(rad),0],[0,0,0,1]], dtype=np.float32)
            mat_trans = np.eye(4, dtype=np.float32)
            mat_trans[0,3]=math.cos(rad)*25
            mat_trans[2,3]=math.sin(rad)*25
            mat_trans[1,3]=10
            wall = transform_mesh(wall, mat_trans @ mat_rot)
            blocks.append(wall)

        final = merge_meshes(blocks, name="sarcophagus_complex")
        global_cache.save_mesh(final, category="chernobyl")
        return final

    def generate_pripyat_building(self, floors=5, seed=0, damaged=0.5):
        cached = global_cache.load_mesh(f"pripyat_{floors}", seed, category="chernobyl")
        if cached:
            return cached
        blocks = []
        width = 20
        depth = 12
        floor_height = 3.0
        for floor in range(floors):
            y = floor*floor_height
            # пол
            floor_block = BuildingBlockGenerator.floor_block(width=width, depth=depth, seed=seed+floor, thickness=0.3)
            mat_floor = np.eye(4, dtype=np.float32)
            mat_floor[1,3]=y
            floor_block = transform_mesh(floor_block, mat_floor)
            blocks.append(floor_block)
            # стены
            for wall_idx in range(4):
                is_long = wall_idx % 2 == 0
                w = width if is_long else depth
                wall = BuildingBlockGenerator.wall(width=w, height=floor_height, thickness=0.3, seed=seed+floor*10+wall_idx, damaged=damaged)
                import math
                if wall_idx == 0:
                    mat = np.eye(4, dtype=np.float32)
                    mat[2,3]=depth*0.5
                    mat[1,3]=y+floor_height*0.5
                elif wall_idx == 1:
                    mat = np.eye(4, dtype=np.float32)
                    mat[0,3]=width*0.5
                    mat[1,3]=y+floor_height*0.5
                    # поворот 90
                    rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
                    mat = mat @ rot
                elif wall_idx == 2:
                    mat = np.eye(4, dtype=np.float32)
                    mat[2,3]=-depth*0.5
                    mat[1,3]=y+floor_height*0.5
                else:
                    mat = np.eye(4, dtype=np.float32)
                    mat[0,3]=-width*0.5
                    mat[1,3]=y+floor_height*0.5
                    rot = np.array([[0,0,1,0],[0,1,0,0],[-1,0,0,0],[0,0,0,1]], dtype=np.float32)
                    mat = mat @ rot
                wall = transform_mesh(wall, mat)
                blocks.append(wall)
                # окна
                if self.rng.random() > 0.3:
                    win = BuildingBlockGenerator.window_frame(width=1.2, height=1.2, seed=seed+floor*20+wall_idx)
                    win = transform_mesh(win, mat)
                    blocks.append(win)

        final = merge_meshes(blocks, name=f"pripyat_{floors}")
        global_cache.save_mesh(final, category="chernobyl")
        return final

    def generate_jupiter_factory(self, seed=0):
        cached = global_cache.load_mesh("jupiter", seed, category="chernobyl")
        if cached:
            return cached
        blocks = []
        # большие цеха
        for i in range(3):
            hall = BuildingBlockGenerator.wall(width=40, height=15, thickness=1.0, seed=seed+i, damaged=0.7)
            import math
            mat = np.eye(4, dtype=np.float32)
            mat[0,3]=i*45
            mat[1,3]=7.5
            hall = transform_mesh(hall, mat)
            blocks.append(hall)
            roof = BuildingBlockGenerator.roof_block(width=40, depth=30, seed=seed+10+i, damaged=0.6)
            mat_roof = np.eye(4, dtype=np.float32)
            mat_roof[0,3]=i*45
            mat_roof[1,3]=15
            roof = transform_mesh(roof, mat_roof)
            blocks.append(roof)

        final = merge_meshes(blocks, name="jupiter_factory")
        global_cache.save_mesh(final, category="chernobyl")
        return final

    def generate_location(self, loc_type, seed=0):
        if loc_type == "sarcophagus":
            return self.generate_sarcophagus(seed=seed)
        elif loc_type == "pripyat":
            return self.generate_pripyat_building(floors=self.rng.integers(3,9), seed=seed)
        elif loc_type == "jupiter":
            return self.generate_jupiter_factory(seed=seed)
        else:
            return self.generate_pripyat_building(seed=seed)
