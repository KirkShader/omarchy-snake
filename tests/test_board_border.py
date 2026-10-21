"""Pixel checks for the non-playable border around the native board."""
import importlib.util
from pathlib import Path
import struct
import unittest

import cairo

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('border_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class BoardBorderTests(unittest.TestCase):
    def test_border_is_text_white_outside_and_fades_inward_on_all_sides(self):
        self.assertTrue(hasattr(preview, 'draw_board_border'), 'Board border is not implemented')
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 40)
        cr = cairo.Context(surface)
        cr.set_source_rgb(5 / 255, 5 / 255, 5 / 255)
        cr.paint()
        preview.draw_board_border(cr, 40, 40)
        surface.flush()

        def pixel(x, y):
            raw = struct.unpack_from('=I', surface.get_data(),
                                     y * surface.get_stride() + x * 4)[0]
            return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)

        for side in [lambda d: (d, 20), lambda d: (39 - d, 20),
                     lambda d: (20, d), lambda d: (20, 39 - d)]:
            values = [pixel(*side(d)) for d in range(preview.BORDER_PIXELS)]
            self.assertEqual(values[0], (220, 225, 230))
            self.assertEqual(values[1], (220, 225, 230))
            self.assertEqual(values[-1], (5, 5, 5))
            self.assertTrue(all(sum(a) >= sum(b) for a, b in zip(values, values[1:])))
        self.assertEqual(pixel(20, 20), (5, 5, 5))

    def test_custom_border_colour_preserves_the_inward_fade(self):
        import inspect
        self.assertIn('color', inspect.signature(preview.draw_board_border).parameters,
                      'Selectable border colour is not implemented')
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 40)
        preview.draw_board_border(cairo.Context(surface), 40, 40, color=(255, 64, 32))
        surface.flush()
        def pixel(x, y):
            raw = struct.unpack_from('=I', surface.get_data(), y * surface.get_stride() + x * 4)[0]
            return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)
        self.assertEqual(pixel(0, 20), (255, 64, 32))
        self.assertEqual(pixel(preview.BORDER_PIXELS - 1, 20), (5, 5, 5))


if __name__ == '__main__':
    unittest.main()
