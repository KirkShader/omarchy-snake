"""Theme reading is local, validated, and does not change the game board."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('theme_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
sys.path.insert(0, str(PATH.parent))
from omarchy_snake import theme  # noqa: E402


class OmarchyThemeTests(unittest.TestCase):
    def test_reads_palette_from_the_current_users_theme(self):
        self.assertTrue(hasattr(preview, 'load_omarchy_palette'), 'Theme support is not implemented')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'colors.toml'
            path.write_text('background = "#030b07"\nforeground = "#b9e9c7"\naccent = "#39ef78"\nselection = "#17492a"\n')
            palette = preview.load_omarchy_palette([path])
            self.assertEqual(palette['background'], '#030b07')
            self.assertEqual(palette['foreground'], '#b9e9c7')
            self.assertEqual(palette['accent'], '#39ef78')
            self.assertEqual(palette['selection'], '#17492a')
            path.write_text('background = "#112233"\n')
            self.assertEqual(preview.load_omarchy_palette([path])['background'], '#112233')

    def test_state_theme_wins_over_config_and_invalid_values_keep_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'state/omarchy/current/theme/colors.toml'
            config = root / 'config/omarchy/current/theme/colors.toml'
            for path in (state, config):
                path.parent.mkdir(parents=True)
            config.write_text('background = "#101010"\nforeground = "#eeeeee"\n')
            state.write_text('background = "#ABCDEF"\nforeground = "#fff"\naccent = 7\n')
            env = {'XDG_STATE_HOME': str(root / 'state'), 'XDG_CONFIG_HOME': str(root / 'config')}
            with mock.patch.dict(os.environ, env):
                palette = preview.load_omarchy_palette()
            self.assertEqual(palette['background'], '#abcdef')  # state first, lower-cased
            self.assertEqual(palette['foreground'], '#dce1e6')  # 3-digit hex rejected -> default
            self.assertEqual(palette['accent'], '#dce1e6')  # non-string rejected -> default
            state.write_text('background = [unterminated\n')
            with mock.patch.dict(os.environ, env):
                self.assertEqual(preview.load_omarchy_palette()['background'], '#101010')
            state.unlink()
            config.unlink()
            with mock.patch.dict(os.environ, env):
                self.assertEqual(preview.load_omarchy_palette()['background'], '#050505')


LIGHT_AND_DARK = {
    'default-dark': {'background': '#050505', 'foreground': '#dce1e6', 'accent': '#dce1e6', 'selection': '#26332b'},
    'catppuccin-latte': {'background': '#eff1f5', 'foreground': '#4c4f69', 'accent': '#1e66f5', 'selection': '#acb0be'},
    'flexoki-light': {'background': '#fffcf0', 'foreground': '#100f0f', 'accent': '#205ea6', 'selection': '#cecdc3'},
    'rose-pine-dawn': {'background': '#faf4ed', 'foreground': '#575279', 'accent': '#56949f', 'selection': '#dfdad9'},
    'low-contrast-dark': {'background': '#202020', 'foreground': '#303030', 'accent': '#404040', 'selection': '#e0e0e0'},
}


class ContrastTests(unittest.TestCase):
    def test_contrast_ratio_matches_wcag(self):
        self.assertAlmostEqual(theme.contrast_ratio('#ffffff', '#000000'), 21, places=3)
        self.assertAlmostEqual(theme.contrast_ratio('#777777', '#777777'), 1, places=6)
        # The reviewed defect: light-theme foreground on the fixed near-black button.
        self.assertLess(theme.contrast_ratio('#4c4f69', '#050505'), 3)

    def test_overlay_buttons_are_readable_under_light_and_dark_palettes(self):
        for name, palette in LIGHT_AND_DARK.items():
            with self.subTest(theme=name):
                colors = theme.overlay_button_colors(palette)
                self.assertGreaterEqual(theme.contrast_ratio(colors['foreground'], colors['background']), 4.5)
                self.assertGreaterEqual(theme.contrast_ratio(colors['foreground'], colors['hover']), 4.5)
                css = theme.build_css(palette)
                self.assertIn(colors['foreground'], css)
                self.assertIn('.snake-overlay-card button', css)

    def test_general_ui_text_gets_a_readable_fallback(self):
        for name, palette in LIGHT_AND_DARK.items():
            with self.subTest(theme=name):
                fg = theme.readable_on(palette['foreground'], palette['background'])
                self.assertGreaterEqual(theme.contrast_ratio(fg, palette['background']), 4.5)
        self.assertEqual(theme.readable_on('#4c4f69', '#eff1f5'), '#4c4f69')  # already readable: kept


if __name__ == '__main__':
    unittest.main()
