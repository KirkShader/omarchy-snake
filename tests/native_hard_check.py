"""Run explicitly: Hard rules through real GTK actions and GLib movement timers."""
import json
import os
import random
import subprocess
import sys
import time
import traceback
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grid_preview as game_module

checks, failures, models, scheduled, observations = [], [], [], [], []
BaseGame = game_module.MovementPreview
original_action = Gtk.ApplicationWindow.add_action
original_timeout = GLib.timeout_add


class ObservedGame(BaseGame):
    def __init__(self):
        super().__init__(rng=random.Random(731))
        models.append(self)

    def step(self, elapsed_ms=None):
        super().step(elapsed_ms)
        observations.append({'time': time.monotonic(), 'score': self.score,
                             'configured_ms': self.step_interval_ms, 'elapsed_ms': elapsed_ms})


def timeout(interval, function, *args, **kwargs):
    source = original_timeout(interval, function, *args, **kwargs)
    if function.__name__ == 'advance':
        scheduled.append((interval, source))
    return source


def widgets(root):
    yield root
    child = root.get_first_child()
    while child:
        yield from widgets(child)
        child = child.get_next_sibling()


def find(window, name):
    matches = [w for w in widgets(window) if w.get_name() == name]
    assert len(matches) == 1, f'{name}: expected one widget, found {len(matches)}'
    return matches[0]


def guarded(window, function):
    def callback():
        try:
            function()
        except Exception:
            failures.append(traceback.format_exc())
            window.close()
        return GLib.SOURCE_REMOVE
    return callback


def add_action(window, action):
    original_action(window, action)
    if action.get_name() != 'quit':
        return

    def start_hard():
        window.lookup_action('new-game').activate(None)
        scheduled.clear()
        observations.clear()
        find(window, 'difficulty-hard').emit('clicked')
        game = models[0]
        assert game.difficulty == 'Hard' and len(game.foods) == 10
        assert (game.score, game.step_interval_ms) == (0, 150)
        game.foods = {(8, 8), (9, 8)} | {(x, 20) for x in range(20, 28)}
        GLib.timeout_add(620, guarded(window, verify_acceleration))

    def verify_acceleration():
        game = models[0]
        assert (game.score, game.step_interval_ms, len(game.snake), len(game.foods)) == (2, 145.4, 8, 10)
        status = find(window, 'movement-status').get_label()
        assert '0.1454 sec' in status and 'Solid walls' in status, status
        assert [delay for delay, _source in scheduled] == [150, 148, 145], scheduled
        assert len(observations) >= 3
        assert [(o['score'], o['configured_ms']) for o in observations[:2]] == [(1, 147.7), (2, 145.4)]
        assert (find(window, 'playing-board').get_width(), find(window, 'playing-board').get_height()) == (512, 512)
        checks.extend(['hard_has_ten_orange_dots', 'each_orange_reschedules_real_movement_timer',
                       'hard_status_shows_current_speed_and_solid_walls'])
        print(json.dumps({'observed_native_steps': observations}), flush=True)
        clients = json.loads(subprocess.check_output(['hyprctl', 'clients', '-j']))
        client = next(c for c in clients if c.get('pid') == os.getpid())
        x, y = client['at']
        width, height = client['size']
        screenshot = Path(os.environ.get('TMPDIR', str(Path.home() / '.hermes/cache/scratch'))) / 'omarchy-snake-hard.png'
        subprocess.run(['grim', '-g', f'{x},{y} {width}x{height}', str(screenshot)], check=True)
        print(json.dumps({'hard_screenshot': str(screenshot)}), flush=True)
        window.lookup_action('new-game').activate(None)
        paused = (game.ticks, game.green_elapsed_ms, game.step_interval_ms)
        def verify_pause():
            assert (game.ticks, game.green_elapsed_ms, game.step_interval_ms) == paused
            checks.append('accelerated_game_and_green_cooldown_pause_in_chooser')
            find(window, 'difficulty-cancel').emit('clicked')
            GLib.timeout_add(200, guarded(window, lambda: verify_resume(paused[0])))
        GLib.timeout_add(350, guarded(window, verify_pause))

    def verify_resume(ticks):
        game = models[0]
        assert game.ticks > ticks and game.step_interval_ms == 145.4
        checks.append('cancel_resumes_without_resetting_acceleration')
        game.snake = [(31, 8), (30, 8), (29, 8), (28, 8), (27, 8), (26, 8)]
        game.foods = set()
        game.direction = 'Right'
        game.pending_direction = None
        GLib.timeout_add(200, guarded(window, verify_wall_death))

    def verify_stopped_timer():
        context = GLib.MainContext.default()
        assert all(context.find_source_by_id(source) is None for _delay, source in scheduled), scheduled

    def verify_wall_death():
        game = models[0]
        assert game.game_over and game.game_over_reason == 'wall collision'
        assert game.snake[0] == (31, 8)
        assert find(window, 'game-over-overlay').get_visible()
        assert 'wall collision' in find(window, 'movement-status').get_label()
        verify_stopped_timer()
        checks.append('wall_collision_shows_game_over_and_stops_movement_timer')
        find(window, 'game-over-new-game').emit('clicked')
        find(window, 'difficulty-hard').emit('clicked')
        assert (game.score, game.step_interval_ms, len(game.foods)) == (0, 150, 10)
        assert not find(window, 'game-over-overlay').get_visible()
        checks.append('hard_restart_resets_speed_score_and_foods')
        game.snake = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10), (12, 11)]
        game.foods = set()
        GLib.timeout_add(220, guarded(window, verify_short_self_collision))

    def verify_short_self_collision():
        game = models[0]
        assert len(game.snake) == 6 and game.game_over
        assert game.game_over_reason == 'self collision'
        assert find(window, 'game-over-overlay').get_visible()
        assert 'self collision' in find(window, 'movement-status').get_label()
        verify_stopped_timer()
        checks.append('six_square_self_collision_ends_hard_run')
        find(window, 'game-over-new-game').emit('clicked')
        find(window, 'difficulty-normal').emit('clicked')
        assert len(game.foods) == 5 and game.step_interval_ms == 150
        assert 'Edge wrap' in find(window, 'movement-status').get_label()
        checks.append('switching_to_normal_restores_unchanged_rules')
        window.close()

    GLib.timeout_add(1000, guarded(window, start_hard))


game_module.MovementPreview = ObservedGame
GLib.timeout_add = timeout
Gtk.ApplicationWindow.add_action = add_action
sys.argv = [game_module.__file__]
game_module.main()
print(json.dumps({'native_checks': checks, 'failures': failures}), flush=True)
raise SystemExit(1 if failures else 0)
