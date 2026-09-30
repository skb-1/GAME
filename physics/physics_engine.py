"""
Физика — обёртка с фолбэками, оптимизирована под 8 ГБ.
Python 3.10.0

Приоритет бэкендов:
1. PyBullet 3.2.5+ — полноценная 3D физика (предпочтительно)
2. Pymunk 6.x — 2D физика, используем проекцию XZ+Y отдельно, работает без компиляции C++ (включает chipmunk dll)
3. Pure Python stub — простая гравитация + интеграция, всегда работает

Проблема на Windows: pybullet требует Microsoft Visual C++ 14.0 для сборки из исходников.
Решение:
- pip install --upgrade pip setuptools wheel
- pip install pybullet==3.2.5 --only-binary :all:  (берёт готовое колесо win_amd64 cp310)
- ИЛИ conda install -c conda-forge pybullet
- ИЛИ использовать pymunk фолбэк (pip install pymunk==6.6.0 — чистый wheel, без компиляции)
- ИЛИ играть на stub физике (уже встроена, без зависимостей)

Этот модуль автоматически выбирает доступный бэкенд.
"""
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List
import numpy as np
import threading
import math

# ---------- Детекция бэкендов ----------

HAS_BULLET = False
HAS_PYMUNK = False
p = None
pymunk = None

# Попытка PyBullet
try:
    import pybullet as p
    import pybullet_data
    HAS_BULLET = True
    print("[Physics] PyBullet найден, используется 3D физика")
except ImportError as e:
    print(f"[Physics] PyBullet не найден ({e}), пробую Pymunk...")

# Попытка Pymunk если нет PyBullet
if not HAS_BULLET:
    try:
        import pymunk
        import pymunk.pygame_util
        HAS_PYMUNK = True
        print("[Physics] Pymunk найден, используется 2D физика (проекция)")
    except ImportError as e:
        print(f"[Physics] Pymunk тоже не найден ({e}), используется Pure Python заглушка")

@dataclass(slots=True)
class PhysicsBody:
    body_id: int
    mass: float
    position: np.ndarray
    velocity: np.ndarray
    shape_type: str
    # для pymunk — ссылка на тело
    pymunk_body: Optional[object] = None
    pymunk_shape: Optional[object] = None

