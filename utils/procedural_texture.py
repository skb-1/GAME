"""
Генерация процедурных текстур — PBR материалы.
Python 3.10.0, Numpy 1.24.4, Numba 0.57.1, Scipy 1.11.4
"""
from dataclasses import dataclass
from typing import Tuple, Dict, Optional, List
import math
import numpy as np
from .math_utils import make_rng, perlin_init_permutation, fbm_2d, smoothstep

try:
    from scipy.ndimage import gaussian_filter, sobel
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    def gaussian_filter(arr, sigma):
        return arr

def generate_perlin_texture(width, height, scale=0.05, octaves=4, lacunarity=2.0, persistence=0.5, seed=0):
    perm = perlin_init_permutation(seed)
    tex = np.zeros((height, width), dtype=np.float32)
    for y in range(height):
        for x in range(width):
            nx = x * scale
            ny = y * scale
            tex[y, x] = fbm_2d(nx, ny, octaves, lacunarity, persistence, perm)
    tex = (tex + 1.0) * 0.5
    tex = np.clip(tex, 0.0, 1.0)
    return tex

def generate_voronoi_texture(width, height, points_count=20, seed=0):
    rng = make_rng(seed)
    points = rng.uniform(0, 1, size=(points_count, 2))
    points[:,0] *= width
    points[:,1] *= height
    tex = np.zeros((height, width), dtype=np.float32)
    for y in range(height):
        for x in range(width):
            dx = points[:,0] - x
            dy = points[:,1] - y
            dist = np.sqrt(dx*dx + dy*dy)
            min_dist = np.min(dist)
            tex[y,x] = min_dist
    tex = tex / (np.max(tex)+1e-8)
    return tex

def colorize_grayscale(gray, color_low, color_high):
    h, w = gray.shape
    color_low = np.array(color_low, dtype=np.float32)
    color_high = np.array(color_high, dtype=np.float32)
    out = np.zeros((h,w,3), dtype=np.float32)
    for c in range(3):
        out[:,:,c] = color_low[c] + (color_high[c]-color_low[c]) * gray
    return out

def generate_normal_map_from_height(height_map, strength=1.0):
    if HAS_SCIPY:
        dx = sobel(height_map, axis=1)
        dy = sobel(height_map, axis=0)
    else:
        dx = np.zeros_like(height_map)
        dy = np.zeros_like(height_map)
        dx[:,1:-1] = (height_map[:,2:] - height_map[:,:-2])*0.5
        dy[1:-1,:] = (height_map[2:,:] - height_map[:-2,:])*0.5
    h,w = height_map.shape
    normal = np.zeros((h,w,3), dtype=np.float32)
    normal[:,:,0] = -dx * strength
    normal[:,:,1] = -dy * strength
    normal[:,:,2] = 1.0
    norm = np.sqrt(normal[:,:,0]**2 + normal[:,:,1]**2 + normal[:,:,2]**2) + 1e-8
    normal[:,:,0] /= norm
    normal[:,:,1] /= norm
    normal[:,:,2] /= norm
    normal_encoded = (normal + 1.0)*0.5
    return normal, normal_encoded

@dataclass(slots=True)
class PBRMaterial:
    name: str
    albedo: np.ndarray
    roughness: np.ndarray
    metallic: np.ndarray
    normal: np.ndarray
    normal_encoded: np.ndarray
    height: Optional[np.ndarray] = None
    ao: Optional[np.ndarray] = None
    seed: int = 0

    def get_resolution(self):
        return self.albedo.shape[1], self.albedo.shape[0]

