"""
Интерактивное меню с рабочими кнопками, настройками и т.д.
Panda3D DirectGUI
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
    print("[Menu] DirectGUI не доступен, используется заглушка")

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

        self.logger.log_menu("Инициализация главного меню")

        if not HAS_DIRECTGUI or game.headless:
            self.logger.warning(LogCategory.MENU, "DirectGUI не доступен, меню в консольном режиме")
            return

        # Фон
        self.bg_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.9),
            frameSize=(-2, 2, -1.5, 1.5),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        # Заголовок
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
            text="Процедурная Зона Отчуждения | Python 3.10 + Panda3D",
            scale=0.05,
            pos=(0, 0, 0.75),
            text_fg=(0.7, 0.7, 0.7, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.subtitle)

        # Кнопки
        button_params = {
            "scale": 0.07,
            "frameSize": (-4, 4, -0.5, 1),
            "text_fg": (1, 1, 1, 1),
            "frameColor": ((0.2, 0.2, 0.3, 0.8), (0.3, 0.3, 0.5, 0.9), (0.1, 0.1, 0.2, 0.9), (0.2, 0.2, 0.3, 0.5)),
            "parent": self.bg_frame,
            "text_shadow": (0, 0, 0, 1),
        }

        self.btn_new_game = DirectButton(
            text="Новая игра",
            pos=(0, 0, 0.4),
            command=self._on_new_game_click,
            **button_params
        )
        self.elements.append(self.btn_new_game)

        self.btn_load_game = DirectButton(
            text="Загрузить игру",
            pos=(0, 0, 0.2),
            command=self._on_load_game_click,
            **button_params
        )
        self.elements.append(self.btn_load_game)

        self.btn_settings = DirectButton(
            text="Настройки",
            pos=(0, 0, 0.0),
            command=self._on_settings_click,
            **button_params
        )
        self.elements.append(self.btn_settings)

        self.btn_locations = DirectButton(
            text="Карта Зоны",
            pos=(0, 0, -0.2),
            command=self._on_locations_click,
            **button_params
        )
        self.elements.append(self.btn_locations)

        self.btn_exit = DirectButton(
            text="Выход",
            pos=(0, 0, -0.5),
            command=self._on_exit_click,
            **button_params
        )
        self.elements.append(self.btn_exit)

        # Seed ввод
        self.seed_label = DirectLabel(
            text="Seed мира:",
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

        # Локация стартовая
        self.loc_label = DirectLabel(
            text="Стартовая локация:",
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
                text="Кордон",
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
            self.logger.error(LogCategory.MENU, f"Не удалось создать меню локаций: {e}")

        # Версия
        self.version_label = DirectLabel(
            text="v0.2.0 | Python 3.10.0 | Panda3D 1.10.14 | Процедурная генерация",
            scale=0.035,
            pos=(0, 0, -1.3),
            text_fg=(0.5, 0.5, 0.5, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.version_label)

        self.hide()
        self.logger.log_menu("Главное меню создано с DirectGUI")

    def _on_seed_changed(self, text):
        self.seed_input = text
        self.logger.log_menu(f"Seed изменён на {text}")

    def _on_location_selected(self, selection):
        # selection вида "cordon - Кордон"
        loc_id = selection.split(" - ")[0]
        self.selected_location = loc_id
        self.logger.log_menu(f"Выбрана стартовая локация: {loc_id}")

    def _on_new_game_click(self):
        self.logger.log_menu(f"Нажата Новая игра, seed={self.seed_input}, location={self.selected_location}")
        seed = int(self.seed_input) if self.seed_input.isdigit() else 1337
        if self.on_new_game:
            self.on_new_game(seed, self.selected_location)

    def _on_load_game_click(self):
        self.logger.log_menu("Нажата Загрузить игру")
        if self.on_load_game:
            self.on_load_game()

    def _on_settings_click(self):
        self.logger.log_menu("Нажата Настройки")
        if self.on_settings:
            self.on_settings()

    def _on_locations_click(self):
        self.logger.log_menu("Нажата Карта Зоны")
        # Показываем карту локаций
        if hasattr(self.game, 'show_location_map'):
            self.game.show_location_map()

    def _on_exit_click(self):
        self.logger.log_menu("Нажата Выход")
        if self.on_exit:
            self.on_exit()
        else:
            sys.exit(0)

    def handle_input(self, key):
        # Для совместимости со старой системой
        if key == "up":
            pass
        elif key == "down":
            pass
        elif key == "enter":
            self._on_new_game_click()

class SettingsMenu(BaseMenu):
    def __init__(self, game, on_back=None):
        super().__init__(game)
        self.on_back = on_back
        self.logger.log_menu("Инициализация меню настроек")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.95),
            frameSize=(-1.5, 1.5, -1.2, 1.2),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.title = DirectLabel(
            text="Настройки",
            scale=0.1,
            pos=(0, 0, 0.9),
            text_fg=(0.8, 0.6, 0.2, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.title)

        # Графика
        y = 0.6
        self.gfx_label = DirectLabel(
            text="Графика:",
            scale=0.06,
            pos=(-1.0, 0, y),
            text_fg=(1, 1, 1, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.gfx_label)

        # View distance slider
        self.view_dist_label = DirectLabel(
            text="Дальность прорисовки чанков:",
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

        # Тени checkbox
        self.shadows_check = DirectCheckButton(
            text="Тени",
            scale=0.05,
            pos=(-1.0, 0, y-0.3),
            command=self._on_shadows_toggled,
            parent=self.bg_frame
        )
        self.elements.append(self.shadows_check)

        # Туман checkbox
        self.fog_check = DirectCheckButton(
            text="Туман",
            scale=0.05,
            pos=(-0.3, 0, y-0.3),
            command=self._on_fog_toggled,
            parent=self.bg_frame
        )
        self.elements.append(self.fog_check)

        # Звук
        y -= 0.5
        self.audio_label = DirectLabel(
            text="Звук:",
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

        # Управление
        y -= 0.5
        self.controls_label = DirectLabel(
            text="Управление: WASD движение, Shift бег, Ctrl присед, ЛКМ копать, F3 дебаг, F5 сохранить, F8 консоль, Esc пауза",
            scale=0.035,
            pos=(0, 0, y),
            text_fg=(0.7, 0.7, 0.7, 1),
            frameColor=(0, 0, 0, 0),
            text_wordwrap=20,
            parent=self.bg_frame
        )
        self.elements.append(self.controls_label)

        # Кнопка назад
        self.btn_back = DirectButton(
            text="Назад",
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
        self.logger.log_menu(f"Дальность прорисовки изменена на {val}")
        if hasattr(self.game, 'config'):
            # Обновляем конфиг
            pass

    def _on_shadows_toggled(self, value):
        self.logger.log_menu(f"Тени toggled: {value}")

    def _on_fog_toggled(self, value):
        self.logger.log_menu(f"Туман toggled: {value}")

    def _on_volume_changed(self):
        val = int(self.volume_slider['value'])
        self.logger.log_menu(f"Громкость изменена на {val}%")

    def _on_back_click(self):
        self.logger.log_menu("Нажата Назад в настройках")
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

        self.logger.log_menu("Инициализация паузы")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.9),
            frameSize=(-1, 1, -1, 1),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.title = DirectLabel(
            text="Пауза",
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

        self.btn_resume = DirectButton(text="Продолжить", pos=(0,0,0.4), command=self._on_resume, **btn_params)
        self.elements.append(self.btn_resume)

        self.btn_save = DirectButton(text="Сохранить (F5)", pos=(0,0,0.2), command=self._on_save, **btn_params)
        self.elements.append(self.btn_save)

        self.btn_load = DirectButton(text="Загрузить", pos=(0,0,0.0), command=self._on_load, **btn_params)
        self.elements.append(self.btn_load)

        self.btn_settings = DirectButton(text="Настройки", pos=(0,0,-0.2), command=self._on_settings, **btn_params)
        self.elements.append(self.btn_settings)

        self.btn_exit = DirectButton(text="Выход в меню", pos=(0,0,-0.5), command=self._on_exit_to_menu, **btn_params)
        self.elements.append(self.btn_exit)

        self.hide()

    def _on_resume(self):
        self.logger.log_menu("Продолжить")
        self.hide()
        if self.on_resume:
            self.on_resume()

    def _on_save(self):
        self.logger.log_menu("Сохранить")
        if self.on_save:
            self.on_save()

    def _on_load(self):
        self.logger.log_menu("Загрузить")
        if self.on_load:
            self.on_load()

    def _on_settings(self):
        self.logger.log_menu("Настройки из паузы")
        if self.on_settings:
            self.on_settings()

    def _on_exit_to_menu(self):
        self.logger.log_menu("Выход в меню")
        self.hide()
        if self.on_exit_to_menu:
            self.on_exit_to_menu()

class LocationMapMenu(BaseMenu):
    """Карта Зоны с локациями и переходами."""

    def __init__(self, game, location_system, on_select_location=None, on_back=None):
        super().__init__(game)
        self.location_system = location_system
        self.on_select_location = on_select_location
        self.on_back = on_back

        self.logger.log_menu("Инициализация карты Зоны")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0.02, 0.05, 0.02, 0.95),
            frameSize=(-2, 2, -1.5, 1.5),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.title = DirectLabel(
            text="Карта Зоны Отчуждения",
            scale=0.08,
            pos=(0, 0, 1.2),
            text_fg=(0.2, 0.8, 0.2, 1),
            frameColor=(0, 0, 0, 0),
            parent=self.bg_frame
        )
        self.elements.append(self.title)

        # Создаём кнопки для каждой локации в виде сетки
        try:
            from world.location_system import LOCATION_DEFINITIONS
            # Позиции локаций на карте (упрощённо по логике связей)
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

                # Цвет по радиации
                rad = loc_def.radiation_level
                if rad < 0.2:
                    color = (0.2, 0.8, 0.2, 0.8)  # зелёный безопасно
                elif rad < 0.5:
                    color = (0.8, 0.8, 0.2, 0.8)  # жёлтый
                elif rad < 0.8:
                    color = (0.8, 0.4, 0.2, 0.8)  # оранжевый
                else:
                    color = (0.8, 0.2, 0.2, 0.8)  # красный опасно

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

            # Линии связей — упрощённо через лейблы
            # В реальном — LineSegs, но для простоты текст
            self.info_label = DirectLabel(
                text="Кликните на локацию для телепорта (читерство) или просмотра инфо\nЗелёный - безопасно, Красный - смертельно опасно\nЛинии - переходы между локациями",
                scale=0.035,
                pos=(0, 0, -1.1),
                text_fg=(0.7, 0.7, 0.7, 1),
                frameColor=(0, 0, 0, 0),
                parent=self.bg_frame
            )
            self.elements.append(self.info_label)

        except Exception as e:
            self.logger.error(LogCategory.MENU, f"Ошибка создания карты: {e}")

        self.btn_back = DirectButton(
            text="Назад",
            scale=0.06,
            pos=(0, 0, -1.3),
            command=self._on_back,
            parent=self.bg_frame
        )
        self.elements.append(self.btn_back)

        self.hide()

    def _on_location_click(self, loc_id):
        self.logger.log_menu(f"Клик по локации {loc_id}")
        if self.on_select_location:
            self.on_select_location(loc_id)

    def _on_back(self):
        self.hide()
        if self.on_back:
            self.on_back()

class LoadingScreen(BaseMenu):
    def __init__(self, game):
        super().__init__(game)
        self.logger.log_menu("Инициализация экрана загрузки")

        if not HAS_DIRECTGUI or game.headless:
            return

        self.bg_frame = DirectFrame(
            frameColor=(0, 0, 0, 1),
            frameSize=(-2, 2, -1.5, 1.5),
            pos=(0, 0, 0)
        )
        self.elements.append(self.bg_frame)

        self.label = DirectLabel(
            text="Загрузка...",
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

# Совместимость со старым кодом
class MainMenuOld:
    def __init__(self, game):
        self.game = game
        self.options = ["Новая игра", "Загрузить", "Настройки", "Выход"]
        self.selected = 0
        self.seed_input = "1337"

    def handle_input(self, key):
        if key == "up":
            self.selected = (self.selected - 1) % len(self.options)
        elif key == "down":
            self.selected = (self.selected + 1) % len(self.options)
        elif key == "enter":
            return self.activate()
        return None

    def activate(self):
        choice = self.options[self.selected]
        if choice == "Новая игра":
            return {"action": "new_game", "seed": int(self.seed_input) if self.seed_input.isdigit() else 1337}
        elif choice == "Загрузить":
            return {"action": "load_game"}
        elif choice == "Настройки":
            return {"action": "settings"}
        elif choice == "Выход":
            return {"action": "exit"}
        return None
