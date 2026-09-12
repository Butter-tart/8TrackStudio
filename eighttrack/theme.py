"""Theme and colour accent system for 8T DAW."""

from dataclasses import dataclass
from typing import List, Tuple


THEME_PRESETS = [
    ("light", "Studio Light (Classic)"),
    ("dark", "Studio Dark"),
    ("midnight", "Midnight Blue"),
    ("retro", "Retro Tape"),
    ("slate", "Slate Gray"),
]

ACCENT_PRESETS = [
    ("teal", "Teal (Default)", "#168777"),
    ("blue", "Ocean Blue", "#2b77ad"),
    ("amber", "Amber Gold", "#c6811e"),
    ("ruby", "Ruby Crimson", "#c7434e"),
    ("purple", "Purple Violet", "#8b4fc7"),
    ("orange", "Sunset Orange", "#d96338"),
    ("sage", "Sage Green", "#4b8b64"),
    ("cyan", "Electric Cyan", "#0097a7"),
]

DEFAULT_TRACK_COLORS = [
    "#168777", "#3676b2", "#b27b17", "#ac556b",
    "#598137", "#5577a0", "#a55e35", "#6c7280",
]


def clamp(val: float, low: float = 0.0, high: float = 255.0) -> int:
    return int(max(low, min(high, round(val))))


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        return (22, 135, 119)
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{clamp(r):02x}{clamp(g):02x}{clamp(b):02x}"


def adjust_color(hex_str: str, factor: float) -> str:
    """Adjust color brightness. factor > 1.0 is lighter, < 1.0 is darker."""
    r, g, b = hex_to_rgb(hex_str)
    return rgb_to_hex(r * factor, g * factor, b * factor)


def mix_colors(hex1: str, hex2: str, weight: float = 0.5) -> str:
    """Mix two hex colors. weight is the proportion of hex1 (0.0 to 1.0)."""
    r1, g1, b1 = hex_to_rgb(hex1)
    r2, g2, b2 = hex_to_rgb(hex2)
    w = max(0.0, min(1.0, weight))
    return rgb_to_hex(r1 * w + r2 * (1 - w), g1 * w + g2 * (1 - w), b1 * w + b2 * (1 - w))


@dataclass
class ThemePalette:
    name: str
    accent: str
    bg_main: str
    bg_dialog: str
    bg_panel: str
    bg_input: str
    bg_button: str
    bg_button_hover: str
    bg_button_disabled: str
    text_main: str
    text_muted: str
    text_disabled: str
    border_main: str
    border_light: str
    clock_bg: str
    clock_text: str
    waveform_bg: str
    waveform_grid: str
    waveform_playhead: str
    meter_bg: str
    meter_border: str
    meter_text: str
    meter_normal: str
    meter_clip: str
    track_colors: List[str]