class ProceduralTextureGenerator:

    @staticmethod
    def wood(width=256, height=256, seed=0):
        rng = make_rng(seed)
        perm = perlin_init_permutation(seed)
        albedo = np.zeros((height, width, 3), dtype=np.float32)
        height_map = np.zeros((height, width), dtype=np.float32)
        cx = width*0.5 + rng.uniform(-width*0.2, width*0.2)
        cy = height*0.5 + rng.uniform(-height*0.2, height*0.2)
        for y in range(height):
            for x in range(width):
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                noise = fbm_2d(x*0.02, y*0.02, 3, 2.0, 0.5, perm) * 5.0
                ring = math.sin(dist*0.1 + noise*2.0)
                ring = (ring+1)*0.5
                height_map[y,x] = ring
                dark = np.array([0.25, 0.15, 0.05])
                light = np.array([0.6, 0.35, 0.15])
                fiber = fbm_2d(x*0.05, y*0.01, 2, 2.0, 0.5, perm) * 0.2
                t = np.clip(ring + fiber, 0, 1)
                albedo[y,x] = dark + (light-dark)*t
        roughness = 0.7 + height_map*0.2
        roughness = np.clip(roughness, 0.0, 1.0)
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=2.0)
        return PBRMaterial(name=f"wood_{seed}", albedo=albedo, roughness=roughness, metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def stone(width=256, height=256, seed=0):
        base_noise = generate_perlin_texture(width, height, scale=0.03, octaves=5, seed=seed)
        voronoi = generate_voronoi_texture(width, height, points_count=30, seed=seed+1)
        height_map = base_noise*0.6 + voronoi*0.4
        rng = make_rng(seed)
        base_color = np.array([0.5, 0.5, 0.52]) + rng.uniform(-0.05,0.05, size=3)
        albedo = np.zeros((height,width,3), dtype=np.float32)
        for y in range(height):
            for x in range(width):
                h = height_map[y,x]
                variation = (h-0.5)*0.2
                albedo[y,x] = np.clip(base_color + variation, 0, 1)
        roughness = 0.8 + base_noise*0.15
        roughness = np.clip(roughness, 0, 1)
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=3.0)
        return PBRMaterial(name=f"stone_{seed}", albedo=albedo, roughness=roughness, metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def metal(width=256, height=256, seed=0, rust_amount=0.2):
        rng = make_rng(seed)
        base_noise = generate_perlin_texture(width, height, scale=0.08, octaves=3, seed=seed)
        scratch_noise = generate_perlin_texture(width, height, scale=0.2, octaves=2, seed=seed+10)
        height_map = scratch_noise*0.3 + base_noise*0.1
        albedo = np.zeros((height,width,3), dtype=np.float32)
        metal_color = np.array([0.7, 0.72, 0.75])
        rust_color = np.array([0.6, 0.25, 0.1])
        for y in range(height):
            for x in range(width):
                rust_mask = smoothstep(0.3, 0.7, base_noise[y,x])
                if rng.random() < rust_amount:
                    rust_mask = 1.0 - rust_mask*0.5
                else:
                    rust_mask *= 0.2
                albedo[y,x] = metal_color*(1-rust_mask) + rust_color*rust_mask
        roughness = 0.2 + base_noise*0.3 + scratch_noise*0.2
        roughness = np.clip(roughness + rust_amount*0.3, 0, 1)
        metallic = np.ones((height,width), dtype=np.float32) * 0.9
        metallic *= (1.0 - rust_amount*0.5)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=1.5)
        return PBRMaterial(name=f"metal_{seed}", albedo=albedo, roughness=roughness, metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def concrete(width=256, height=256, seed=0):
        base = generate_perlin_texture(width, height, scale=0.04, octaves=4, seed=seed)
        small = generate_perlin_texture(width, height, scale=0.15, octaves=2, seed=seed+5)
        height_map = base*0.7 + small*0.3
        albedo = np.zeros((height,width,3), dtype=np.float32)
        base_col = np.array([0.6, 0.6, 0.58])
        for y in range(height):
            for x in range(width):
                v = height_map[y,x]
                albedo[y,x] = base_col + (v-0.5)*0.1
        roughness = 0.85 + small*0.1
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=2.5)
        return PBRMaterial(name=f"concrete_{seed}", albedo=albedo, roughness=np.clip(roughness,0,1), metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def fabric(width=256, height=256, seed=0):
        rng = make_rng(seed)
        height_map = np.zeros((height,width), dtype=np.float32)
        for y in range(height):
            for x in range(width):
                wx = math.sin(x*0.2) * 0.5 + 0.5
                wy = math.sin(y*0.2) * 0.5 + 0.5
                weave = wx*wy
                noise = rng.uniform(-0.05,0.05)
                height_map[y,x] = weave + noise
        base_col = rng.uniform(0.2,0.8, size=3)
        albedo = np.zeros((height,width,3), dtype=np.float32)
        for y in range(height):
            for x in range(width):
                albedo[y,x] = base_col * (0.8 + height_map[y,x]*0.4)
        roughness = np.ones((height,width), dtype=np.float32)*0.9
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=1.0)
        return PBRMaterial(name=f"fabric_{seed}", albedo=np.clip(albedo,0,1), roughness=roughness, metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def skin(width=256, height=256, seed=0):
        base = generate_perlin_texture(width, height, scale=0.05, octaves=4, seed=seed)
        pores = generate_perlin_texture(width, height, scale=0.2, octaves=2, seed=seed+3)
        height_map = base*0.8 + pores*0.2
        rng = make_rng(seed)
        skin_tone = np.array([0.8, 0.6, 0.5]) + rng.uniform(-0.1,0.1, size=3)
        albedo = np.zeros((height,width,3), dtype=np.float32)
        for y in range(height):
            for x in range(width):
                albedo[y,x] = skin_tone * (0.9 + height_map[y,x]*0.2)
        roughness = 0.6 + pores*0.2
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=0.8)
        return PBRMaterial(name=f"skin_{seed}", albedo=np.clip(albedo,0,1), roughness=np.clip(roughness,0,1), metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def fur(width=256, height=256, seed=0, fur_length=0.5):
        rng = make_rng(seed)
        height_map = np.zeros((height,width), dtype=np.float32)
        perm = perlin_init_permutation(seed)
        for y in range(height):
            for x in range(width):
                n = fbm_2d(x*0.1, y*0.02, 3, 2.0, 0.5, perm)
                height_map[y,x] = (n+1)*0.5
        fur_colors = [np.array([0.3, 0.2, 0.15]), np.array([0.5, 0.5, 0.5]), np.array([0.9, 0.85, 0.7]), np.array([0.1, 0.1, 0.1])]
        base_col = fur_colors[rng.integers(0,len(fur_colors))]
        albedo = np.zeros((height,width,3), dtype=np.float32)
        for y in range(height):
            for x in range(width):
                albedo[y,x] = base_col * (0.7 + height_map[y,x]*0.6)
        roughness = 0.9 + height_map*0.1
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=1.2)
        return PBRMaterial(name=f"fur_{seed}", albedo=np.clip(albedo,0,1), roughness=np.clip(roughness,0,1), metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def rust(width=256, height=256, seed=0):
        base = generate_perlin_texture(width, height, scale=0.03, octaves=5, seed=seed)
        detail = generate_perlin_texture(width, height, scale=0.12, octaves=3, seed=seed+7)
        height_map = base*0.6 + detail*0.4
        albedo = np.zeros((height,width,3), dtype=np.float32)
        rust_col = np.array([0.55, 0.22, 0.08])
        metal_col = np.array([0.5, 0.5, 0.52])
        for y in range(height):
            for x in range(width):
                t = height_map[y,x]
                albedo[y,x] = metal_col*(1-t) + rust_col*t
        roughness = 0.4 + height_map*0.5
        metallic = 0.2 + (1-height_map)*0.6
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=2.0)
        return PBRMaterial(name=f"rust_{seed}", albedo=albedo, roughness=np.clip(roughness,0,1), metallic=np.clip(metallic,0,1), normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def water(width=256, height=256, seed=0, time=0.0):
        perm = perlin_init_permutation(seed)
        height_map = np.zeros((height,width), dtype=np.float32)
        for y in range(height):
            for x in range(width):
                wx = x*0.05 + time*0.5
                wy = y*0.05
                n = fbm_2d(wx, wy, 4, 2.0, 0.5, perm)
                height_map[y,x] = (n+1)*0.5
        albedo = np.zeros((height,width,3), dtype=np.float32)
        water_col = np.array([0.1, 0.4, 0.6])
        for y in range(height):
            for x in range(width):
                albedo[y,x] = water_col * (0.8 + height_map[y,x]*0.4)
        roughness = 0.1 + height_map*0.1
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=1.5)
        return PBRMaterial(name=f"water_{seed}", albedo=albedo, roughness=roughness, metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

    @staticmethod
    def grass(width=256, height=256, seed=0):
        base = generate_perlin_texture(width, height, scale=0.04, octaves=5, seed=seed)
        blades = generate_perlin_texture(width, height, scale=0.15, octaves=2, seed=seed+2)
        height_map = base*0.7 + blades*0.3
        albedo = np.zeros((height,width,3), dtype=np.float32)
        grass_col = np.array([0.15, 0.4, 0.1])
        earth_col = np.array([0.3, 0.2, 0.1])
        for y in range(height):
            for x in range(width):
                t = height_map[y,x]
                albedo[y,x] = earth_col*(1-t) + grass_col*t
        roughness = 0.8 + base*0.15
        metallic = np.zeros((height,width), dtype=np.float32)
        normal, normal_enc = generate_normal_map_from_height(height_map, strength=1.0)
        return PBRMaterial(name=f"grass_{seed}", albedo=albedo, roughness=np.clip(roughness,0,1), metallic=metallic, normal=normal, normal_encoded=normal_enc, height=height_map, seed=seed)

MATERIAL_GENERATORS = {
    "wood": ProceduralTextureGenerator.wood,
    "stone": ProceduralTextureGenerator.stone,
    "metal": ProceduralTextureGenerator.metal,
    "concrete": ProceduralTextureGenerator.concrete,
    "fabric": ProceduralTextureGenerator.fabric,
    "skin": ProceduralTextureGenerator.skin,
    "fur": ProceduralTextureGenerator.fur,
    "rust": ProceduralTextureGenerator.rust,
    "water": ProceduralTextureGenerator.water,
    "grass": ProceduralTextureGenerator.grass,
    "bark": ProceduralTextureGenerator.wood,
    "leaves": ProceduralTextureGenerator.grass,
    "rubber": ProceduralTextureGenerator.fabric,
    "plastic": ProceduralTextureGenerator.fabric,
    "glass": ProceduralTextureGenerator.water,
}

def generate_material(material_type, width=256, height=256, seed=0, **kwargs):
    gen = MATERIAL_GENERATORS.get(material_type)
    if gen is None:
        gen = ProceduralTextureGenerator.stone
    return gen(width=width, height=height, seed=seed, **kwargs)

def material_to_panda3d_textures(material):
    try:
        from panda3d.core import Texture
    except ImportError:
        raise ImportError("Panda3D не установлен")
    def numpy_to_texture(arr, name, fmt=Texture.FRgb8):
        h,w = arr.shape[:2]
        if arr.ndim == 2:
            arr_rgb = np.stack([arr, arr, arr], axis=-1)
        else:
            arr_rgb = arr
        arr_uint8 = (np.clip(arr_rgb,0,1)*255).astype(np.uint8)
        tex = Texture(name)
        tex.setup2dTexture(w, h, Texture.TUnsignedByte, fmt)
        tex.setRamImageAs(arr_uint8.tobytes(), "RGB")
        return tex
    textures = {}
    textures['albedo'] = numpy_to_texture(material.albedo, f"{material.name}_albedo")
    rough_rgb = np.stack([material.roughness, material.roughness, material.roughness], axis=-1)
    textures['roughness'] = numpy_to_texture(rough_rgb, f"{material.name}_rough")
    textures['normal'] = numpy_to_texture(material.normal_encoded, f"{material.name}_normal")
    if isinstance(material.metallic, np.ndarray) and material.metallic.ndim==2:
        met_rgb = np.stack([material.metallic, material.metallic, material.metallic], axis=-1)
    else:
        met_rgb = np.ones((material.albedo.shape[0], material.albedo.shape[1], 3), dtype=np.float32)*0.0
    textures['metallic'] = numpy_to_texture(met_rgb, f"{material.name}_metallic")
    return textures

def material_to_numpy_cache(material):
    return {
        "albedo": material.albedo,
        "roughness": material.roughness,
        "metallic": material.metallic if isinstance(material.metallic, np.ndarray) else np.array(material.metallic),
        "normal_encoded": material.normal_encoded,
        "height": material.height,
        "name": material.name,
        "seed": material.seed,
    }
