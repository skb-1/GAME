
import numpy as np
from utils.procedural_mesh import MeshData, PrimitiveFactory, merge_meshes, transform_mesh, Modifier
from utils.math_utils import make_rng

class BuildingBlockGenerator:
    @staticmethod
    def wall(width=4.0, height=3.0, thickness=0.3, seed=0, damaged=0.0):
        # стена — box с повреждениями
        wall = PrimitiveFactory.box(size_x=width, size_y=height, size_z=thickness, seed=seed, name="wall")
        if damaged > 0:
            wall = Modifier.noise_displace(wall, amplitude=damaged*0.5, frequency=1.0, octaves=2, seed=seed)
        return wall

    @staticmethod
    def floor_block(width=4.0, depth=4.0, thickness=0.2, seed=0):
        floor = PrimitiveFactory.box(size_x=width, size_y=thickness, size_z=depth, seed=seed, name="floor")
        return floor

    @staticmethod
    def pillar(radius=0.3, height=3.0, seed=0):
        pillar = PrimitiveFactory.cylinder(radius=radius, height=height, segments=8, seed=seed, name="pillar")
        return pillar

    @staticmethod
    def window_frame(width=1.5, height=1.5, seed=0):
        # рама — 4 коробки
        top = PrimitiveFactory.box(size_x=width, size_y=0.1, size_z=0.1, seed=seed, name="window_top")
        mat_top = np.eye(4, dtype=np.float32)
        mat_top[1,3]=height*0.5
        top = transform_mesh(top, mat_top)
        bottom = PrimitiveFactory.box(size_x=width, size_y=0.1, size_z=0.1, seed=seed+1, name="window_bottom")
        mat_bottom = np.eye(4, dtype=np.float32)
        mat_bottom[1,3]=-height*0.5
        bottom = transform_mesh(bottom, mat_bottom)
        left = PrimitiveFactory.box(size_x=0.1, size_y=height, size_z=0.1, seed=seed+2, name="window_left")
        mat_left = np.eye(4, dtype=np.float32)
        mat_left[0,3]=-width*0.5
        left = transform_mesh(left, mat_left)
        right = PrimitiveFactory.box(size_x=0.1, size_y=height, size_z=0.1, seed=seed+3, name="window_right")
        mat_right = np.eye(4, dtype=np.float32)
        mat_right[0,3]=width*0.5
        right = transform_mesh(right, mat_right)
        return merge_meshes([top, bottom, left, right], name="window_frame")

    @staticmethod
    def roof_block(width=4.0, depth=4.0, seed=0, damaged=0.5):
        roof = PrimitiveFactory.box(size_x=width, size_y=0.2, size_z=depth, seed=seed, name="roof")
        if damaged>0:
            roof = Modifier.noise_displace(roof, amplitude=damaged*0.3, frequency=2.0, octaves=2, seed=seed)
        return roof

    @staticmethod
    def sarcophagus_block(seed=0):
        # саркофаг — большой бетонный блок с ржавчиной
        block = PrimitiveFactory.box(size_x=10.0, size_y=8.0, size_z=10.0, seed=seed, name="sarcophagus")
        block = Modifier.noise_displace(block, amplitude=0.8, frequency=0.5, octaves=3, seed=seed)
        return block
