"""Theme reading is local, validated, and does not change the game board."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'grid_preview.py'
spec = importlib.util.spec_from_file_location('theme_preview', PATH)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


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


if __name__ == '__main__':
    unittest.main()