def get_theme_palette(theme_name: str = "light", accent_color: str = "#168777") -> ThemePalette:
    theme_key = theme_name.lower().strip()
    accent = accent_color if accent_color.startswith("#") else f"#{accent_color}"

    # Generate custom track colors with track 1 using the accent color
    track_colors = list(DEFAULT_TRACK_COLORS)
    track_colors[0] = accent

    if theme_key == "dark":
        hover_bg = mix_colors(accent, "#272d2a", 0.2)
        return ThemePalette(
            name="dark",
            accent=accent,
            bg_main="#1e2220",
            bg_dialog="#232825",
            bg_panel="#272d2a",
            bg_input="#2a312d",
            bg_button="#2d3531",
            bg_button_hover=hover_bg,
            bg_button_disabled="#1b1f1d",
            text_main="#e4ece6",
            text_muted="#9aa8a0",
            text_disabled="#5f6963",
            border_main="#3d4742",
            border_light="#48544e",
            clock_bg="#111613",
            clock_text="#8eedc0",
            waveform_bg="#141a17",
            waveform_grid="#2a3830",
            waveform_playhead="#ffd700",
            meter_bg="#151b18",
            meter_border="#35443a",
            meter_text="#7e9185",
            meter_normal="#8eedc0",
            meter_clip="#e74c3c",
            track_colors=track_colors,
        )
    elif theme_key == "midnight":
        hover_bg = mix_colors(accent, "#1c2230", 0.25)
        return ThemePalette(
            name="midnight",
            accent=accent,
            bg_main="#121620",
            bg_dialog="#181e2b",
            bg_panel="#1c2230",
            bg_input="#22293a",
            bg_button="#252d40",
            bg_button_hover=hover_bg,
            bg_button_disabled="#151a24",
            text_main="#e2e8f0",
            text_muted="#8898aa",
            text_disabled="#526075",
            border_main="#2e384d",
            border_light="#3a4660",
            clock_bg="#0b0e14",
            clock_text="#64b5f6",
            waveform_bg="#0d1017",
            waveform_grid="#212c40",
            waveform_playhead="#ffca28",
            meter_bg="#0d1017",
            meter_border="#2a354a",
            meter_text="#7082a0",
            meter_normal="#64b5f6",
            meter_clip="#ef5350",
            track_colors=track_colors,
        )
    elif theme_key == "retro":
        hover_bg = mix_colors(accent, "#f6f1ea", 0.2)
        return ThemePalette(
            name="retro",
            accent=accent,
            bg_main="#e4dbcf",
            bg_dialog="#ebe3d8",
            bg_panel="#f6f1ea",
            bg_input="#faf7f2",
            bg_button="#f0e9df",
            bg_button_hover=hover_bg,
            bg_button_disabled="#ded5c8",
            text_main="#382d24",
            text_muted="#756353",
            text_disabled="#a69585",
            border_main="#b8aa99",
            border_light="#c4b7a6",
            clock_bg="#241e18",
            clock_text="#f3bf6a",
            waveform_bg="#201b15",
            waveform_grid="#40362c",
            waveform_playhead="#e85d3f",
            meter_bg="#f0e8dc",
            meter_border="#b8aa99",
            meter_text="#6b594b",
            meter_normal="#453326",
            meter_clip="#c23934",
            track_colors=track_colors,
        )
    elif theme_key == "slate":
        hover_bg = mix_colors(accent, "#313640", 0.25)
        return ThemePalette(
            name="slate",
            accent=accent,
            bg_main="#282c34",
            bg_dialog="#2c313a",
            bg_panel="#313640",
            bg_input="#353b45",
            bg_button="#3b424e",
            bg_button_hover=hover_bg,
            bg_button_disabled="#22252c",
            text_main="#abb2bf",
            text_muted="#7c8594",
            text_disabled="#5c6370",
            border_main="#454c59",
            border_light="#4f5766",
            clock_bg="#1a1d22",
            clock_text="#98c379",
            waveform_bg="#1e2227",
            waveform_grid="#393f4c",
            waveform_playhead="#e5c07b",
            meter_bg="#1e2227",
            meter_border="#3e4451",
            meter_text="#7c8594",
            meter_normal="#98c379",
            meter_clip="#e06c75",
            track_colors=track_colors,
        )
    else:  # Light (default)
        hover_bg = mix_colors(accent, "#f9faf8", 0.15)
        return ThemePalette(
            name="light",
            accent=accent,
            bg_main="#e8eae7",
            bg_dialog="#e8eae7",
            bg_panel="#f9faf8",
            bg_input="#f9faf8",
            bg_button="#f9faf8",
            bg_button_hover=hover_bg,
            bg_button_disabled="#e1e4df",
            text_main="#232927",
            text_muted="#5a6860",
            text_disabled="#969e98",
            border_main="#b4bdb6",
            border_light="#bbc3bc",
            clock_bg="#192721",
            clock_text="#d1edb6",
            waveform_bg="#192721",
            waveform_grid="#334a3d",
            waveform_playhead="#f0d879",
            meter_bg="#f1f3e9",
            meter_border="#9ca79d",
            meter_text="#47594d",
            meter_normal="#26392e",
            meter_clip="#b43f46",
            track_colors=track_colors,
        )


