"""AudioDirector with the real GameSession and rules; only the audio backend is a recorder."""
import io
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake import audio  # noqa: E402
from omarchy_snake.audio import AudioDirector, NullBackend, create_backend  # noqa: E402
from omarchy_snake.log import GameLog  # noqa: E402
from omarchy_snake.preferences import DEFAULT_AUDIO  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402
from omarchy_snake.session import GameSession  # noqa: E402
from omarchy_snake.synth import MUSIC_GAIN  # noqa: E402

COLLISION = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
             (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]


class RecordingBackend(NullBackend):
    def __init__(self):
        self.calls = []
        self.levels = None
        self.held = False
        self.shutdowns = 0

    def set_levels(self, music, sfx):
        self.levels = (music, sfx)

    def play_cue(self, name):
        self.calls.append(name)

    def stop_cues(self):
        self.calls.append('stop_cues')

    def music(self, state):
        self.calls.append('music:' + state)

    def hold_effects(self, held):
        self.held = held

    def shutdown(self):
        self.shutdowns += 1


class Scheduler:
    def __init__(self):
        self.next_id, self.sources = 0, {}

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


class Rig(unittest.TestCase):
    settings = DEFAULT_AUDIO

    def setUp(self):
        self.backend = RecordingBackend()
        self.director = AudioDirector(self.backend, dict(self.settings))
        self.game = MovementPreview(rng=random.Random(4), difficulty='Easy')
        self.game.foods, self.game.green_dot = set(), None
        self.scheduler = Scheduler()
        self.session = GameSession(self.game, self.scheduler, now=lambda: 0.0,
                                   listener=self.director.on_event)

    def calls(self):
        calls, self.backend.calls = self.backend.calls, []
        return calls

    def running(self):
        self.session.begin()
        self.calls()

    def head_next(self):
        return (self.game.snake[0][0] + 1, self.game.snake[0][1])


class LifecycleTests(Rig):
    def test_launching_into_a_run_cues_the_start_and_plays_music(self):
        self.session.begin()
        self.assertEqual(self.calls(), ['start', 'music:playing'])

    def test_launching_behind_the_chooser_is_silent(self):
        self.session.pause('difficulty')
        self.calls()
        self.session.begin()
        self.assertEqual(self.calls(), [])

    def test_cancelling_the_launch_chooser_plays_music_without_a_start_cue(self):
        self.session.pause('difficulty')
        self.session.begin()
        self.calls()
        self.session.resume('difficulty')
        self.assertEqual(self.calls(), ['music:playing'])

    def test_every_pause_reason_stops_effects_and_pauses_music_then_resumes(self):
        for reason in ('manual', 'menu', 'color', 'focus', 'difficulty'):
            with self.subTest(reason=reason):
                self.setUp()
                self.running()
                self.session.pause(reason)
                self.assertEqual(self.calls(), ['stop_cues', 'music:paused'])
                self.session.resume(reason)
                self.assertEqual(self.calls(), ['music:playing'])

    def test_music_waits_until_the_last_reason_is_gone(self):
        self.running()
        self.session.pause('menu')
        self.session.pause('manual')
        self.calls()
        self.session.resume('menu')
        self.assertEqual(self.calls(), ['stop_cues'])
        self.session.resume('manual')
        self.assertEqual(self.calls(), ['music:playing'])

    def test_steps_without_a_reward_make_no_sound_calls(self):
        self.running()
        for _ in range(5):
            self.scheduler.fire()
        self.assertEqual(self.calls(), [])

    def test_the_effects_stream_is_held_open_only_while_it_could_be_needed(self):
        self.assertFalse(self.backend.held)
        self.running()
        self.assertTrue(self.backend.held)
        self.session.pause('menu')
        self.assertFalse(self.backend.held)
        self.director.update(self.session, sfx_enabled=False)
        self.session.resume('menu')
        self.assertFalse(self.backend.held)
        self.director.update(self.session, sfx_enabled=True)
        self.assertTrue(self.backend.held)
        self.director.update(self.session, master_volume=0)
        self.assertFalse(self.backend.held)
        self.director.update(self.session, master_volume=0.2)
        self.assertTrue(self.backend.held)
        self.game.snake, self.game.direction = list(COLLISION), 'Right'
        self.scheduler.fire()
        self.assertFalse(self.backend.held)  # released, so the finish cue plays out and ends it

    def test_shutdown_stops_once_and_nothing_can_resurrect_playback(self):
        self.running()
        self.director.shutdown()
        self.director.shutdown()
        self.assertEqual(self.backend.shutdowns, 1)
        self.calls()
        self.session.pause('menu')
        self.session.resume('menu')
        self.director.update(self.session, music_enabled=True, master_volume=0.9)
        self.session.start('Easy')
        self.assertEqual(self.calls(), [])


