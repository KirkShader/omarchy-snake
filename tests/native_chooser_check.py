"""Run explicitly: two-page New Game chooser in real GTK — choosing previews only, Back and
Escape step out without touching the run, Start resets exactly once, focus is trapped per page,
held Enter/Space cannot run on into Start, and Paused/Game Over/launch use the same flow.

Key presses go through the window's real capture handler (`on_key`/`on_key_released`); when it
lets a press through, the focused widget is activated as GTK would for Enter/Space (a GTK 4
button shows itself pressed and emits `clicked` about 250 ms later, so the scenario waits for the
resulting page). They are synthesised in-process, not compositor key events.
"""
import random
import sys
from pathlib import Path

from native_support import NativeCheck, isolate_from_desktop_focus, screenshot, until

from gi.repository import Gdk, Gtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MovementPreview  # noqa: E402

COLLISION = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
             (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]


def factory():
    return MovementPreview(rng=random.Random(57), difficulty='Easy')


def press(c, name):
    return c.on_key(None, Gdk.keyval_from_name(name), 0, 0)


def release(c, name):
    c.on_key_released(None, Gdk.keyval_from_name(name), 0, 0)


def key_activate(c, name):
    """A press of Enter/Space: the capture handler first, then the focused button if let through.
    Returns whether the press reached the button."""
    if press(c, name):
        return False
    assert c.window.get_focus().activate()
    return True


def buttons_in(widget):
    found, child = [], widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Button):
            found.append(child.get_name())
        found.extend(buttons_in(child))
        child = child.get_next_sibling()
    return found


def focus_name(c):
    return c.window.get_focus().get_name()


def tab_cycle(c, key, count):
    order = []
    for _ in range(count):
        assert press(c, key)
        order.append(focus_name(c))
    return order


