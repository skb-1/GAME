
import os
import pickle
import zlib
import time
import json
from typing import Dict, Optional
from config import SAVE_DIR

class SaveManager:
    def __init__(self, save_dir=SAVE_DIR):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def save_game(self, name, data):
        # data: dict
        # сохраняем через pickle+zlib (как требовалось)
        path = os.path.join(self.save_dir, f"{name}.save")
        try:
            pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            compressed = zlib.compress(pickled, level=6)
            with open(path, "wb") as f:
                f.write(compressed)
            # также json для отладки
            json_path = os.path.join(self.save_dir, f"{name}.json")
            # упрощённый json — только мета
            meta = {"timestamp": time.time(), "seed": data.get("world_seed"), "player_pos": data.get("player", {}).get("position")}
            with open(json_path, "w") as jf:
                json.dump(meta, jf, indent=2)
            return True
        except Exception as e:
            print(f"[SaveManager] Save failed: {e}")
            return False

    def load_game(self, name):
        path = os.path.join(self.save_dir, f"{name}.save")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                compressed = f.read()
            pickled = zlib.decompress(compressed)
            data = pickle.loads(pickled)
            return data
        except Exception as e:
            print(f"[SaveManager] Load failed: {e}")
            return None

    def list_saves(self):
        saves = []
        for fname in os.listdir(self.save_dir):
            if fname.endswith(".save"):
                name = fname[:-5]
                path = os.path.join(self.save_dir, fname)
                mtime = os.path.getmtime(path)
                saves.append({"name": name, "mtime": mtime})
        saves.sort(key=lambda x: x["mtime"], reverse=True)
        return saves

    def delete_save(self, name):
        path = os.path.join(self.save_dir, f"{name}.save")
        if os.path.exists(path):
            os.remove(path)
            json_path = os.path.join(self.save_dir, f"{name}.json")
            if os.path.exists(json_path):
                os.remove(json_path)
            return True
        return False

    def autosave(self, data):
        return self.save_game("autosave", data)
