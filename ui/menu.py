"""
Interactive menu with working buttons, settings, etc.
Panda3D DirectGUI - English version to avoid Cyrillic font issues
"""
from typing import Dict, Optional, Callable, List
import sys

try:
    from direct.gui.DirectGui import (
        DirectFrame, DirectButton, DirectLabel, DirectEntry,
        DirectOptionMenu, DirectSlider, DirectCheckButton
    )
    from panda3d.core import TextNode, LVecBase4f
    HAS_DIRECTGUI = True
except ImportError:
    HAS_DIRECTGUI = False
    print("[Menu] DirectGUI not available, using stub")

from utils.logger import get_logger, LogCategory

class BaseMenu:
    def __init__(self, game):
        self.game = game
        self.logger = get_logger()
        self.elements = []
        self.is_visible = False

    def show(self):
        self.is_visible = True
        for elem in self.elements:
            if hasattr(elem, 'show'):
                elem.show()

    def hide(self):
        self.is_visible = False
        for elem in self.elements:
            if hasattr(elem, 'hide'):
                elem.hide()

    def destroy(self):
        for elem in self.elements:
            if hasattr(elem, 'destroy'):
                elem.destroy()
        self.elements = []

class MainMenu(BaseMenu):
    def __init__(self, game, on_new_game=None, on_load_game=None, on_settings=None, on_exit=None):
        super().__init__(game)
        self.on_new_game = on_new_game
        self.on_load_game = on_load_game
        self.on_settings = on_settings
        self.on_exit = on_exit
        self.seed_input = "1337"
        self.selected_location = "cordon"

        self.logger.log_menu("Initializing main menu")

        if not HAS_DIRECTGUI or game.headless:
            self.logger.warning(LogCategory.MENU, "DirectGUI not available, console mode")
            return

        # Background
        self.bg_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.9),
            frameSize=(-2, 2, -1.5, 1.5),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        # Title
        self.title = DirectLabel(
            text="S.T.A.L.K.E.R.craft",
            scale=0.15,
            pos=(0, 0, 0.9),
            text_fg=(0.8, 0.6, 0.2, 1),
            text_shadow=(0, 0, 0, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.title)

        self.subtitle = DirectLabel(
            text="Procedural Exclusion Zone | Python 3.10 + Panda3D",
            scale=0.05,
            pos=(0, 0, 0.75),
            text_fg=(0.7, 0.7, 0.7, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.subtitle)

        # Buttons
        button_params = {
            "scale": 0.07,
            "frameSize": (-4, 4, -0.5, 1),
            "text_fg": (1, 1, 1, 1),
            "frameColor": ((0.2, 0.2, 0.3, 0.8), (0.3, 0.3, 0.5, 0.9), (0.1, 0.1, 0.2, 0.9), (0.2, 0.2, 0.3, 0.5)),
            "parent": self.bg_frame,
            "text_shadow": (0, 0, 0, 1),
        }

        self.btn_new_game = DirectButton(
            text="New Game",
            pos=(0, 0, 0.4),
            command=self._on_new_game_click,
            **button_params
        )
        self.elements.append(self.btn_new_game)

        self.btn_load_game = DirectButton(
            text="Load Game",
            pos=(0, 0, 0.2),
            command=self._on_load_game_click,
            **button_params
        )
        self.elements.append(self.btn_load_game)

        self.btn_settings = DirectButton(
            text="Settings",
            pos=(0, 0, 0.0),
            command=self._on_settings_click,
            **button_params
        )
        self.elements.append(self.btn_settings)

        self.btn_locations = DirectButton(
            text="Zone Map",
            pos=(0, 0, -0.2),
            command=self._on_locations_click,
            **button_params
        )
        self.elements.append(self.btn_locations)

        self.btn_exit = DirectButton(
            text="Exit",
            pos=(0, 0, -0.5),
            command=self._on_exit_click,
            **button_params
        )
        self.elements.append(self.btn_exit)

        # Seed input
        self.seed_label = DirectLabel(
            text="World Seed:",
            scale=0.05,
            pos=(-0.8, 0, -0.8),
            text_fg=(0.8, 0.8, 0.8, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.seed_label)

        self.seed_entry = DirectEntry(
            text="1337",
            scale=0.05,
            pos=(-0.4, 0, -0.8),
            width=10,
            numLines=1,
            frameColor=(0.1, 0.1, 0.15, 0.9),
            text_fg=(1, 1, 1, 1),
            command=self._on_seed_changed,
            parent=self.bg_frame
        )
        self.elements.append(self.seed_entry)

        # Location selection
        self.loc_label = DirectLabel(
            text="Start Location:",
            scale=0.05,
            pos=(0.2, 0, -0.8),
            text_fg=(0.8, 0.8, 0.8, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.loc_label)

        try:
            from world.location_system import LOCATION_DEFINITIONS
            loc_names = [f"{loc_id} - {loc_def.display_name}" for loc_id, loc_def in LOCATION_DEFINITIONS.items()]
            self.location_menu = DirectOptionMenu(
                text="Cordon",
                scale=0.05,
                items=loc_names,
                initialitem=0,
                pos=(0.7, 0, -0.8),
                frameColor=(0.1, 0.1, 0.15, 0.9),
                text_fg=(1, 1, 1, 1),
                command=self._on_location_selected,
                parent=self.bg_frame
            )
            self.elements.append(self.location_menu)
        except Exception as e:
            self.logger.error(LogCategory.MENU, f"Failed to create location menu: {e}")

        # Version
        self.version_label = DirectLabel(
            text="v0.2.1 | Python 3.10.0 | Panda3D 1.10.14 | Procedural",
            scale=0.035,
            pos=(0, 0, -1.3),
            text_fg=(0.5, 0.5, 0.5, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.version_label)

        self.hide()
        self.logger.log_menu("Main menu created with DirectGUI")

    def _on_seed_changed(self, text):
        self.seed_input = text
        self.logger.log_menu(f"Seed changed to {text}")

    def _on_location_selected(self, selection):
        loc_id = selection.split(" - ")[0]
        self.selected_location = loc_id
        self.logger.log_menu(f"Selected start location: {loc_id}")

    def _on_new_game_click(self):
        self.logger.log_menu(f"New Game clicked, seed={self.seed_input}, location={self.selected_location}")
        seed = int(self.seed_input) if self.seed_input.isdigit() else 1337
        if self.on_new_game:
            self.on_new_game(seed, self.selected_location)

    def _on_load_game_click(self):
        self.logger.log_menu("Load Game clicked")
        if self.on_load_game:
            self.on_load_game()

    def _on_settings_click(self):
        self.logger.log_menu("Settings clicked")
        if self.on_settings:
            self.on_settings()

    def _on_locations_click(self):
        self.logger.log_menu("Zone Map clicked")
        if hasattr(self.game, 'show_location_map'):
            self.game.show_location_map()

    def _on_exit_click(self):
        self.logger.log_menu("Exit clicked")
        if self.on_exit:
            self.on_exit()
        else:
            sys.exit(0)

class SettingsMenu(BaseMenu):
    def __init__(self, game, on_back=None):
        super().__init__(game)
        self.on_back = on_back
        self.logger.log_menu("Initializing settings menu")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.95),
            frameSize=(-1.5, 1.5, -1.2, 1.2),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.title = DirectLabel(
            text="Settings",
            scale=0.1,
            pos=(0, 0, 0.9),
            text_fg=(0.8, 0.6, 0.2, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.title)

        y = 0.6
        self.gfx_label = DirectLabel(
            text="Graphics:",
            scale=0.06,
            pos=(-1.0, 0, y),
            text_fg=(1, 1, 1, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.gfx_label)

        self.view_dist_label = DirectLabel(
            text="View Distance (chunks):",
            scale=0.04,
            pos=(-1.0, 0, y-0.15),
            text_fg=(0.8, 0.8, 0.8, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.view_dist_label)

        self.view_dist_slider = DirectSlider(
            range=(2, 10),
            value=5,
            pageSize=1,
            scale=0.3,
            pos=(0.5, 0, y-0.15),
            command=self._on_view_dist_changed,
            parent=self.bg_frame
        )
        self.elements.append(self.view_dist_slider)

        self.shadows_check = DirectCheckButton(
            text="Shadows",
            scale=0.05,
            pos=(-1.0, 0, y-0.3),
            command=self._on_shadows_toggled,
            parent=self.bg_frame
        )
        self.elements.append(self.shadows_check)

        self.fog_check = DirectCheckButton(
            text="Fog",
            scale=0.05,
            pos=(-0.3, 0, y-0.3),
            command=self._on_fog_toggled,
            parent=self.bg_frame
        )
        self.elements.append(self.fog_check)

        y -= 0.5
        self.audio_label = DirectLabel(
            text="Audio:",
            scale=0.06,
            pos=(-1.0, 0, y),
            text_fg=(1, 1, 1, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.audio_label)

        self.volume_slider = DirectSlider(
            range=(0, 100),
            value=80,
            pageSize=5,
            scale=0.3,
            pos=(0.5, 0, y-0.15),
            command=self._on_volume_changed,
            parent=self.bg_frame
        )
        self.elements.append(self.volume_slider)

        y -= 0.5
        self.controls_label = DirectLabel(
            text="Controls: WASD move, Shift run, Ctrl crouch, LMB dig, RMB build, F3 debug, F5 save, F8 console, Esc pause, M mouse lock",
            scale=0.035,
            pos=(0, 0, y),
            text_fg=(0.7, 0.7, 0.7, 1),
            frameColor=(0, 0, 0, 0),
            text_wordwrap=20,
            parent=self.bg_frame
        )
        self.elements.append(self.controls_label)

        self.btn_back = DirectButton(
            text="Back",
            scale=0.06,
            pos=(0, 0, -0.9),
            frameSize=(-3, 3, -0.5, 1),
            command=self._on_back_click,
            parent=self.bg_frame
        )
        self.elements.append(self.btn_back)

        self.hide()

    def _on_view_dist_changed(self):
        val = int(self.view_dist_slider['value'])
        self.logger.log_menu(f"View distance changed to {val}")

    def _on_shadows_toggled(self, value):
        self.logger.log_menu(f"Shadows toggled: {value}")

    def _on_fog_toggled(self, value):
        self.logger.log_menu(f"Fog toggled: {value}")

    def _on_volume_changed(self):
        val = int(self.volume_slider['value'])
        self.logger.log_menu(f"Volume changed to {val}%")

    def _on_back_click(self):
        self.logger.log_menu("Back from settings")
        self.hide()
        if self.on_back:
            self.on_back()

class PauseMenu(BaseMenu):
    def __init__(self, game, on_resume=None, on_save=None, on_load=None, on_settings=None, on_exit_to_menu=None):
        super().__init__(game)
        self.on_resume = on_resume
        self.on_save = on_save
        self.on_load = on_load
        self.on_settings = on_settings
        self.on_exit_to_menu = on_exit_to_menu

        self.logger.log_menu("Initializing pause menu")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.9),
            frameSize=(-1, 1, -1, 1),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.title = DirectLabel(
            text="Pause",
            scale=0.12,
            pos=(0, 0, 0.7),
            text_fg=(0.8, 0.6, 0.2, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.title)

        btn_params = {
            "scale": 0.06,
            "frameSize": (-4, 4, -0.5, 1),
            "text_fg": (1, 1, 1, 1),
            "parent": self.bg_frame,
        }

        self.btn_resume = DirectButton(text="Resume", pos=(0,0,0.4), command=self._on_resume, **btn_params)
        self.elements.append(self.btn_resume)

        self.btn_save = DirectButton(text="Save (F5)", pos=(0,0,0.2), command=self._on_save, **btn_params)
        self.elements.append(self.btn_save)

        self.btn_load = DirectButton(text="Load", pos=(0,0,0.0), command=self._on_load, **btn_params)
        self.elements.append(self.btn_load)

        self.btn_settings = DirectButton(text="Settings", pos=(0,0,-0.2), command=self._on_settings, **btn_params)
        self.elements.append(self.btn_settings)

        self.btn_exit = DirectButton(text="Exit to Menu", pos=(0,0,-0.5), command=self._on_exit_to_menu, **btn_params)
        self.elements.append(self.btn_exit)

        self.hide()

    def _on_resume(self):
        self.logger.log_menu("Resume")
        self.hide()
        if self.on_resume:
            self.on_resume()

    def _on_save(self):
        self.logger.log_menu("Save")
        if self.on_save:
            self.on_save()

    def _on_load(self):
        self.logger.log_menu("Load")
        if self.on_load:
            self.on_load()

    def _on_settings(self):
        self.logger.log_menu("Settings from pause")
        if self.on_settings:
            self.on_settings()

    def _on_exit_to_menu(self):
        self.logger.log_menu("Exit to Menu")
        self.hide()
        if self.on_exit_to_menu:
            self.on_exit_to_menu()

class LocationMapMenu(BaseMenu):
    def __init__(self, game, location_system, on_select_location=None, on_back=None):
        super().__init__(game)
        self.location_system = location_system
        self.on_select_location = on_select_location
        self.on_back = on_back

        self.logger.log_menu("Initializing Zone Map")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0.02, 0.05, 0.02, 0.95),
            frameSize=(-2, 2, -1.5, 1.5),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.title = DirectLabel(
            text="Exclusion Zone Map",
            scale=0.08,
            pos=(0, 0, 1.2),
            text_fg=(0.2, 0.8, 0.2, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.title)

        try:
            from world.location_system import LOCATION_DEFINITIONS
            loc_positions = {
                "cordon": (-1.2, 0.8),
                "garbage": (-0.6, 0.6),
                "dark_valley": (-1.2, 0.2),
                "agroprom": (0.0, 0.4),
                "bar": (0.0, 0.0),
                "wild_territory": (0.6, -0.2),
                "yantar": (0.0, -0.4),
                "army_warehouses": (-0.6, -0.2),
                "red_forest": (0.6, -0.6),
                "jupiter": (1.2, -0.4),
                "zaton": (1.5, -0.8),
                "skadovsk": (1.2, -1.0),
                "pripyat": (1.2, 0.2),
                "sarcophagus": (1.5, 0.6),
            }

            for loc_id, (x, z) in loc_positions.items():
                loc_def = LOCATION_DEFINITIONS.get(loc_id)
                if not loc_def:
                    continue

                rad = loc_def.radiation_level
                if rad < 0.2:
                    color = (0.2, 0.8, 0.2, 0.8)
                elif rad < 0.5:
                    color = (0.8, 0.8, 0.2, 0.8)
                elif rad < 0.8:
                    color = (0.8, 0.4, 0.2, 0.8)
                else:
                    color = (0.8, 0.2, 0.2, 0.8)

                btn = DirectButton(
                    text=loc_def.display_name,
                    scale=0.04,
                    pos=(x, 0, z),
                    frameSize=(-2, 2, -0.3, 0.8),
                    frameColor=color,
                    text_fg=(1, 1, 1, 1),
                    command=self._on_location_click,
                    extraArgs=[loc_id],
                    parent=self.bg_frame
                )
                self.elements.append(btn)

            self.info_label = DirectLabel(
                text="Click location to teleport (cheat) or view info\nGreen - safe, Red - deadly\nLines - transitions",
                scale=0.035,
                pos=(0, 0, -1.1),
                text_fg=(0.7, 0.7, 0.7, 1),
                frameColor=(0, 0, 0, 0),
                parent=self.bg_frame
            )
            self.elements.append(self.info_label)

        except Exception as e:
            self.logger.error(LogCategory.MENU, f"Error creating map: {e}")

        self.btn_back = DirectButton(
            text="Back",
            scale=0.06,
            pos=(0, 0, -1.3),
            command=self._on_back,
            parent=self.bg_frame
        )
        self.elements.append(self.btn_back)

        self.hide()

    def _on_location_click(self, loc_id):
        self.logger.log_menu(f"Location clicked {loc_id}")
        if self.on_select_location:
            self.on_select_location(loc_id)

    def _on_back(self):
        self.hide()
        if self.on_back:
            self.on_back()

class LoadingScreen(BaseMenu):
    def __init__(self, game):
        super().__init__(game)
        self.logger.log_menu("Initializing loading screen")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0, 0, 0, 1),
            frameSize=(-2, 2, -1.5, 1.5),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.label = DirectLabel(
            text="Loading...",
            scale=0.1,
            pos=(0, 0, 0.2),
            text_fg=(1, 1, 1, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.label)

        self.progress_label = DirectLabel(
            text="0%",
            scale=0.06,
            pos=(0, 0, -0.1),
            text_fg=(0.8, 0.8, 0.8, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.progress_label)

        self.details_label = DirectLabel(
            text="",
            scale=0.04,
            pos=(0, 0, -0.3),
            text_fg=(0.6, 0.6, 0.6, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.details_label)

        self.hide()

    def update_progress(self, percent, details=""):
        if not HAS_DIRECTGUI:
            return
        self.progress_label['text'] = f"{percent:.0f}%"
        self.details_label['text'] = details
