"""Run explicitly: Hard rules through real GTK actions and GLib movement timers."""
import json
import random
import sys
import time
from pathlib import Path

from native_support import NativeCheck, choose_and_start, isolate_from_desktop_focus, screenshot, until

from gi.repository import Gdk

from gi.repository import GLib  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MovementPreview  # noqa: E402

steps = []


class ObservedGame(MovementPreview):
    def step(self, elapsed_ms=None):
        super().step(elapsed_ms)
        steps.append((time.monotonic(), self.score, self.step_interval_ms, elapsed_ms))


class RecordingScheduler:
    def __init__(self):
        self.scheduled = []

    def add(self, interval_ms, callback):
        source = GLib.timeout_add(interval_ms, callback)
        self.scheduled.append((interval_ms, source))
        return source

    def remove(self, source):
        GLib.source_remove(source)


def factory():
    return ObservedGame(rng=random.Random(731))


def no_live_timers(scheduler):
    context = GLib.MainContext.default()
    return all(source_destroyed(context, source) for _interval, source in scheduler.scheduled)


def source_destroyed(context, source_id):
    source = context.find_source_by_id(source_id)
    return source is None or source.is_destroyed()


def scenario(c, check):
    game, w = c.game, c.widgets
    isolate_from_desktop_focus(c)
    recorder = RecordingScheduler()
    c.session.scheduler = recorder
    c.window.lookup_action('new-game').activate(None)
    choose_and_start(c, 'Hard')
    assert game.difficulty == 'Hard' and len(game.foods) == 10
    assert (game.score, game.step_interval_ms) == (0, 150)
    c.session.pause('menu')
    game.foods = {(8, 8), (9, 8)} | {(x, 20) for x in range(20, 28)}
    steps.clear()
    c.session.resume('menu')
    yield until(lambda: game.score == 2 and len(steps) >= 3, label='two oranges eaten')
    assert game.step_interval_ms == 145.4
    # 150 (new run), 150 (fixture pause/resume), then one reschedule per orange.
    assert [interval for interval, _ in recorder.scheduled] == [150, 150, 148, 145], recorder.scheduled
    context = GLib.MainContext.default()
    live = [s for _i, s in recorder.scheduled if not source_destroyed(context, s)]
    assert live == [recorder.scheduled[-1][1]], live
    assert [(s[1], s[2]) for s in steps[:2]] == [(1, 147.7), (2, 145.4)]
    assert '0.1454 sec' in w['movement-status'].get_label() and 'Solid walls' in w['movement-status'].get_label()
    check.ok('each_orange_reschedules_one_real_timer')

    # Chooser freezes the accelerated run; previewing Hard, Back and Escape keep its speed.
    c.window.lookup_action('new-game').activate(None)
    frozen = (game.ticks, game.green_elapsed_ms)
    scheduled = len(recorder.scheduled)
    w['difficulty-hard'].emit('clicked')
    assert w['difficulty-details-page'].get_visible()
    yield 400
    assert (game.ticks, game.green_elapsed_ms) == frozen and c.session.timer is None
    assert (game.score, game.step_interval_ms) == (2, 145.4)
    w['difficulty-back'].emit('clicked')
    assert c.on_key(None, Gdk.KEY_Escape, 0, 0) and not w['difficulty-overlay'].get_visible()
    yield until(lambda: game.ticks > frozen[0], label='resumed')
    assert game.step_interval_ms == 145.4 and recorder.scheduled[scheduled][0] == 145
    check.ok('chooser_preview_back_and_escape_keep_acceleration')

    # 50 ms floor: measure real cadence over many callbacks on a long straight path.
    c.session.pause('menu')
    game.score = 60
    game.snake = [(1, 2), (1, 1), (1, 0)]
    game.direction, game.queued_turns, game.foods, game.green_dot = 'Down', [], set(), None
    steps.clear()
    c.session.resume('menu')
    yield until(lambda: len(steps) >= 21 or game.finished, timeout_ms=4000, label='twenty fast steps')
    assert recorder.scheduled[-1][0] == 50, recorder.scheduled[-1]
    assert game.step_interval_ms == 50
    gaps = [(b[0] - a[0]) * 1000 for a, b in zip(steps, steps[1:])][:20]
    mean = sum(gaps) / len(gaps)
    check.artifacts['floor_cadence_ms'] = {'mean': round(mean, 1), 'min': round(min(gaps), 1),
                                           'max': round(max(gaps), 1), 'samples': len(gaps)}
    assert 45 <= mean <= 80, check.artifacts['floor_cadence_ms']
    assert min(gaps) >= 40, check.artifacts['floor_cadence_ms']  # never faster than the floor
    check.ok('hard_floor_real_cadence_about_50ms')
    yield until(lambda: game.game_over, timeout_ms=4000, label='wall collision at the bottom')
    assert game.game_over_reason == 'wall collision' and game.snake[0][1] == 31
    assert w['game-over-overlay'].get_visible() and 'wall collision' in w['movement-status'].get_label()
    yield 200
    assert c.session.timer is None and no_live_timers(recorder)
    check.ok('wall_collision_stops_all_movement_timers')
    check.artifacts['hard_screenshot'] = screenshot('hard-game-over')

    w['game-over-new-game'].emit('clicked')
    choose_and_start(c, 'Hard')
    assert (game.score, game.step_interval_ms, len(game.foods)) == (0, 150, 10)
    assert recorder.scheduled[-1][0] == 150
    check.ok('restart_resets_speed_score_and_foods')
    c.session.pause('menu')
    game.snake = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10), (12, 11)]
    game.direction, game.queued_turns, game.foods = 'Right', [], set()
    c.session.resume('menu')
    yield until(lambda: game.game_over, label='short self collision')
    assert len(game.snake) == 6 and game.game_over_reason == 'self collision'
    check.ok('six_square_self_collision_ends_hard_run')
    print(json.dumps({'scheduled_intervals': [i for i, _ in recorder.scheduled]}), flush=True)


if __name__ == '__main__':
    raise SystemExit(NativeCheck('hard', [], factory).run(scenario))
