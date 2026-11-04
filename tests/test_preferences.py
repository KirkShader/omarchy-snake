"""Persistence of per-difficulty best scores and appearance/zoom, using temporary dirs only."""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake import preferences  # noqa: E402
from omarchy_snake.preferences import (  # noqa: E402
    DEFAULT_SETTINGS, SCHEMA_VERSION, BestScores, PreferenceStore, default_dirs, record_score)


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.config, self.state = root / 'config' / 'omarchy-snake', root / 'state' / 'omarchy-snake'
        self.store = PreferenceStore(self.config, self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data))

    def test_default_dirs_follow_xdg_with_home_fallback(self):
        env = {'XDG_CONFIG_HOME': '/x/config', 'XDG_STATE_HOME': '/x/state', 'HOME': '/h'}
        self.assertEqual(default_dirs(env), (Path('/x/config/omarchy-snake'), Path('/x/state/omarchy-snake')))
        self.assertEqual(default_dirs({'HOME': '/h'}),
                         (Path('/h/.config/omarchy-snake'), Path('/h/.local/state/omarchy-snake')))
        self.assertEqual(default_dirs({'HOME': '/h', 'XDG_CONFIG_HOME': 'relative'})[0],
                         Path('/h/.config/omarchy-snake'))  # XDG spec: ignore relative paths

    def test_missing_files_give_defaults(self):
        self.assertEqual(self.store.load_settings(), DEFAULT_SETTINGS)
        self.assertEqual(self.store.load_scores(), {'Easy': 0, 'Normal': 0, 'Hard': 0})
        self.assertEqual(DEFAULT_SETTINGS['zoom'], '100')

    def test_round_trip_with_versioned_files_and_ordinary_permissions(self):
        settings = {'border_rgb': (80, 140, 220), 'grid_rgb': (160, 200, 100), 'zoom': 'auto'}
        self.assertTrue(self.store.save_settings(settings))
        self.assertTrue(self.store.save_scores({'Easy': 3, 'Normal': 0, 'Hard': 41}))
        self.assertEqual(PreferenceStore(self.config, self.state).load_settings(), settings)
        self.assertEqual(PreferenceStore(self.config, self.state).load_scores(),
                         {'Easy': 3, 'Normal': 0, 'Hard': 41})
        saved = json.loads((self.config / 'settings.json').read_text())
        self.assertEqual(saved['version'], SCHEMA_VERSION)
        self.assertEqual(saved['border_rgb'], [80, 140, 220])
        self.assertEqual(json.loads((self.state / 'scores.json').read_text())['version'], SCHEMA_VERSION)
        for path in (self.config / 'settings.json', self.state / 'scores.json'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
        self.assertEqual(sorted(p.name for p in self.config.iterdir()), ['settings.json'])

    def test_corrupted_or_wrong_schema_files_fall_back(self):
        for content in ['{not json', '[1, 2]', '"text"', json.dumps({'version': 99, 'zoom': '50'}),
                        json.dumps({'zoom': '50'}), '\udcff'.encode('utf-8', 'surrogateescape').decode('latin-1')]:
            with self.subTest(content=content):
                self.write(self.config / 'settings.json', content)
                self.write(self.state / 'scores.json', content)
                self.assertEqual(self.store.load_settings(), DEFAULT_SETTINGS)
                self.assertEqual(self.store.load_scores(), {'Easy': 0, 'Normal': 0, 'Hard': 0})
        (self.config / 'settings.json').write_bytes(b'\xff\xfe\x00')
        self.assertEqual(self.store.load_settings(), DEFAULT_SETTINGS)

    def test_each_field_is_type_and_range_validated(self):
        self.write(self.config / 'settings.json', {
            'version': 1, 'border_rgb': [10, 20, 30], 'grid_rgb': [255, 51, 51], 'zoom': 'huge'})
        loaded = self.store.load_settings()
        self.assertEqual(loaded['border_rgb'], (10, 20, 30))
        self.assertEqual(loaded['grid_rgb'], DEFAULT_SETTINGS['grid_rgb'])  # exact reserved red
        self.assertEqual(loaded['zoom'], '100')
        for bad in [[1, 2], [True, 0, 0], [0, 0, 256], [-1, 0, 0], [1.5, 0, 0], '#ffffff', None]:
            with self.subTest(bad=bad):
                self.write(self.config / 'settings.json', {'version': 1, 'border_rgb': bad})
                self.assertEqual(self.store.load_settings()['border_rgb'], DEFAULT_SETTINGS['border_rgb'])
        self.write(self.config / 'settings.json', {'version': 1, 'border_rgb': [255, 51, 52]})
        self.assertEqual(self.store.load_settings()['border_rgb'], (255, 51, 52))  # near-red is allowed
        self.write(self.state / 'scores.json', {'version': 1, 'high_scores': {
            'Easy': -1, 'Normal': True, 'Hard': 7, 'Extreme': 99}})
        self.assertEqual(self.store.load_scores(), {'Easy': 0, 'Normal': 0, 'Hard': 7})
        self.write(self.state / 'scores.json', {'version': 1, 'high_scores': {'Easy': 2.5, 'Hard': '9'}})
        self.assertEqual(self.store.load_scores(), {'Easy': 0, 'Normal': 0, 'Hard': 0})
        self.write(self.state / 'scores.json', {'version': 1, 'high_scores': [1, 2]})
        self.assertEqual(self.store.load_scores(), {'Easy': 0, 'Normal': 0, 'Hard': 0})

    def test_saving_reserved_red_is_refused_without_writing(self):
        self.assertFalse(self.store.save_settings(dict(DEFAULT_SETTINGS, border_rgb=(255, 51, 51))))
        self.assertFalse((self.config / 'settings.json').exists())

    def test_write_failure_returns_false_and_keeps_previous_file(self):
        self.assertTrue(self.store.save_scores({'Easy': 5, 'Normal': 0, 'Hard': 0}))
        with mock.patch.object(preferences.os, 'replace', side_effect=OSError('disk full')):
            self.assertFalse(self.store.save_scores({'Easy': 9, 'Normal': 0, 'Hard': 0}))
        self.assertEqual(self.store.load_scores()['Easy'], 5)
        self.assertEqual(sorted(p.name for p in self.state.iterdir()), ['scores.json'])
        blocked = PreferenceStore(self.config, Path(self.tmp.name) / 'file-not-dir' / 'x')
        (Path(self.tmp.name) / 'file-not-dir').write_text('')
        self.assertFalse(blocked.save_scores({'Easy': 1, 'Normal': 0, 'Hard': 0}))
        self.assertEqual(blocked.load_scores(), {'Easy': 0, 'Normal': 0, 'Hard': 0})
        if os.geteuid() != 0:
            self.config.mkdir(parents=True, exist_ok=True)
            self.config.chmod(0o500)
            try:
                self.assertFalse(self.store.save_settings(DEFAULT_SETTINGS))
            finally:
                self.config.chmod(0o755)

    def test_record_score_tracks_each_difficulty_separately(self):
        scores = {'Easy': 4, 'Normal': 0, 'Hard': 10}
        self.assertFalse(record_score(scores, 'Hard', 10))
        self.assertTrue(record_score(scores, 'Hard', 11))
        self.assertTrue(record_score(scores, 'Normal', 1))
        self.assertEqual(scores, {'Easy': 4, 'Normal': 1, 'Hard': 11})


class BestScoresTests(unittest.TestCase):
    """An unsaved new best stays pending and is written by the next save attempt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.blocker = Path(self.tmp.name) / 'state'
        self.blocker.write_text('')  # file in place of the state directory: writes fail
        self.store = PreferenceStore(Path(self.tmp.name) / 'config', self.blocker / 'omarchy-snake')

    def tearDown(self):
        self.tmp.cleanup()

    def test_failed_save_is_retried_until_written(self):
        best = BestScores(self.store)
        self.assertFalse(best.commit('Hard', 7))
        self.assertEqual((best.get('Hard'), best.dirty), (7, True))
        self.blocker.unlink()
        self.assertTrue(best.commit('Hard', 0))  # e.g. close or New Game with a fresh run
        self.assertFalse(best.dirty)
        self.assertEqual(PreferenceStore(self.store.config_dir, self.store.state_dir).load_scores()['Hard'], 7)

    def test_memory_best_never_lowers_and_clean_state_skips_writes(self):
        self.blocker.unlink()
        best = BestScores(self.store)
        self.assertTrue(best.commit('Easy', 4))
        with mock.patch.object(self.store, 'save_scores', wraps=self.store.save_scores) as save:
            self.assertTrue(best.commit('Easy', 2))
            self.assertTrue(best.commit('Normal', 0))
            save.assert_not_called()
        self.assertEqual(best.get('Easy'), 4)

    def test_loads_saved_bests(self):
        self.blocker.unlink()
        self.store.save_scores({'Easy': 0, 'Normal': 5, 'Hard': 0})
        best = BestScores(self.store)
        self.assertEqual((best.get('Normal'), best.dirty), (5, False))


if __name__ == '__main__':
    unittest.main()