def build_stylesheet(theme_name: str = "light", accent_color: str = "#168777") -> str:
    """Generate complete Qt stylesheet matching the given theme and accent color."""
    p = get_theme_palette(theme_name, accent_color)
    accent_darker = adjust_color(p.accent, 0.85)

    return f"""
QMainWindow, QDialog {{ background: {p.bg_main}; color: {p.text_main}; }}
QWidget {{ font-family: 'DejaVu Sans'; font-size: 12px; color: {p.text_main}; }}
QLabel {{ color: {p.text_main}; }}
QToolButton, QPushButton {{
    background: {p.bg_button};
    color: {p.text_main};
    border: 1px solid {p.border_main};
    border-radius: 4px;
    padding: 7px;
}}
QToolButton:hover, QPushButton:hover {{
    background: {p.bg_button_hover};
    border-color: {p.accent};
}}
QToolButton:disabled, QPushButton:disabled {{
    color: {p.text_disabled};
    background: {p.bg_button_disabled};
    border-color: {p.border_main};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {p.bg_input};
    color: {p.text_main};
    border: 1px solid {p.border_light};
    border-radius: 3px;
    padding: 5px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {p.accent};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {p.border_main};
}}
QComboBox QAbstractItemView {{
    background: {p.bg_panel};
    color: {p.text_main};
    selection-background-color: {p.accent};
    selection-color: white;
    border: 1px solid {p.border_main};
}}
QSlider::groove:vertical {{
    width: 5px;
    background: {p.border_light};
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    height: 23px;
    margin: 0 -11px;
    background: {p.bg_button};
    border: 1px solid {p.border_main};
    border-radius: 3px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {p.border_light};
}}
QSlider::handle:horizontal {{
    width: 12px;
    margin: -5px 0;
    background: {p.accent};
    border-radius: 3px;
}}
QProgressBar {{
    background: {p.border_light};
    border: none;
    border-radius: 2px;
}}
QProgressBar::chunk {{
    background: {p.accent};
}}
QCheckBox {{
    spacing: 5px;
    color: {p.text_main};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {p.border_main};
    border-radius: 2px;
    background: {p.bg_input};
}}
QCheckBox::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
}}
QMenuBar, QMenu {{
    background: {p.bg_panel};
    color: {p.text_main};
    border: 1px solid {p.border_main};
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background: {p.accent};
    color: white;
}}
QStatusBar {{
    background: {p.bg_main};
    color: {p.text_muted};
    border-top: 1px solid {p.border_main};
}}
QDockWidget {{
    color: {p.text_main};
}}
QDockWidget::title {{
    background: {p.bg_dialog};
    color: {p.text_main};
    padding: 5px;
    border-bottom: 1px solid {p.border_main};
}}
QMainWindow::separator {{
    background: {p.border_main};
    height: 5px;
    width: 5px;
}}
QMainWindow::separator:hover {{
    background: {p.accent};
}}
QToolTip {{
    background: {p.bg_panel};
    color: {p.text_main};
    border: 1px solid {p.border_main};
    padding: 4px;
}}
QTabBar::tab {{
    background: {p.bg_button};
    color: {p.text_muted};
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {p.text_main};
    font-weight: bold;
    border-bottom: 2px solid {p.accent};
}}
QTabBar::tab:hover {{
    color: {p.text_main};
}}
QListWidget, QTableWidget {{
    background: {p.bg_input};
    color: {p.text_main};
    border: 1px solid {p.border_light};
    alternate-background-color: {p.bg_panel};
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {p.accent};
    color: white;
}}
QHeaderView::section {{
    background: {p.bg_panel};
    color: {p.text_main};
    padding: 4px;
    border: 1px solid {p.border_main};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QPlainTextEdit {{
    background: {p.bg_input};
    color: {p.text_main};
    border: 1px solid {p.border_light};
    padding: 12px;
}}
"""
