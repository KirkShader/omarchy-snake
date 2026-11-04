"""SnakeWindow audio routing with the real session, chooser, director and preferences."""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from omarchy_snake.audio import AudioDirector, NullBackend  # noqa: E402
from omarchy_snake.preferences import DEFAULT_AUDIO, PreferenceStore  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402
from omarchy_snake.session import GameSession  # noqa: E402
from test_app_controller import app, controller  # noqa: E402


class Recorder(NullBackend):
    def __init__(self):
        self.calls = []

    def play_cue(self, name):
        self.calls.append(name)

    def music(self, state):
        self.calls.append('music:' + state)

    def shutdown(self):
        self.calls.append('shutdown')


class Scheduler:
    def __init__(self):
        self.sources, self.next_id = {}, 0

    def add(self, _interval, callback):
        self.next_id += 1
        self.sources[self.next_id] = callback
        return self.next_id

    def remove(self, source):
        self.sources.pop(source, None)

    def fire(self):
        source = max(self.sources)
        if self.sources[source]() is False:
            self.sources.pop(source, None)


@unittest.skipIf(app is None, 'GTK 4 bindings unavailable')
class WindowAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = PreferenceStore(Path(self.tmp.name) / 'c', Path(self.tmp.name) / 's')
        self.game = MovementPreview(rng=random.Random(3), difficulty='Easy')
        self.game.foods, self.game.green_dot = set(), None
        self.window = controller(self.store, self.game)
        self.window.fit.scroll_fallback = False
        self.window.appearance = {'border_rgb': (80, 140, 220), 'grid_rgb': (160, 200, 100)}
        self.window.zoom = 'auto'
        self.backend = Recorder()
        self.window.audio = AudioDirector(self.backend, dict(DEFAULT_AUDIO))
        self.scheduler = Scheduler()
        self.window.session = GameSession(self.game, self.scheduler, now=lambda: 0.0,
                                          listener=self.window.on_session)
        self.window.session.pause('difficulty')
        self.window.session.begin()
        self.window.chooser.open()

    def calls(self):
        calls, self.backend.calls = self.backend.calls, []
        return calls

    def test_previewing_going_back_and_cancelling_are_silent(self):
        self.window.choose_difficulty('Hard')
        self.window.show_difficulty_choices()
        self.window.choose_difficulty('Normal')
        self.window.show_difficulty_choices()
        self.assertEqual(self.calls(), [])
        self.window.cancel_difficulty()
        self.assertEqual(self.calls(), ['music:playing'])

    def test_start_cues_once_and_plays_music(self):
        self.window.choose_difficulty('Hard')
        self.window.start_selected()
        self.window.start_selected()
        self.assertEqual(self.calls(), ['start', 'music:playing'])

    def test_collecting_and_losing_reach_the_backend_through_the_window(self):
        self.window.choose_difficulty('Easy')
        self.window.start_selected()
        self.calls()
        self.game.foods = {(self.game.snake[0][0] + 1, self.game.snake[0][1])}
        self.scheduler.fire()
        self.assertEqual(self.calls(), ['orange'])
        self.game.snake = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
                           (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]
        self.game.direction, self.game.foods = 'Right', set()
        self.scheduler.fire()
        self.assertEqual(self.calls(), ['music:stopped', 'game_over'])

    def test_close_stops_the_session_and_shuts_audio_down(self):
        self.window.choose_difficulty('Easy')
        self.window.start_selected()
        self.calls()
        self.window.on_close(None)
        self.assertEqual(self.calls(), ['shutdown'])
        self.assertIsNone(self.window.session.timer)

    def saved(self):
        return json.loads(self.store.settings_path.read_text())

    def test_switches_apply_save_and_keep_colours_and_zoom(self):
        self.window.on_audio_switch(mock.MagicMock(get_active=lambda: False), None, 'music_enabled')
        self.window.on_audio_switch(mock.MagicMock(get_active=lambda: False), None, 'sfx_enabled')
        self.assertFalse(self.window.audio.settings['music_enabled'])
        saved = self.saved()
        self.assertEqual((saved['music_enabled'], saved['sfx_enabled'], saved['master_volume']),
                         (False, False, 0.3))
        self.assertEqual((saved['border_rgb'], saved['zoom']), ([80, 140, 220], 'auto'))

    def test_volume_slider_saves_a_fraction_and_only_real_changes(self):
        self.window.on_volume_changed(mock.MagicMock(get_value=lambda: 65.0))
        self.assertEqual(self.window.audio.settings['master_volume'], 0.65)
        self.assertEqual(self.saved()['master_volume'], 0.65)
        with mock.patch.object(self.store, 'save_settings') as save:
            self.window.on_volume_changed(mock.MagicMock(get_value=lambda: 65.2))
            save.assert_not_called()

    def test_saving_appearance_includes_current_audio(self):
        self.window.audio.update(self.window.session, master_volume=0.8)
        self.window.save_settings()
        self.assertEqual(self.store.load_audio()['master_volume'], 0.8)

    def test_options_moves_keyboard_focus_to_its_first_control(self):
        self.window.show_options()
        self.window.widgets['border-color'].grab_focus.assert_called_once_with()

    def test_options_back_returns_focus_to_the_options_entry(self):
        self.window.show_options()
        self.window.options_back()
        self.window.widgets['menu-options'].grab_focus.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