class PhysicsEngine:
    def __init__(self, gravity=(0, -9.81, 0)):
        self.gravity = gravity
        self.bodies: Dict[int, PhysicsBody] = {}
        self.terrain_heightfield = None
        self.client_id = None
        self.lock = threading.Lock()
        self.time_step = 1/60.0
        self.backend = "stub"

        if HAS_BULLET:
            try:
                self.client_id = p.connect(p.DIRECT)
                p.setGravity(gravity[0], gravity[1], gravity[2], physicsClientId=self.client_id)
                p.setAdditionalSearchPath(pybullet_data.getDataPath())
                self.backend = "pybullet"
                print(f"[Physics] Backend: PyBullet (client {self.client_id})")
            except Exception as e:
                print(f"[Physics] PyBullet init failed: {e}, переключаюсь на фолбэк")
                self.client_id = None
                # попробовать pymunk
                if HAS_PYMUNK:
                    self._init_pymunk()
                else:
                    self.backend = "stub"
        elif HAS_PYMUNK:
            self._init_pymunk()
        else:
            print("[Physics] Backend: Pure Python stub (без внешних зависимостей) — игра работает, но без коллизий террейна")
            self.backend = "stub"

    def _init_pymunk(self):
        """Инициализация Pymunk 2D мира."""
        try:
            self.pymunk_space = pymunk.Space()
            # гравитация в Y (в pymunk Y вниз обычно, но мы инвертируем)
            # используем (0, gravity[1]) для вертикали, а XZ обрабатываем отдельно
            self.pymunk_space.gravity = (0, self.gravity[1])
            self.backend = "pymunk"
            print(f"[Physics] Backend: Pymunk {pymunk.version}, gravity={self.pymunk_space.gravity}")
        except Exception as e:
            print(f"[Physics] Pymunk init failed: {e}")
            self.backend = "stub"

    def get_backend_name(self):
        return self.backend

    def create_terrain_collision(self, heightmap, chunk_size=32, world_offset=(0,0)):
        """Создание heightfield для террейна."""
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    shape = p.createCollisionShape(p.GEOM_PLANE, physicsClientId=self.client_id)
                    body = p.createMultiBody(baseCollisionShapeIndex=shape, basePosition=[world_offset[0], 0, world_offset[1]], physicsClientId=self.client_id)
                    return body
                except Exception as e:
                    print(f"[Physics] create_terrain_collision failed: {e}")
                    return None
        elif self.backend == "pymunk":
            # в pymunk — создаём статический сегмент как землю
            try:
                static_body = self.pymunk_space.static_body
                # простая плоскость на y=0
                shape = pymunk.Segment(static_body, (world_offset[0]-chunk_size, 0), (world_offset[0]+chunk_size*2, 0), 1.0)
                shape.friction = 1.0
                self.pymunk_space.add(shape)
                return shape
            except Exception as e:
                print(f"[Physics] pymunk terrain failed: {e}")
                return None
        return None

    def create_box(self, position, size, mass=1.0):
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    col_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[size[0]*0.5, size[1]*0.5, size[2]*0.5], physicsClientId=self.client_id)
                    body_id = p.createMultiBody(baseMass=mass, baseCollisionShapeIndex=col_shape, basePosition=position, physicsClientId=self.client_id)
                    self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="box")
                    return body_id
                except Exception as e:
                    print(f"[Physics] PyBullet create_box failed: {e}, fallback to stub")

        if self.backend == "pymunk":
            try:
                body = pymunk.Body(mass, pymunk.moment_for_box(mass, (size[0], size[1])) if mass>0 else float('inf'))
                body.position = (position[0], position[1])  # XZ -> XY проекция, Y вертикаль
                shape = pymunk.Poly.create_box(body, (size[0], size[1]))
                shape.friction = 0.8
                self.pymunk_space.add(body, shape)
                body_id = id(body) % 1000000 + 2000
                self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="box", pymunk_body=body, pymunk_shape=shape)
                return body_id
            except Exception as e:
                print(f"[Physics] Pymunk create_box failed: {e}")

        # stub
        body_id = len(self.bodies) + 1000
        self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="box")
        return body_id

    def create_sphere(self, position, radius, mass=1.0):
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    col_shape = p.createCollisionShape(p.GEOM_SPHERE, radius=radius, physicsClientId=self.client_id)
                    body_id = p.createMultiBody(baseMass=mass, baseCollisionShapeIndex=col_shape, basePosition=position, physicsClientId=self.client_id)
                    self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="sphere")
                    return body_id
                except Exception as e:
                    print(f"[Physics] PyBullet create_sphere failed: {e}")

        if self.backend == "pymunk":
            try:
                body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, radius) if mass>0 else float('inf'))
                body.position = (position[0], position[1])
                shape = pymunk.Circle(body, radius)
                shape.friction = 0.8
                self.pymunk_space.add(body, shape)
                body_id = id(body) % 1000000 + 2000
                self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="sphere", pymunk_body=body, pymunk_shape=shape)
                return body_id
            except Exception as e:
                print(f"[Physics] Pymunk create_sphere failed: {e}")

        body_id = len(self.bodies) + 1000
        self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="sphere")
        return body_id

    def create_capsule(self, position, radius, height, mass=1.0):
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    col_shape = p.createCollisionShape(p.GEOM_CAPSULE, radius=radius, height=height, physicsClientId=self.client_id)
                    body_id = p.createMultiBody(baseMass=mass, baseCollisionShapeIndex=col_shape, basePosition=position, physicsClientId=self.client_id)
                    self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="capsule")
                    return body_id
                except Exception as e:
                    print(f"[Physics] PyBullet create_capsule failed: {e}")

        if self.backend == "pymunk":
            try:
                body = pymunk.Body(mass, pymunk.moment_for_segment(mass, (0, -height*0.5), (0, height*0.5), radius) if mass>0 else float('inf'))
                body.position = (position[0], position[1])
                shape = pymunk.Segment(body, (0, -height*0.5), (0, height*0.5), radius)
                shape.friction = 0.8
                self.pymunk_space.add(body, shape)
                body_id = id(body) % 1000000 + 2000
                self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="capsule", pymunk_body=body, pymunk_shape=shape)
                return body_id
            except Exception as e:
                print(f"[Physics] Pymunk create_capsule failed: {e}")

        body_id = len(self.bodies) + 1000
        self.bodies[body_id] = PhysicsBody(body_id=body_id, mass=mass, position=np.array(position, dtype=np.float32), velocity=np.zeros(3, dtype=np.float32), shape_type="capsule")
        return body_id

    def raycast(self, from_pos, to_pos):
        """Raycast — возвращает hit info."""
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    result = p.rayTest(from_pos, to_pos, physicsClientId=self.client_id)
                    if result and result[0][0] != -1:
                        hit = result[0]
                        return {"hit": True, "position": hit[3], "normal": hit[4], "body_id": hit[0]}
                    return {"hit": False, "position": to_pos, "normal": [0,1,0]}
                except Exception as e:
                    pass

        if self.backend == "pymunk":
            try:
                # 2D raycast в pymunk
                from_p = (from_pos[0], from_pos[1])
                to_p = (to_pos[0], to_pos[1])
                hit = self.pymunk_space.segment_query_first(from_p, to_p, 1, pymunk.ShapeFilter())
                if hit:
                    return {"hit": True, "position": (hit.point[0], from_pos[1], hit.point[1]), "normal": (hit.normal[0], 0, hit.normal[1]), "body_id": id(hit.shape)}
            except Exception as e:
                pass

        # stub — проверка по высоте террейна (упрощённо всегда нет хита, кроме земли)
        # если луч идёт вниз и пересекает y=0
        if from_pos[1] > 0 and to_pos[1] < 0:
            t = from_pos[1] / (from_pos[1] - to_pos[1] + 1e-8)
            hit_pos = np.array(from_pos) + (np.array(to_pos)-np.array(from_pos))*t
            return {"hit": True, "position": hit_pos.tolist(), "normal": [0,1,0], "body_id": -1}
        return {"hit": False, "position": to_pos, "normal": [0,1,0]}

    def set_gravity(self, g):
        self.gravity = g
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    p.setGravity(g[0], g[1], g[2], physicsClientId=self.client_id)
                except:
                    pass
        elif self.backend == "pymunk":
            try:
                self.pymunk_space.gravity = (0, g[1])
            except:
                pass

    def step(self, dt=None):
        if dt is None:
            dt = self.time_step

        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    p.stepSimulation(physicsClientId=self.client_id)
                    for body_id in list(self.bodies.keys()):
                        try:
                            pos, orn = p.getBasePositionAndOrientation(body_id, physicsClientId=self.client_id)
                            vel, _ = p.getBaseVelocity(body_id, physicsClientId=self.client_id)
                            self.bodies[body_id].position = np.array(pos, dtype=np.float32)
                            self.bodies[body_id].velocity = np.array(vel, dtype=np.float32)
                        except:
                            pass
                    return
                except Exception as e:
                    print(f"[Physics] PyBullet step failed: {e}")

        if self.backend == "pymunk":
            try:
                self.pymunk_space.step(dt)
                for body in self.bodies.values():
                    if body.pymunk_body is not None:
                        # обновляем 3D позицию из 2D
                        body.position[0] = body.pymunk_body.position[0]
                        body.position[1] = body.pymunk_body.position[1]
                        body.velocity[0] = body.pymunk_body.velocity[0]
                        body.velocity[1] = body.pymunk_body.velocity[1]
                return
            except Exception as e:
                print(f"[Physics] Pymunk step failed: {e}")

        # stub — простая интеграция
        for body in self.bodies.values():
            if body.mass > 0:
                body.velocity[1] += self.gravity[1]*dt
                body.position += body.velocity*dt
                # простая коллизия с землёй y=0
                if body.position[1] < 0.5:
                    body.position[1] = 0.5
                    body.velocity[1] = 0

    def get_body_position(self, body_id):
        b = self.bodies.get(body_id)
        if b:
            return b.position
        return np.zeros(3, dtype=np.float32)

    def set_body_position(self, body_id, pos):
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    p.resetBasePositionAndOrientation(body_id, pos, [0,0,0,1], physicsClientId=self.client_id)
                except:
                    pass
        elif self.backend == "pymunk":
            try:
                b = self.bodies.get(body_id)
                if b and b.pymunk_body is not None:
                    b.pymunk_body.position = (pos[0], pos[1])
            except:
                pass

        if body_id in self.bodies:
            self.bodies[body_id].position = np.array(pos, dtype=np.float32)

    def remove_body(self, body_id):
        if self.backend == "pybullet" and self.client_id is not None:
            with self.lock:
                try:
                    p.removeBody(body_id, physicsClientId=self.client_id)
                except:
                    pass
        elif self.backend == "pymunk":
            try:
                b = self.bodies.get(body_id)
                if b and b.pymunk_body is not None:
                    self.pymunk_space.remove(b.pymunk_body, b.pymunk_shape)
            except:
                pass

        if body_id in self.bodies:
            del self.bodies[body_id]

    def shutdown(self):
        if self.backend == "pybullet" and self.client_id is not None:
            try:
                p.disconnect(physicsClientId=self.client_id)
            except:
                pass
        print(f"[Physics] Shutdown backend={self.backend}")
