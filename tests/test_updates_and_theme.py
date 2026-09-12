"""Tests for GitHub update checking and theme/accent customization."""

import io
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QMessageBox, QPushButton, QRadioButton, QTextEdit

from eighttrack import __version__
from eighttrack.theme import (
    ACCENT_PRESETS, THEME_PRESETS, adjust_color, build_stylesheet, get_theme_palette,
    hex_to_rgb, mix_colors, rgb_to_hex,
)
from eighttrack.updates import (
    DEFAULT_CLONE_URL, DEFAULT_REPO, DEFAULT_REPO_URL, UpdateInfo, check_for_updates,
    is_newer_version, parse_version,
)
from eighttrack.ui import AboutDialog, StudioWindow, ThemeDialog, UpdateDialog, UpdateWorker


class VersionAndUpdatesTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("0.1.0"), (0, 1, 0))
        self.assertEqual(parse_version("v0.2.1"), (0, 2, 1))
        self.assertEqual(parse_version("V1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version("1.2.3.4"), (1, 2, 3, 4))
        self.assertEqual(parse_version("v2.0-rc1"), (2, 0, 1))
        self.assertEqual(parse_version(""), (0,))
        self.assertEqual(parse_version("none"), (0,))

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version("0.2.0", "0.1.0"))
        self.assertTrue(is_newer_version("v1.0.0", "0.9.9"))
        self.assertTrue(is_newer_version("0.1.1", "0.1.0"))
        self.assertTrue(is_newer_version("1.0.0.1", "1.0.0"))
        self.assertFalse(is_newer_version("0.1.0", "0.1.0"))
        self.assertFalse(is_newer_version("0.0.9", "0.1.0"))
        self.assertFalse(is_newer_version("v0.1.0", "0.2.0"))

    def test_check_for_updates_latest_release_newer(self):
        payload = {
            "tag_name": "v0.2.0",
            "name": "8T v0.2.0 Release",
            "body": "- Added themes with colour accents\n- Added check for updates",
            "published_at": "2026-09-12T12:00:00Z",
            "html_url": "https://github.com/Butter-tart/8TrackStudio/releases/tag/v0.2.0",
            "assets": [{"browser_download_url": "https://github.com/Butter-tart/8TrackStudio/releases/download/v0.2.0/8t.exe"}],
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            info = check_for_updates(current_version="0.1.0")
            self.assertTrue(info.has_update)
            self.assertEqual(info.latest_version, "0.2.0")
            self.assertEqual(info.release_name, "8T v0.2.0 Release")
            self.assertIn("Added themes", info.release_notes)
            self.assertEqual(info.published_at, "2026-09-12")
            self.assertEqual(info.download_url, "https://github.com/Butter-tart/8TrackStudio/releases/download/v0.2.0/8t.exe")
            self.assertIsNone(info.error)

    def test_check_for_updates_latest_release_current(self):
        payload = {
            "tag_name": "v0.1.0",
            "name": "8T v0.1.0",
            "body": "Initial release",
            "published_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/Butter-tart/8TrackStudio/releases/tag/v0.1.0",
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            info = check_for_updates(current_version="0.1.0")
            self.assertFalse(info.has_update)
            self.assertEqual(info.latest_version, "0.1.0")
            self.assertIsNone(info.error)

    def test_check_for_updates_fallback_tags(self):
        err_404 = urllib.error.HTTPError("url", 404, "Not Found", {}, None)

        tags_payload = [
            {"name": "v0.3.0", "commit": {"sha": "12345"}},
            {"name": "v0.1.0", "commit": {"sha": "67890"}},
        ]
        mock_tags_resp = MagicMock()
        mock_tags_resp.status = 200
        mock_tags_resp.read.return_value = json.dumps(tags_payload).encode("utf-8")
        mock_tags_resp.__enter__.return_value = mock_tags_resp

        def urlopen_side_effect(req, timeout=None):
            if "releases/latest" in req.full_url or "releases" in req.full_url:
                raise err_404
            return mock_tags_resp

        with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            info = check_for_updates(current_version="0.1.0")
            self.assertTrue(info.has_update)
            self.assertEqual(info.latest_version, "0.3.0")

    def test_check_for_updates_network_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("No internet")):
            info = check_for_updates(current_version="0.1.0")
            self.assertFalse(info.has_update)
            self.assertIsNotNone(info.error)
            self.assertIn("No internet", info.error)


class ThemeSystemTests(unittest.TestCase):
    def test_color_utilities(self):
        self.assertEqual(hex_to_rgb("#ffffff"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#168777"), (22, 135, 119))
        self.assertEqual(rgb_to_hex(255, 255, 255), "#ffffff")
        self.assertEqual(rgb_to_hex(0, 0, 0), "#000000")

        # adjust_color
        darker = adjust_color("#ffffff", 0.5)
        self.assertEqual(darker, "#808080")

        # mix_colors
        mixed = mix_colors("#000000", "#ffffff", 0.5)
        self.assertEqual(mixed, "#808080")

    def test_theme_palettes(self):
        for key, name in THEME_PRESETS:
            palette = get_theme_palette(key, "#168777")
            self.assertEqual(palette.name, key)
            self.assertEqual(palette.accent, "#168777")
            self.assertTrue(palette.bg_main.startswith("#"))
            self.assertTrue(palette.text_main.startswith("#"))
            self.assertTrue(palette.meter_bg.startswith("#"))
            self.assertTrue(palette.waveform_bg.startswith("#"))
            self.assertEqual(len(palette.track_colors), 8)
            self.assertEqual(palette.track_colors[0], "#168777")

    def test_build_stylesheet(self):
        css_light = build_stylesheet("light", "#168777")
        self.assertIn("#168777", css_light)
        self.assertIn("QMainWindow", css_light)
        self.assertIn("QSlider::handle:horizontal", css_light)

        css_dark = build_stylesheet("dark", "#c7434e")
        self.assertIn("#c7434e", css_dark)
        self.assertIn("#1e2220", css_dark)


class UIThemeAndUpdatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.directory.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.settings_patch = patch("eighttrack.ui.QSettings", return_value=self.settings)
        self.settings_patch.start()
        self.window = StudioWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.settings_patch.stop()
        self.directory.cleanup()
        self.app.processEvents()

    def test_theme_application_and_persistence(self):
        self.window.apply_theme("dark", "#2b77ad", save=True)
        self.assertEqual(self.window.current_theme, "dark")
        self.assertEqual(self.window.current_accent, "#2b77ad")
        self.assertEqual(self.settings.value("theme/base"), "dark")
        self.assertEqual(self.settings.value("theme/accent"), "#2b77ad")
        self.assertEqual(self.window.palette.name, "dark")
        self.assertEqual(self.window.strips[0].color, "#2b77ad")

        self.window.apply_theme("midnight", "#8b4fc7", save=True)
        self.assertEqual(self.window.current_theme, "midnight")
        self.assertEqual(self.window.current_accent, "#8b4fc7")
        self.assertEqual(self.settings.value("theme/base"), "midnight")
        self.assertEqual(self.settings.value("theme/accent"), "#8b4fc7")

    def test_theme_dialog_interaction(self):
        dialog = ThemeDialog(self.window)
        self.addCleanup(dialog.deleteLater)

        # Change base theme radio
        dark_radio = dialog.theme_radios.get("dark")
        self.assertIsNotNone(dark_radio)
        dark_radio.setChecked(True)
        self.assertEqual(dialog.selected_theme, "dark")

        # Click accent preset
        dialog.on_accent_preset("#c6811e")
        self.assertEqual(dialog.selected_accent, "#c6811e")

        # Apply
        dialog.apply_live()
        self.assertEqual(self.window.current_theme, "dark")
        self.assertEqual(self.window.current_accent, "#c6811e")

    def test_update_dialog_with_new_version(self):
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.2.0",
            has_update=True,
            release_name="v0.2.0 Awesome Release",
            release_notes="New features added",
            published_at="2026-09-12",
            html_url="https://github.com/Butter-tart/8TrackStudio/releases/tag/v0.2.0",
        )
        dialog = UpdateDialog(info, parent=self.window)
        self.addCleanup(dialog.deleteLater)
        labels = [l.text() for l in dialog.findChildren(QLabel)]
        self.assertTrue(any("A new version of 8T is available" in t for t in labels))
        self.assertTrue(any("Installed version: v0.1.0" in t for t in labels))

        with patch("eighttrack.ui.QDesktopServices.openUrl") as mock_open:
            dialog.open_browser()
            mock_open.assert_called_once()

    def test_update_dialog_up_to_date(self):
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.1.0",
            has_update=False,
        )
        dialog = UpdateDialog(info, parent=self.window)
        self.addCleanup(dialog.deleteLater)
        labels = [l.text() for l in dialog.findChildren(QLabel)]
        self.assertTrue(any("You are up to date" in t for t in labels))

    def test_update_dialog_error(self):
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.1.0",
            has_update=False,
            error="Connection timed out",
        )
        dialog = UpdateDialog(info, parent=self.window)
        self.addCleanup(dialog.deleteLater)
        labels = [l.text() for l in dialog.findChildren(QLabel)]
        self.assertTrue(any("Unable to check for updates" in t for t in labels))
        self.assertTrue(any("Connection timed out" in t for t in labels))

    def test_about_dialog(self):
        dialog = AboutDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        labels = [l.text() for l in dialog.findChildren(QLabel)]
        self.assertTrue(any(f"Version {__version__}" in t for t in labels))
        self.assertTrue(any(DEFAULT_CLONE_URL in t for t in labels))

    def test_help_and_view_menus_exist(self):
        menu_titles = [action.text() for action in self.window.menuBar().actions()]
        self.assertIn("View", menu_titles)
        self.assertIn("Help", menu_titles)