class CueTests(Rig):
    def test_orange_and_green_each_cue_once(self):
        self.running()
        self.game.foods = {self.head_next()}
        self.scheduler.fire()
        self.assertEqual(self.calls(), ['orange'])
        self.game.green_dot = self.head_next()
        self.scheduler.fire()
        self.assertEqual(self.calls(), ['green'])
        self.scheduler.fire()
        self.assertEqual(self.calls(), [])

    def test_collision_is_game_over_only_and_stops_music(self):
        self.running()
        self.game.snake, self.game.direction = list(COLLISION), 'Right'
        self.scheduler.fire()
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.calls(), ['music:stopped', 'game_over'])

    def test_orange_with_victory_plays_only_the_jingle(self):
        self.game.reset('Hard')
        path = [(x if y % 2 == 0 else 31 - x, y) for y in range(32) for x in range(32)]
        self.game.snake = list(reversed(path[:-1]))
        self.game.direction, self.game.foods, self.game.green_dot = 'Left', {path[-1]}, None
        self.running()
        self.scheduler.fire()
        self.assertTrue(self.game.won)
        self.assertEqual(self.calls(), ['music:stopped', 'victory'])

    def test_repeated_finish_notifications_cue_once(self):
        self.running()
        self.game.game_over = True
        self.director.on_event('finished', self.session)
        self.director.on_event('finished', self.session)
        self.assertEqual(self.calls().count('game_over'), 1)

    def test_new_game_cues_and_restarts_the_melody_from_the_top(self):
        self.running()
        self.session.pause('difficulty')
        self.calls()
        self.session.start('Normal')
        self.assertEqual(self.calls(), ['music:stopped', 'start', 'music:playing'])

    def test_new_game_after_a_loss_can_finish_with_sound_again(self):
        self.running()
        self.game.snake, self.game.direction = list(COLLISION), 'Right'
        self.scheduler.fire()
        self.session.pause('difficulty')
        self.session.start('Easy')
        self.calls()
        self.game.snake, self.game.direction, self.game.foods = list(COLLISION), 'Right', set()
        self.scheduler.fire()
        self.assertIn('game_over', self.calls())

    def test_chooser_preview_and_cancel_after_a_loss_never_cue_or_resume_music(self):
        self.running()
        self.game.snake, self.game.direction = list(COLLISION), 'Right'
        self.scheduler.fire()
        self.calls()
        self.session.pause('difficulty')
        self.assertEqual(self.calls(), ['stop_cues'])
        self.session.resume('difficulty')
        self.assertEqual(self.calls(), [])