def scenario(c, check):
    game, session, w = c.game, c.session, c.widgets
    isolate_from_desktop_focus(c)
    resets = []
    original_reset = game.reset
    game.reset = lambda difficulty=None: (resets.append(difficulty), original_reset(difficulty))[1]

    # Launch (--show-difficulty) opens the same choices page: three difficulties, nothing else.
    assert w['difficulty-overlay'].get_visible() and w['difficulty-choices-page'].get_visible()
    assert not w['difficulty-details-page'].get_visible()
    assert buttons_in(w['difficulty-choices-page']) == ['difficulty-easy', 'difficulty-normal', 'difficulty-hard']
    assert session.reasons == {'difficulty'} and c.chooser.page == 'choices'
    assert focus_name(c) == 'difficulty-easy', focus_name(c)
    yield 400
    assert game.ticks == 0 and session.timer is None
    check.ok('launch_opens_choices_page_with_only_three_difficulties')
    check.artifacts['choices_screenshot'] = screenshot('chooser-choices')

    # Page 1 focus trap: Tab, Shift+Tab and arrows cycle only the three difficulties.
    assert tab_cycle(c, 'Tab', 4) == ['difficulty-normal', 'difficulty-hard', 'difficulty-easy',
                                      'difficulty-normal']
    assert tab_cycle(c, 'ISO_Left_Tab', 2) == ['difficulty-easy', 'difficulty-hard']
    assert tab_cycle(c, 'Right', 1) == ['difficulty-easy']
    assert tab_cycle(c, 'Up', 1) == ['difficulty-hard']
    check.ok('choices_page_focus_trap')

    # Enter on Hard previews it; held-key auto-repeat cannot reach Start.
    assert key_activate(c, 'Return')
    yield until(lambda: w['difficulty-details-page'].get_visible(), label='Hard details page')
    assert not w['difficulty-choices-page'].get_visible()
    assert w['difficulty-details-title'].get_label() == 'Hard'
    assert 'Solid walls' in w['difficulty-details-text'].get_label()
    assert focus_name(c) == 'difficulty-start'
    for _ in range(5):
        assert key_activate(c, 'Return') is False  # repeats swallowed by the capture handler
        yield 60
    yield 400  # longer than GTK's 250 ms activation: no delayed Start either
    assert w['difficulty-details-page'].get_visible() and resets == []
    assert (game.difficulty, game.grid_cells, game.score) == ('Easy', 64, 0)
    assert session.reasons == {'difficulty'} and game.ticks == 0
    check.ok('enter_previews_details_and_repeat_cannot_start')
    assert buttons_in(w['difficulty-details-page']) == ['difficulty-back', 'difficulty-start']
    assert tab_cycle(c, 'Tab', 3) == ['difficulty-back', 'difficulty-start', 'difficulty-back']
    assert tab_cycle(c, 'ISO_Left_Tab', 1) == ['difficulty-start']
    assert tab_cycle(c, 'Left', 1) == ['difficulty-back']
    assert tab_cycle(c, 'Down', 1) == ['difficulty-start']
    check.ok('details_page_focus_trap')
    yield 300
    check.artifacts['details_screenshot'] = screenshot('chooser-details')
    release(c, 'Return')

    # Escape on details goes back (Hard keeps focus); Escape on choices cancels; no reset.
    assert press(c, 'Escape') and w['difficulty-choices-page'].get_visible()
    assert focus_name(c) == 'difficulty-hard' and session.reasons == {'difficulty'}
    w['difficulty-normal'].emit('clicked')
    w['difficulty-back'].emit('clicked')
    assert w['difficulty-choices-page'].get_visible() and focus_name(c) == 'difficulty-normal'
    yield 400
    assert game.ticks == 0 and resets == []
    assert press(c, 'Escape') and not w['difficulty-overlay'].get_visible()
    assert session.reasons == set() and c.chooser.page is None
    yield until(lambda: game.ticks >= 2, label='launch run moves after cancel')
    assert (game.difficulty, game.grid_cells, resets) == ('Easy', 64, [])
    check.ok('escape_steps_back_then_cancels_without_reset')

    # Mid-run: preview, Back and Escape leave snake, score and difficulty exactly as they were.
    c.session.pause('menu')
    game.score = 5
    c.session.resume('menu')
    yield until(lambda: game.ticks >= 4, label='mid-run')
    c.window.lookup_action('new-game').activate(None)
    frozen = (list(game.snake), game.ticks, game.score, game.difficulty, game.green_elapsed_ms)
    w['difficulty-hard'].emit('clicked')
    yield 400
    assert (list(game.snake), game.ticks, game.score, game.difficulty, game.green_elapsed_ms) == frozen
    assert session.timer is None
    w['difficulty-back'].emit('clicked')
    assert press(c, 'Escape')  # choices page: cancel
    assert not w['difficulty-overlay'].get_visible() and not session.paused, session.reasons
    yield until(lambda: game.ticks > frozen[1], label='same run resumes')
    assert (game.score, game.difficulty, resets) == (5, 'Easy', [])
    check.ok('mid_run_preview_back_escape_keep_run')

    # Start alone commits: exactly one reset into the chosen mode, then the new run moves.
    c.window.lookup_action('new-game').activate(None)
    w['difficulty-hard'].emit('clicked')
    assert key_activate(c, 'Return')  # a fresh press on the focused Start
    release(c, 'Return')
    yield until(lambda: resets, label='Start activated')
    assert resets == ['Hard'], resets
    assert (game.difficulty, game.grid_cells, game.score, len(game.foods)) == ('Hard', 32, 0, 10)
    assert not w['difficulty-overlay'].get_visible() and session.reasons == set()
    # Another Enter after the chooser closed reaches the board, which has nothing to activate.
    assert c.window.get_focus() is w['playing-board'], c.window.get_focus()
    assert press(c, 'Return') is False and not c.window.get_focus().activate()
    release(c, 'Return')
    yield 400
    assert resets == ['Hard'], resets
    yield until(lambda: game.ticks >= 1, label='new Hard run moves')
    check.ok('start_resets_exactly_once_into_chosen_mode')

    # Over a manual pause: preview and Escape twice return to Paused; Start clears it.
    assert press(c, 'Escape') and session.reasons == {'manual'}
    w['pause-new-game'].emit('clicked')
    w['difficulty-easy'].emit('clicked')
    assert session.reasons == {'manual', 'difficulty'}
    assert press(c, 'Escape') and press(c, 'Escape')
    assert w['pause-overlay'].get_visible() and session.reasons == {'manual'}
    assert focus_name(c) in ('pause-resume', 'pause-new-game') and game.difficulty == 'Hard'
    w['pause-new-game'].emit('clicked')
    w['difficulty-normal'].emit('clicked')
    w['difficulty-start'].emit('clicked')
    assert resets == ['Hard', 'Normal'] and session.reasons == set() and game.grid_cells == 48
    check.ok('paused_new_game_preview_keeps_manual_pause_start_clears_it')

    # Game Over: preview and cancel keep the loss; a held Space from New Game cannot choose.
    c.session.pause('menu')
    game.snake, game.direction, game.queued_turns, game.foods = list(COLLISION), 'Right', [], set()
    game.score = 3
    c.session.resume('menu')
    yield until(lambda: game.game_over, label='self collision')
    assert c.window.get_focus() is w['game-over-new-game']
    assert key_activate(c, 'space')
    yield until(lambda: w['difficulty-choices-page'].get_visible(), label='choices from Game Over')
    for _ in range(3):
        assert key_activate(c, 'space') is False  # still held: auto-repeat swallowed
        yield 60
    yield 400
    assert w['difficulty-choices-page'].get_visible() and not w['difficulty-details-page'].get_visible()
    release(c, 'space')
    assert key_activate(c, 'space')  # fresh press
    release(c, 'space')
    yield until(lambda: w['difficulty-details-page'].get_visible(), label='details after fresh Space')
    assert press(c, 'Escape') and press(c, 'Escape')
    assert w['game-over-overlay'].get_visible() and (game.state, game.score) == ('lost', 3)
    assert resets == ['Hard', 'Normal'] and c.window.get_focus() is w['game-over-new-game']
    check.ok('game_over_preview_and_held_space_keep_loss')


if __name__ == '__main__':
    raise SystemExit(NativeCheck('chooser', ['--show-difficulty'], factory).run(scenario))
