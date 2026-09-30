
class HUD:
    def __init__(self):
        self.show_debug = False

    def update(self, player, time_cycle, weather, geiger, anomaly_system, profiler):
        # данные для HUD — в реальном Panda3D это DirectGUI
        # здесь просто собираем строку
        lines = []
        if player:
            lines.append(f"HP: {player.state.health:.0f} | Hunger: {player.needs.hunger:.2f} | Thirst: {player.needs.thirst:.2f}")
            lines.append(f"Rad: {player.needs.radiation:.1f} mSv | Stamina: {player.state.stamina:.0f}")
            lines.append(f"Pos: {player.state.position[0]:.1f}, {player.state.position[1]:.1f}, {player.state.position[2]:.1f}")
        if time_cycle:
            lines.append(f"Time: {time_cycle.get_time_string()} | Sun: {time_cycle.get_sun_intensity():.2f}")
        if weather:
            lines.append(f"Weather: {weather.current_weather} | Fog: {weather.fog_density:.2f}")
        if geiger:
            lines.append(f"Geiger: {geiger.get_display_value():.2f} uSv/h | Clicks: {geiger.click_rate:.1f}/s")
        if profiler and self.show_debug:
            lines.append(profiler.get_text())
        return "\n".join(lines)

    def toggle_debug(self):
        self.show_debug = not self.show_debug