class SettingsTests(Rig):
    def test_levels_follow_master_with_music_quieter(self):
        self.assertEqual(self.backend.levels, (0.3 * MUSIC_GAIN, 0.3))
        self.director.update(self.session, master_volume=0.5)
        self.assertEqual(self.backend.levels, (0.5 * MUSIC_GAIN, 0.5))

    def test_music_switch_is_independent_of_effects_and_applies_at_once(self):
        self.running()
        self.director.update(self.session, music_enabled=False)
        self.assertEqual(self.calls(), ['music:stopped'])
        self.game.foods = {self.head_next()}
        self.scheduler.fire()
        self.assertEqual(self.calls(), ['orange'])
        self.director.update(self.session, music_enabled=True)
        self.assertEqual(self.calls(), ['music:playing'])

    def test_effects_switch_is_independent_of_music_and_cuts_a_playing_cue(self):
        self.running()
        self.director.update(self.session, sfx_enabled=False)
        self.assertEqual(self.calls(), ['stop_cues'])
        self.game.foods = {self.head_next()}
        self.scheduler.fire()
        self.game.snake, self.game.direction = list(COLLISION), 'Right'
        self.scheduler.fire()
        self.assertEqual(self.calls(), ['music:stopped'])
        self.session.start('Easy')
        self.assertEqual(self.calls(), ['music:playing'])

    def test_volume_zero_silences_both_and_raising_it_restores_only_what_is_on(self):
        self.running()
        self.director.update(self.session, master_volume=0)
        self.assertEqual(self.backend.levels, (0, 0))
        self.assertEqual(self.calls(), ['stop_cues', 'music:stopped'])
        self.game.foods = {self.head_next()}
        self.scheduler.fire()
        self.assertEqual(self.calls(), [])
        self.director.update(self.session, music_enabled=False)
        self.calls()  # stopping cues again at volume 0 is harmless
        self.director.update(self.session, master_volume=0.4)
        self.assertEqual(self.calls(), [])

    def test_disabled_music_is_not_resurrected_by_pause_resume_or_new_game(self):
        self.director.update(self.session, music_enabled=False)
        self.session.begin()
        self.assertEqual(self.calls(), ['start'])
        self.session.pause('manual')
        self.session.resume('manual')
        self.session.pause('difficulty')
        self.calls()
        self.session.start('Hard')
        self.assertNotIn('music:playing', self.calls())

    def test_enabling_or_raising_while_paused_waits_for_resume(self):
        self.running()
        self.session.pause('menu')
        self.calls()
        self.director.update(self.session, music_enabled=False)
        self.assertEqual(self.calls(), ['music:stopped'])
        self.director.update(self.session, music_enabled=True, master_volume=0.8)
        self.assertEqual(self.calls(), [])
        self.session.resume('menu')
        self.assertEqual(self.calls(), ['music:playing'])

    def test_settings_copy_reflects_updates_for_saving(self):
        self.director.update(self.session, sfx_enabled=False, master_volume=0.65)
        self.assertEqual(self.director.settings,
                         {'music_enabled': True, 'sfx_enabled': False, 'master_volume': 0.65})


class BackendFallbackTests(unittest.TestCase):
    def test_missing_audio_libraries_give_a_silent_backend_and_one_diagnostic(self):
        stream = io.StringIO()
        with mock.patch.object(audio, '_load_gst_backend', side_effect=ImportError('no Gst typelib')):
            backend = create_backend(GameLog('verbose', stream))
        self.assertIsInstance(backend, NullBackend)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual([e['event'] for e in events], ['audio_unavailable'])
        self.assertIn('no Gst typelib', events[0]['reason'])

    def test_null_backend_accepts_every_call_silently(self):
        backend = NullBackend()
        backend.set_levels(0.1, 0.2)
        backend.play_cue('orange')
        backend.stop_cues()
        backend.music('playing')
        backend.shutdown()

    def test_gameplay_exceptions_are_not_swallowed(self):
        class Broken(NullBackend):
            def play_cue(self, name):
                raise KeyError(name)
        director = AudioDirector(Broken(), dict(DEFAULT_AUDIO))
        game = MovementPreview(rng=random.Random(1))
        session = GameSession(game, Scheduler(), now=lambda: 0.0, listener=director.on_event)
        with self.assertRaises(KeyError):
            session.begin()
        with mock.patch.object(audio, '_load_gst_backend', side_effect=TypeError('a bug')):
            with self.assertRaises(TypeError):
                create_backend(GameLog('quiet'))

    def test_without_gi_the_real_loader_falls_back_to_silence(self):
        stream = io.StringIO()
        with mock.patch.dict(sys.modules, {'gi': None, 'omarchy_snake.gst_audio': None}):
            backend = create_backend(GameLog('verbose', stream))
        self.assertIs(type(backend), NullBackend)
        self.assertIn('audio_unavailable', stream.getvalue())

    def test_the_director_and_synth_import_without_gi(self):
        code = ("import sys; sys.modules['gi'] = None; sys.path.insert(0, %r); "
                "import omarchy_snake.audio, omarchy_snake.synth" % str(Path(__file__).resolve().parents[1]))
        subprocess.run([sys.executable, '-I', '-c', code], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
