"""Pause reasons, timer ownership and step-clock policy with a deterministic fake clock."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import GREEN_INTERVAL_MS, MovementPreview  # noqa: E402
from omarchy_snake.session import (  # noqa: E402
    FOCUS_LOSS_CONFIRM_MS, STALL_CREDIT_FACTOR, GameSession, escape_action)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, ms):
        self.t += ms / 1000


class FakeScheduler:
    """Mimics GLib.timeout_add/source_remove: callback returning False removes the source."""

    def __init__(self):
        self.sources, self.next_id, self.added = {}, 1, []

    def add(self, interval_ms, callback):
        source = self.next_id
        self.next_id += 1
        self.sources[source] = (interval_ms, callback)
        self.added.append(interval_ms)
        return source

    def remove(self, source):
        del self.sources[source]

    def fire(self):
        assert len(self.sources) == 1, self.sources
        source, (_interval, callback) = next(iter(self.sources.items()))
        if not callback():
            self.sources.pop(source, None)

    @property
    def active(self):
        return len(self.sources)


def make(difficulty='Normal', reasons=()):
    clock, scheduler = FakeClock(), FakeScheduler()
    game = MovementPreview(rng=random.Random(5), difficulty=difficulty)
    game.foods = set()
    events = []
    session = GameSession(game, scheduler, now=clock,
                          listener=lambda event, _s: events.append(event))
    for reason in reasons:
        session.pause(reason)
    session.begin()
    return session, game, clock, scheduler, events


def tick(session, clock, scheduler, ms=None):
    clock.advance(session.game.step_interval_ms if ms is None else ms)
    scheduler.fire()


class PauseReasonTests(unittest.TestCase):
    def test_running_session_owns_exactly_one_timer_at_step_interval(self):
        session, game, clock, scheduler, _ = make()
        self.assertFalse(session.paused)
        self.assertEqual((scheduler.active, scheduler.added), (1, [150]))
        tick(session, clock, scheduler)
        self.assertEqual(game.ticks, 1)

    def test_difficulty_chooser_open_before_first_movement(self):
        session, game, clock, scheduler, _ = make(reasons=['difficulty'])
        self.assertTrue(session.paused)
        self.assertEqual(scheduler.active, 0)
        clock.advance(5000)
        self.assertEqual(game.ticks, 0)
        session.start('Hard')
        self.assertEqual((session.paused, scheduler.active, game.difficulty), (False, 1, 'Hard'))

    def test_escape_toggles_manual_pause_and_freezes_board_and_green_timer(self):
        session, game, clock, scheduler, events = make()
        game.green_elapsed_ms = 1000
        tick(session, clock, scheduler)
        self.assertTrue(session.toggle_manual())
        self.assertIn('pause_changed', events)
        self.assertEqual(scheduler.active, 0)
        frozen = (list(game.snake), game.ticks, game.green_elapsed_ms)
        clock.advance(60000)
        self.assertEqual((game.snake, game.ticks, game.green_elapsed_ms), frozen)
        self.assertFalse(session.toggle_manual())
        self.assertEqual(scheduler.active, 1)

    def test_closing_menu_or_colour_chooser_never_resumes_a_manual_pause(self):
        session, _game, _clock, scheduler, _ = make()
        session.toggle_manual()
        session.pause('menu')
        session.pause('color')
        session.resume('menu')
        session.resume('color')
        self.assertEqual(session.reasons, {'manual'})
        self.assertEqual(scheduler.active, 0)

    def test_colour_chooser_keeps_game_paused_after_popover_closes(self):
        session, _game, _clock, scheduler, _ = make()
        session.pause('menu')
        session.pause('color')
        session.resume('menu')
        self.assertTrue(session.paused)
        self.assertEqual(scheduler.active, 0)
        session.resume('color')
        self.assertFalse(session.paused)
        self.assertEqual(scheduler.active, 1)

    def test_confirmed_focus_loss_engages_manual_pause_and_regain_does_not_resume(self):
        self.assertEqual(FOCUS_LOSS_CONFIRM_MS, 300)
        session, _game, _clock, scheduler, _ = make()
        session.focus_changed(False)
        self.assertEqual(session.reasons, {'focus'})  # frozen at once
        self.assertEqual(scheduler.active, 0)
        session.confirm_focus_loss()
        self.assertEqual(session.reasons, {'manual', 'focus'})
        session.focus_changed(True)
        self.assertEqual(session.reasons, {'manual'})
        self.assertEqual(scheduler.active, 0)

    def test_transient_focus_blip_does_not_leave_a_manual_pause(self):
        # GTK on Wayland briefly reports the window inactive while a popover opens.
        session, _game, _clock, scheduler, _ = make()
        session.pause('menu')
        session.focus_changed(False)
        session.focus_changed(True)
        session.confirm_focus_loss()  # confirmation fires after focus already returned
        session.resume('menu')
        self.assertEqual((session.reasons, scheduler.active), (set(), 1))

    def test_focus_moving_to_own_colour_dialog_does_not_add_manual_pause(self):
        session, _game, _clock, scheduler, _ = make()
        session.pause('menu')
        session.pause('color')
        session.focus_changed(False)
        session.confirm_focus_loss(own_dialog=True)
        self.assertEqual(session.reasons, {'menu', 'color', 'focus'})
        session.focus_changed(True)
        session.resume('color')
        session.resume('menu')
        self.assertFalse(session.paused)
        self.assertEqual(scheduler.active, 1)

    def test_steering_is_not_consumed_while_paused(self):
        session, game, _clock, _scheduler, _ = make()
        session.toggle_manual()
        self.assertFalse(session.steer('Up'))
        self.assertEqual(game.queued_turns, [])
        session.toggle_manual()
        self.assertTrue(session.steer('Up'))
        self.assertEqual(game.queued_turns, ['Up'])

    def test_pause_unavailable_after_loss_or_win(self):
        session, game, clock, scheduler, events = make('Hard')
        game.snake = [(31, 8), (30, 8), (29, 8)]
        tick(session, clock, scheduler)
        self.assertTrue(game.game_over)
        self.assertIn('finished', events)
        self.assertEqual(scheduler.active, 0)
        self.assertIsNone(session.toggle_manual())
        session.focus_changed(False)
        session.confirm_focus_loss()
        self.assertNotIn('manual', session.reasons)
        session.focus_changed(True)
        self.assertEqual(scheduler.active, 0)

    def test_victory_leaves_zero_timers_even_after_resume_attempts(self):
        session, game, clock, scheduler, _ = make('Hard')
        game.grid_cells = 2
        game.snake = [(1, 1), (1, 0), (0, 0)]
        game.direction = 'Left'
        game.foods = {(0, 1)}
        tick(session, clock, scheduler)
        self.assertTrue(game.won)
        self.assertEqual(scheduler.active, 0)
        session.pause('menu')
        session.resume('menu')
        self.assertEqual(scheduler.active, 0)

    def test_new_game_clears_manual_and_difficulty_but_respects_open_dialogs(self):
        session, _game, _clock, scheduler, _ = make()
        session.toggle_manual()
        session.pause('difficulty')
        session.start('Easy')
        self.assertEqual((session.reasons, scheduler.active), (set(), 1))
        session.pause('color')
        session.start('Normal')
        self.assertEqual((session.reasons, scheduler.active), ({'color'}, 0))


    def test_stop_removes_timer_and_blocks_restart_until_new_game(self):
        session, _game, _clock, scheduler, _ = make()
        session.stop()
        self.assertEqual(scheduler.active, 0)
        session.pause('menu')
        session.resume('menu')
        self.assertEqual(scheduler.active, 0)


class StepClockTests(unittest.TestCase):
    def test_resume_resets_timestamp_so_pause_time_is_never_credited(self):
        session, game, clock, scheduler, _ = make()
        game.green_elapsed_ms = 0
        clock.advance(100)
        session.toggle_manual()
        clock.advance(10 * 60 * 1000)
        session.toggle_manual()
        tick(session, clock, scheduler, 150)
        self.assertAlmostEqual(game.green_elapsed_ms, 150, places=6)
        self.assertEqual(game.ticks, 1)

    def test_long_stall_credits_a_bounded_delta_and_moves_once(self):
        self.assertEqual(STALL_CREDIT_FACTOR, 2)
        session, game, clock, scheduler, _ = make()
        tick(session, clock, scheduler, 5000)  # event loop stalled for five seconds
        self.assertEqual(game.ticks, 1)
        self.assertAlmostEqual(game.green_elapsed_ms, 300, places=6)

    def test_ordinary_late_callback_is_credited_actual_time(self):
        session, game, clock, scheduler, _ = make()
        tick(session, clock, scheduler, 170)
        self.assertAlmostEqual(game.green_elapsed_ms, 170, places=6)

    def test_green_cooldown_needs_thirty_seconds_of_active_play_across_pauses(self):
        session, game, clock, scheduler, _ = make()
        steps = 0
        while game.green_dot is None:
            tick(session, clock, scheduler)
            steps += 1
            if steps % 50 == 0:
                session.pause('menu')
                clock.advance(20000)
                session.resume('menu')
        self.assertEqual(steps, GREEN_INTERVAL_MS // 150)

    def test_hard_speed_change_reschedules_without_duplicate_timers(self):
        session, game, clock, scheduler, _ = make('Hard')
        game.foods = {(8, 8), (9, 8)}
        tick(session, clock, scheduler)
        tick(session, clock, scheduler)
        self.assertEqual(scheduler.active, 1)
        self.assertEqual(scheduler.added, [150, 148, 145])
        self.assertEqual(next(iter(scheduler.sources.values()))[0], 145)

    def test_hard_floor_schedules_fifty_ms(self):
        session, game, clock, scheduler, _ = make('Hard')
        game.score = 60
        session.toggle_manual()
        session.toggle_manual()
        self.assertEqual(scheduler.added[-1], 50)


class StepListenerReentrancyTests(unittest.TestCase):
    """The 'step' listener may pause, stop or restart the run before the next timer is set."""

    def make_hard_eating(self, on_step, score=0):
        clock, scheduler = FakeClock(), FakeScheduler()
        game = MovementPreview(rng=random.Random(5), difficulty='Hard')
        game.score = score
        game.foods = {(game.snake[0][0] + 1, game.snake[0][1])}  # eaten next tick: speed changes
        calls = []

        def listener(event, session):
            if event == 'step' and not calls:
                calls.append(event)
                on_step(session)
        session = GameSession(game, scheduler, now=clock, listener=listener)
        session.begin()
        return session, game, clock, scheduler

    def test_pause_on_hard_speed_change_schedules_no_timer_and_no_movement(self):
        session, game, clock, scheduler = self.make_hard_eating(lambda s: s.pause('manual'))
        tick(session, clock, scheduler)
        self.assertEqual(game.ticks, 1)
        self.assertEqual((scheduler.active, session.timer, scheduler.added), (0, None, [150]))
        clock.advance(5000)
        self.assertEqual(game.ticks, 1)
        session.resume('manual')
        self.assertEqual((scheduler.active, scheduler.added), (1, [150, 148]))

    def test_pause_on_steady_speed_step_leaves_no_timer(self):
        session, game, clock, scheduler, _ = make()
        session.listener = lambda event, s: event == 'step' and s.pause('menu')
        tick(session, clock, scheduler)
        self.assertEqual((game.ticks, scheduler.active, session.timer), (1, 0, None))

    def test_stop_on_hard_speed_change_schedules_nothing(self):
        session, game, clock, scheduler = self.make_hard_eating(lambda s: s.stop())
        tick(session, clock, scheduler)
        self.assertEqual((scheduler.active, session.timer, scheduler.added), (0, None, [150]))

    def test_restart_on_speed_change_keeps_only_the_new_games_timer(self):
        session, game, clock, scheduler = self.make_hard_eating(lambda s: s.start('Easy'), score=10)
        tick(session, clock, scheduler)
        self.assertEqual(game.difficulty, 'Easy')
        self.assertEqual(scheduler.active, 1)
        (source, (interval, _callback)), = scheduler.sources.items()
        self.assertEqual((session.timer, interval), (source, 150))

    def test_pause_and_resume_inside_listener_leaves_exactly_one_timer(self):
        def bounce(s):
            s.pause('menu')
            s.resume('menu')
        session, game, clock, scheduler = self.make_hard_eating(bounce)
        tick(session, clock, scheduler)
        self.assertEqual(scheduler.active, 1)
        (source, (interval, _callback)), = scheduler.sources.items()
        self.assertEqual((session.timer, interval), (source, 148))
        tick(session, clock, scheduler)
        self.assertEqual((game.ticks, scheduler.active), (2, 1))

    def test_stale_callback_from_a_replaced_timer_does_not_move(self):
        session, game, _clock, scheduler, _ = make()
        (_source, (_interval, stale)), = scheduler.sources.items()
        session.pause('menu')
        session.resume('menu')
        self.assertFalse(stale())
        self.assertEqual((game.ticks, scheduler.active), (0, 1))

    def test_steady_and_speed_change_paths_keep_one_timer(self):
        session, game, clock, scheduler, _ = make('Hard')
        tick(session, clock, scheduler)  # steady: same source continues
        self.assertEqual((scheduler.active, scheduler.added), (1, [150]))
        game.foods = {(game.snake[0][0] + 1, game.snake[0][1])}
        tick(session, clock, scheduler)  # speed change: one replacement source
        self.assertEqual((scheduler.active, scheduler.added), (1, [150, 148]))
        (source, _), = scheduler.sources.items()
        self.assertEqual(session.timer, source)


class EscapeHierarchyTests(unittest.TestCase):
    def test_escape_closes_innermost_surface_first(self):
        self.assertEqual(escape_action(chooser_open=True, menu_open=False, finished=False), 'close-chooser')
        self.assertEqual(escape_action(chooser_open=True, menu_open=True, finished=True), 'close-chooser')

    def test_escape_on_the_details_page_goes_back_before_closing(self):
        self.assertEqual(escape_action(chooser_open=True, menu_open=False, finished=False,
                                       chooser_details=True), 'chooser-back')
        self.assertEqual(escape_action(chooser_open=True, menu_open=False, finished=True,
                                       chooser_details=True), 'chooser-back')
        self.assertEqual(escape_action(chooser_open=True, menu_open=False, finished=False,
                                       chooser_details=False), 'close-chooser')
        self.assertEqual(escape_action(chooser_open=False, menu_open=True, finished=False), 'close-menu')
        self.assertEqual(escape_action(chooser_open=False, menu_open=False, finished=False), 'toggle-pause')
        self.assertEqual(escape_action(chooser_open=False, menu_open=False, finished=True), 'none')


if __name__ == '__main__':
    unittest.main()
