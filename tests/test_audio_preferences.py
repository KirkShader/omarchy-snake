"""Audio settings live in the existing schema-v1 settings.json, validated field by field."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.preferences import DEFAULT_AUDIO, DEFAULT_SETTINGS, PreferenceStore  # noqa: E402

CHOSEN = {'border_rgb': (80, 140, 220), 'grid_rgb': (160, 200, 100), 'zoom': 'auto'}
QUIET = {'music_enabled': False, 'sfx_enabled': True, 'master_volume': 0.55}


class AudioPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PreferenceStore(Path(self.tmp.name) / 'c', Path(self.tmp.name) / 's')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        self.store.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.store.settings_path.write_text(text if isinstance(text, str) else json.dumps(text))

    def saved(self):
        return json.loads(self.store.settings_path.read_text())

    def test_defaults_are_modest_with_both_channels_on(self):
        self.assertEqual(self.store.load_audio(), DEFAULT_AUDIO)
        self.assertEqual(DEFAULT_AUDIO, {'music_enabled': True, 'sfx_enabled': True, 'master_volume': 0.3})

    def test_a_file_from_before_audio_keeps_its_settings_and_gets_audio_defaults(self):
        self.write({'version': 1, 'border_rgb': [80, 140, 220], 'grid_rgb': [160, 200, 100], 'zoom': 'auto'})
        self.assertEqual(self.store.load_settings(), CHOSEN)
        self.assertEqual(self.store.load_audio(), DEFAULT_AUDIO)

    def test_round_trip_keeps_colours_zoom_and_schema_version(self):
        self.assertTrue(self.store.save_settings(CHOSEN, audio=QUIET))
        self.assertEqual(self.saved()['version'], 1)
        self.assertEqual(self.store.load_settings(), CHOSEN)
        self.assertEqual(self.store.load_audio(), QUIET)

    def test_saving_appearance_alone_keeps_saved_audio(self):
        self.store.save_settings(DEFAULT_SETTINGS, audio=QUIET)
        self.store.save_settings(CHOSEN)
        self.assertEqual(self.store.load_settings(), CHOSEN)
        self.assertEqual(self.store.load_audio(), QUIET)

    def test_each_invalid_field_falls_back_alone(self):
        valid = {'version': 1, **QUIET}
        for key, bad in [('music_enabled', 1), ('music_enabled', 'false'), ('music_enabled', None),
                         ('sfx_enabled', 0), ('sfx_enabled', []),
                         ('master_volume', True), ('master_volume', '0.5'), ('master_volume', None),
                         ('master_volume', -0.01), ('master_volume', 1.01), ('master_volume', 10 ** 400)]:
            with self.subTest(key=key, bad=bad):
                self.write({**valid, key: bad})
                expected = {**QUIET, key: DEFAULT_AUDIO[key]}
                self.assertEqual(self.store.load_audio(), expected)

    def test_nonfinite_json_numbers_are_rejected(self):
        for text in ('NaN', 'Infinity', '-Infinity', '1e999'):
            with self.subTest(text=text):
                self.write('{"version": 1, "master_volume": %s}' % text)
                self.assertEqual(self.store.load_audio()['master_volume'], DEFAULT_AUDIO['master_volume'])

    def test_whole_number_limits_are_valid_volumes(self):
        for value in (0, 1):
            self.write({'version': 1, 'master_volume': value})
            self.assertEqual(self.store.load_audio()['master_volume'], value)

    def test_wrong_schema_version_gives_defaults(self):
        self.write({'version': 2, **QUIET})
        self.assertEqual(self.store.load_audio(), DEFAULT_AUDIO)

    def test_invalid_audio_is_refused_without_writing(self):
        for bad in ({**QUIET, 'master_volume': float('nan')}, {**QUIET, 'master_volume': 2},
                    {**QUIET, 'music_enabled': 1}, {'master_volume': 0.5}):
            with self.subTest(bad=bad):
                self.assertFalse(self.store.save_settings(CHOSEN, audio=bad))
                self.assertFalse(self.store.settings_path.exists())


if __name__ == '__main__':
    unittest.main()
