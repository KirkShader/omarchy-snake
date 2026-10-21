"""Presentation rules for the reserved game-over warning colour."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('game_over_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class GameOverPresentationTests(unittest.TestCase):
    def test_game_over_overrides_board_colours_without_overwriting_choices(self):
        self.assertTrue(hasattr(preview, 'board_colors'), 'Game-over colours are not implemented')
        chosen = {'border_rgb': (80, 140, 220), 'grid_rgb': (160, 200, 100)}
        saved = dict(chosen)
        self.assertEqual(preview.board_colors(False, chosen), chosen)
        warning = preview.board_colors(True, chosen)
        self.assertEqual(warning['border_rgb'], (255, 51, 51))
        self.assertEqual(warning['grid_rgb'], (255, 51, 51))
        self.assertEqual(chosen, saved)
        self.assertEqual(preview.board_colors(False, chosen), saved)

    def test_game_over_red_is_reserved_but_other_colours_are_allowed(self):
        self.assertTrue(hasattr(preview, 'is_reserved_color'), 'Reserved colour validation is missing')
        self.assertTrue(preview.is_reserved_color((255, 51, 51)))
        self.assertTrue(preview.is_reserved_color([255, 51, 51]))
        for color in [(220, 225, 230), (51, 102, 230), (204, 51, 26), (51, 255, 51)]:
            with self.subTest(color=color):
                self.assertFalse(preview.is_reserved_color(color))


if __name__ == '__main__':
    unittest.main()
