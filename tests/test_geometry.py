"""Deterministic display-fit model: cell counts never change, only rendered cell size."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.geometry import (  # noqa: E402
    DEFAULT_ZOOM, MIN_CELL_PIXELS, SCREEN_ALLOWANCE, TARGET_CELL_PIXELS, ZOOM_LEVELS,
    board_layout, fit_board, logical_size, scroll_to_keep_visible, window_size)
from omarchy_snake.rules import DIFFICULTIES  # noqa: E402

CHROME = (32, 150)  # header, labels and margins around the frame (logical px)
BORDER = 6


def available(physical, scale):
    width, height = logical_size(*physical, scale)
    return width - SCREEN_ALLOWANCE[0], height - SCREEN_ALLOWANCE[1]


class GeometryTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual((TARGET_CELL_PIXELS, MIN_CELL_PIXELS, DEFAULT_ZOOM), (16, 6, '100'))
        self.assertEqual(list(ZOOM_LEVELS), ['auto', '50', '75', '100', '125', '150', '200'])
        self.assertEqual(ZOOM_LEVELS['100'], 16)

    def test_logical_sizes_for_common_scales(self):
        self.assertEqual(logical_size(2560, 1440, 1), (2560, 1440))
        self.assertEqual(logical_size(1920, 1080, 1.25), (1536, 864))
        self.assertEqual(logical_size(1920, 1080, 1.5), (1280, 720))
        self.assertEqual(logical_size(1920, 1080, 2), (960, 540))

    def test_default_cell_size_per_display(self):
        # (display, scale) -> expected default-zoom cell size for Easy, Normal, Hard
        expected = {
            ((2560, 1440), 1): (16, 16, 16),
            ((1920, 1080), 1): (13, 16, 16),
            ((1920, 1080), 1.25): (9, 13, 16),
            ((1920, 1080), 1.5): (7, 10, 15),
            ((2560, 1440), 2): (7, 10, 15),
            ((1920, 1080), 2): (6, 6, 9),
        }
        for (physical, scale), cells_px in expected.items():
            for difficulty, cell_px in zip(DIFFICULTIES, cells_px):
                with self.subTest(display=physical, scale=scale, difficulty=difficulty):
                    fit = fit_board(DIFFICULTIES[difficulty], *available(physical, scale), *CHROME)
                    self.assertEqual(fit.cell_pixels, cell_px)
                    self.assertEqual(fit.cells, DIFFICULTIES[difficulty])
                    self.assertEqual(fit.board_pixels, cell_px * fit.cells)
                    self.assertEqual(fit.frame_pixels, fit.board_pixels + 2 * BORDER)
                    self.assertEqual(fit.limited, cell_px < 16)

    def test_window_never_exceeds_usable_area_unless_scroll_fallback(self):
        for physical in [(2560, 1440), (1920, 1080)]:
            for scale in (1, 1.25, 1.5, 2):
                for difficulty, cells in DIFFICULTIES.items():
                    for zoom in ZOOM_LEVELS:
                        with self.subTest(display=physical, scale=scale, d=difficulty, zoom=zoom):
                            width, height = available(physical, scale)
                            fit = fit_board(cells, width, height, *CHROME, zoom=zoom)
                            self.assertGreaterEqual(fit.cell_pixels, MIN_CELL_PIXELS)
                            self.assertIsInstance(fit.cell_pixels, int)
                            win_w, win_h = window_size(fit, *CHROME, width, height)
                            self.assertLessEqual(win_w, width)
                            self.assertLessEqual(win_h, height)
                            self.assertEqual(fit.scroll_fallback,
                                             fit.frame_pixels + CHROME[1] > height
                                             or fit.frame_pixels + CHROME[0] > width)

    def test_easy_on_2x_1080p_uses_readable_minimum_with_scroll_fallback(self):
        fit = fit_board(64, *available((1920, 1080), 2), *CHROME)
        self.assertEqual(fit.cell_pixels, MIN_CELL_PIXELS)
        self.assertTrue(fit.scroll_fallback)
        width, height = available((1920, 1080), 2)
        self.assertEqual(window_size(fit, *CHROME, width, height), (fit.frame_pixels + 32, height))

    def test_zoom_levels_scale_rendering_and_clamp_to_fit(self):
        width, height = available((2560, 1440), 1)
        hard = {zoom: fit_board(32, width, height, *CHROME, zoom=zoom) for zoom in ZOOM_LEVELS}
        self.assertEqual([hard[z].cell_pixels for z in ('50', '75', '100', '125', '150', '200')],
                         [8, 12, 16, 20, 24, 32])
        self.assertEqual(hard['auto'].cell_pixels, 37)  # largest whole cell that fits
        self.assertFalse(hard['200'].limited)
        easy = fit_board(64, width, height, *CHROME, zoom='200')
        self.assertEqual((easy.cell_pixels, easy.limited, easy.requested_cell_pixels), (18, True, 32))
        with self.assertRaises(ValueError):
            fit_board(32, width, height, *CHROME, zoom='300')

    def test_layout_centres_frame_on_whole_pixels_and_never_goes_negative(self):
        fit = fit_board(32, 2000, 2000, *CHROME)
        x, y = board_layout(fit, 700, 601)
        self.assertEqual((x, y), ((700 - fit.frame_pixels) // 2, (601 - fit.frame_pixels) // 2))
        self.assertEqual(board_layout(fit, 100, 100), (0, 0))

    def test_scroll_keeps_head_visible_with_margin(self):
        # 6 px cells, 64 cells = 396 px frame inside a 300 px viewport.
        self.assertEqual(scroll_to_keep_visible(0, 300, 396, cell_start=40, cell_size=6), 0)
        moved = scroll_to_keep_visible(0, 300, 396, cell_start=380, cell_size=6)
        self.assertLessEqual(moved, 396 - 300)
        self.assertLessEqual(moved, 380)
        self.assertGreaterEqual(moved + 300, 386)
        self.assertEqual(scroll_to_keep_visible(96, 300, 396, cell_start=6, cell_size=6), 0)
        self.assertEqual(scroll_to_keep_visible(0, 500, 396, cell_start=380, cell_size=6), 0)


if __name__ == '__main__':
    unittest.main()
