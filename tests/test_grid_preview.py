"""Geometry checks for the stationary native-window size preview."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'


class GridPreviewGeometryTests(unittest.TestCase):
    def test_board_is_1024_pixels_with_sixty_four_square_cells(self):
        self.assertTrue(PATH.is_file(), 'Native grid preview has not been implemented yet')
        spec = importlib.util.spec_from_file_location('grid_preview', PATH)
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        self.assertEqual(preview.GRID_CELLS, 64)
        self.assertEqual(preview.CELL_PIXELS, 16)
        self.assertEqual(preview.BOARD_PIXELS, 1024)
        self.assertEqual(preview.GRID_CELLS * preview.CELL_PIXELS, preview.BOARD_PIXELS)


if __name__ == '__main__':
    unittest.main()
