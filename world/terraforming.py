
import math
import numpy as np

class TerraformingSystem:
    def __init__(self, chunk_system):
        self.chunk_system = chunk_system

    def dig(self, world_x, world_z, radius=2.0, depth=1.0):
        chunk_x = int(world_x // self.chunk_system.chunk_size)
        chunk_z = int(world_z // self.chunk_system.chunk_size)
        # в радиусе могут быть несколько чанков
        for dx in range(-1,2):
            for dz in range(-1,2):
                cx = chunk_x + dx
                cz = chunk_z + dz
                self.chunk_system.terraform(cx, cz, world_x, world_z, radius, -abs(depth))

    def build(self, world_x, world_z, radius=2.0, height=1.0):
        chunk_x = int(world_x // self.chunk_system.chunk_size)
        chunk_z = int(world_z // self.chunk_system.chunk_size)
        for dx in range(-1,2):
            for dz in range(-1,2):
                cx = chunk_x + dx
                cz = chunk_z + dz
                self.chunk_system.terraform(cx, cz, world_x, world_z, radius, abs(height))

    def flatten(self, world_x, world_z, radius=3.0, target_height=None):
        # выравнивание — среднее высоты в радиусе
        if target_height is None:
            target_height = self.chunk_system.get_height_at(world_x, world_z)
        chunk_x = int(world_x // self.chunk_system.chunk_size)
        chunk_z = int(world_z // self.chunk_system.chunk_size)
        for dx in range(-1,2):
            for dz in range(-1,2):
                cx = chunk_x + dx
                cz = chunk_z + dz
                key = f"{cx}_{cz}"
                chunk = self.chunk_system.chunks.get(key)
                if chunk and chunk.heightmap is not None:
                    # для каждой точки в радиусе — интерполировать к target
                    local_x = world_x - cx*self.chunk_system.chunk_size
                    local_z = world_z - cz*self.chunk_system.chunk_size
                    res = chunk.heightmap.shape[0]-1
                    ix = int((local_x / self.chunk_system.chunk_size) * res)
                    iz = int((local_z / self.chunk_system.chunk_size) * res)
                    r_idx = int((radius / self.chunk_system.chunk_size) * res) + 1
                    for dz2 in range(-r_idx, r_idx+1):
                        for dx2 in range(-r_idx, r_idx+1):
                            nx = ix+dx2
                            nz = iz+dz2
                            if 0 <= nx < chunk.heightmap.shape[1] and 0 <= nz < chunk.heightmap.shape[0]:
                                dist = math.sqrt(dx2*dx2 + dz2*dz2)
                                if dist <= r_idx:
                                    falloff = 1.0 - dist/(r_idx+1e-8)
                                    chunk.heightmap[nz, nx] = chunk.heightmap[nz, nx]*(1-falloff) + target_height*falloff
                    chunk.is_dirty = True
                    from world.noise_gen import heightmap_to_mesh_data
                    from utils.procedural_mesh import generate_lod_levels
                    from utils.asset_cache import global_cache
                    new_mesh = heightmap_to_mesh_data(chunk.heightmap, cx, cz, chunk_size=self.chunk_system.chunk_size, world_seed=self.chunk_system.world_seed)
                    chunk.mesh = new_mesh
                    chunk.lod_meshes = generate_lod_levels(new_mesh, levels=3)
                    global_cache.save_mesh(new_mesh, category="terrain")
