
import shlex

class GameConsole:
    def __init__(self, game):
        self.game = game
        self.is_open = False
        self.history = []
        self.output = []
        self.commands = {
            "give": self.cmd_give,
            "spawn": self.cmd_spawn,
            "spawn_anomaly": self.cmd_spawn_anomaly,
            "spawn_artifact": self.cmd_spawn_artifact,
            "teleport": self.cmd_teleport,
            "set_radiation": self.cmd_set_radiation,
            "set_time": self.cmd_set_time,
            "set_weather": self.cmd_set_weather,
            "god": self.cmd_god,
            "noclip": self.cmd_noclip,
            "kill_all": self.cmd_kill_all,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "regen_assets": self.cmd_regen_assets,
            "set_seed": self.cmd_set_seed,
            "help": self.cmd_help,
        }

    def toggle(self):
        self.is_open = not self.is_open

    def execute(self, text):
        self.history.append(text)
        self.output.append(f"> {text}")
        parts = shlex.split(text)
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]
        if cmd in self.commands:
            try:
                result = self.commands[cmd](args)
                self.output.append(str(result))
            except Exception as e:
                self.output.append(f"Error: {e}")
        else:
            self.output.append(f"Unknown command: {cmd}. Type help")

    def cmd_give(self, args):
        if not args:
            return "Usage: give <item> [count]"
        item = args[0]
        count = int(args[1]) if len(args)>1 else 1
        if hasattr(self.game, 'player'):
            self.game.player.inventory.add_item(item, count, seed=0)
            return f"Gave {count}x {item}"
        return "No player"

    def cmd_spawn(self, args):
        if not args:
            return "Usage: spawn <entity> [count] [x y z]"
        entity = args[0]
        count = int(args[1]) if len(args)>1 and args[1].isdigit() else 1
        # позиция
        if len(args) >= 5:
            x,y,z = float(args[2]), float(args[3]), float(args[4])
            pos = (x,y,z)
        else:
            pos = None
        if hasattr(self.game, 'spawn_manager'):
            for _ in range(count):
                self.game.spawn_manager.spawn_animal(entity, position=pos)
            return f"Spawned {count}x {entity}"
        return "No spawn manager"

    def cmd_spawn_anomaly(self, args):
        if not args:
            return "Usage: spawn_anomaly <type> [x y z]"
        atype = args[0]
        if len(args) >= 4:
            x,y,z = float(args[1]), float(args[2]), float(args[3])
            pos = (x,y,z)
        else:
            if hasattr(self.game, 'player'):
                pos = self.game.player.state.position + [5,0,0]
            else:
                pos = (0,0,0)
        if hasattr(self.game, 'anomaly_system'):
            self.game.anomaly_system.spawn_anomaly(atype, pos)
            return f"Spawned anomaly {atype} at {pos}"
        return "No anomaly system"

    def cmd_spawn_artifact(self, args):
        if not args:
            return "Usage: spawn_artifact <type> [x y z]"
        atype = args[0]
        if len(args) >= 4:
            x,y,z = float(args[1]), float(args[2]), float(args[3])
            pos = (x,y,z)
        else:
            pos = (0,0,0)
        if hasattr(self.game, 'artifact_system'):
            self.game.artifact_system.spawn_artifact(atype, pos)
            return f"Spawned artifact {atype} at {pos}"
        return "No artifact system"

    def cmd_teleport(self, args):
        if len(args) < 3:
            return "Usage: teleport <x y z>"
        x,y,z = float(args[0]), float(args[1]), float(args[2])
        if hasattr(self.game, 'player'):
            self.game.player.state.position = __import__('numpy').array([x,y,z], dtype=__import__('numpy').float32)
            return f"Teleported to {x},{y},{z}"
        return "No player"

    def cmd_set_radiation(self, args):
        if not args:
            return "Usage: set_radiation <value>"
        val = float(args[0])
        if hasattr(self.game, 'player'):
            self.game.player.needs.radiation = val
            return f"Radiation set to {val}"
        return "No player"

    def cmd_set_time(self, args):
        if not args:
            return "Usage: set_time <hour>"
        hour = float(args[0])
        if hasattr(self.game, 'time_cycle'):
            self.game.time_cycle.set_time(hour)
            return f"Time set to {hour}"
        return "No time cycle"

    def cmd_set_weather(self, args):
        if not args:
            return "Usage: set_weather <type>"
        wtype = args[0]
        if hasattr(self.game, 'weather'):
            self.game.weather.set_weather(wtype)
            return f"Weather set to {wtype}"
        return "No weather"

    def cmd_god(self, args):
        if hasattr(self.game, 'player'):
            self.game.player.state.health = 1000
            self.game.god_mode = not getattr(self.game, 'god_mode', False)
            return f"God mode: {self.game.god_mode}"
        return "No player"

    def cmd_noclip(self, args):
        self.game.noclip = not getattr(self.game, 'noclip', False)
        return f"Noclip: {self.game.noclip}"

    def cmd_kill_all(self, args):
        if hasattr(self.game, 'spawn_manager'):
            self.game.spawn_manager.kill_all()
            return "Killed all entities"
        return "No spawn manager"

    def cmd_save(self, args):
        if hasattr(self.game, 'save_manager'):
            name = args[0] if args else "quicksave"
            self.game.save_manager.save_game(name, self.game.get_save_data())
            return f"Saved {name}"
        return "No save manager"

    def cmd_load(self, args):
        if hasattr(self.game, 'save_manager'):
            name = args[0] if args else "quicksave"
            data = self.game.save_manager.load_game(name)
            if data:
                self.game.load_save_data(data)
                return f"Loaded {name}"
            return f"Save {name} not found"
        return "No save manager"

    def cmd_regen_assets(self, args):
        atype = args[0] if args else "all"
        from utils.asset_cache import global_cache
        if atype == "all":
            global_cache.clear_disk()
            return "Cleared all asset cache"
        else:
            global_cache.clear_disk(category=atype)
            return f"Cleared cache for {atype}"

    def cmd_set_seed(self, args):
        if not args:
            return "Usage: set_seed <int>"
        seed = int(args[0])
        self.game.world_seed = seed
        return f"Seed set to {seed} (restart needed for full effect)"

    def cmd_help(self, args):
        return "Commands: " + ", ".join(self.commands.keys())

    def get_output_text(self, lines=10):
        return "\n".join(self.output[-lines:])
