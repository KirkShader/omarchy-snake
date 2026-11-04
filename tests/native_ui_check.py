"""Run explicitly: chooser modality/keyboard, presets, HUD, Options and persistence in real GTK."""
import json
import random
import sys
import tempfile
from pathlib import Path

from native_support import (NativeCheck, board_pixel, choose_and_start, frame_origin, isolate_from_desktop_focus,
                            rgb, screenshot, set_rgb, until)

from gi.repository import Gdk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MovementPreview  # noqa: E402

COLLISION = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
             (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]


def factory():
    return MovementPreview(rng=random.Random(900), difficulty='Easy')


def press(c, name):
    return c.on_key(None, Gdk.keyval_from_name(name), 0, 0)


def first_launch(c, check):
    game, w = c.game, c.widgets
    isolate_from_desktop_focus(c)
    yield until(lambda: game.ticks >= 2, label='initial movement')

    # Chooser is modal: focus starts on the current difficulty and is trapped in the card.
    w['playing-board'].grab_focus()
    c.window.lookup_action('new-game').activate(None)
    assert w['difficulty-overlay'].get_visible()
    assert c.window.get_focus() is w['difficulty-easy'], c.window.get_focus()
    assert not w['main-menu'].get_sensitive() and not w['content'].get_can_target()
    order = []
    for _ in range(4):
        assert press(c, 'Tab')
        order.append(c.window.get_focus().get_name())
    assert order == ['difficulty-normal', 'difficulty-hard', 'difficulty-easy', 'difficulty-normal'], order
    assert press(c, 'ISO_Left_Tab') and c.window.get_focus() is w['difficulty-easy']
    assert press(c, 'Left') and c.window.get_focus() is w['difficulty-hard']
    check.ok('chooser_focus_trap_tab_shift_tab_and_arrows')
    # Rules live on the details page; previewing each difficulty leaves the Easy run alone.
    ticks = game.ticks
    details = {}
    for name in ('Easy', 'Normal', 'Hard'):
        w['difficulty-' + name.lower()].emit('clicked')
        details[name] = w['difficulty-details-text'].get_label()
        assert w['difficulty-help'].get_mapped() and c.window.get_focus() is w['difficulty-start']
        w['difficulty-back'].emit('clicked')
        assert c.window.get_focus() is w['difficulty-' + name.lower()]
    assert 'Edges wrap' in details['Easy'] and 'Solid walls' in details['Hard'], details
    help_text = w['difficulty-help'].get_label()
    assert 'Green' in help_text and '30 s' in help_text
    assert (game.difficulty, game.grid_cells) == ('Easy', 64)
    check.ok('chooser_explains_rules_and_green')
    yield 400
    assert game.ticks == ticks
    assert press(c, 'Escape')
    assert not w['difficulty-overlay'].get_visible()
    assert c.window.get_focus() is w['playing-board'], c.window.get_focus()
    assert w['main-menu'].get_sensitive()
    yield until(lambda: game.ticks > ticks, label='resumed after Escape')
    check.ok('escape_closes_chooser_returns_focus_and_resumes')
    check.artifacts['chooser_details_present'] = all(details.values())

    # Presets: cell counts per difficulty at the default 16 px on this monitor.
    for name, cells in [('Normal', 48), ('Hard', 32), ('Easy', 64)]:
        c.window.lookup_action('new-game').activate(None)
        game.score = 42
        choose_and_start(c, name)
        board = w['playing-board']
        frame = cells * c.fit.cell_pixels + 12
        yield until(lambda: board.get_width() >= frame and board.get_height() >= frame,
                    label=f'{name} board allocated')
        assert (game.difficulty, game.grid_cells, game.score, c.fit.cell_pixels) == (name, cells, 0, 16)
        assert len(game.foods) == (10 if name == 'Hard' else 5)
        check.ok(f'{name.lower()}_preset_cells_and_reset')

    # Abandoning a run through New Game keeps its best: each preset above was left at 42.
    scores = json.loads((check.state_dir / 'scores.json').read_text())
    assert scores['high_scores'] == {'Easy': 42, 'Normal': 42, 'Hard': 42}, scores
    check.ok('abandoned_run_best_saved')

    # HUD shows score, length and best.
    game.score, game.foods = 3, {(game.snake[0][0] + 1, game.snake[0][1])}
    yield until(lambda: len(game.snake) == 7, label='ate an orange')
    assert w['hud'].get_label() == 'Score 4  ·  Length 7  ·  Best 42', w['hud'].get_label()
    check.ok('hud_shows_score_length_best')

    # Two quick perpendicular turns through the real key handler apply on consecutive ticks.
    c.session.pause('menu')
    game.snake, game.direction, game.queued_turns, game.foods = [(20 - i, 20) for i in range(6)], 'Right', [], set()
    c.session.resume('menu')
    ticks = game.ticks
    assert press(c, 'Up') and press(c, 'Left')
    assert press(c, 'Down') and game.queued_turns == ['Up', 'Left']  # overflow consumed, ignored
    yield until(lambda: game.ticks >= ticks + 2, label='two ticks')
    assert game.direction == 'Left' and game.snake[0] == (19, 19), (game.direction, game.snake[0])
    check.ok('two_deep_turn_queue_via_key_handler')

    # Options: chosen colours render, persist, and the reserved red is refused.
    w['main-menu'].popup()
    yield until(lambda: w['main-popover'].get_visible(), label='menu open')
    c.window.lookup_action('options').activate(None)
    assert w['options-panel'].get_visible()
    set_rgb(w['border-color'], '#cc331a')
    set_rgb(w['grid-color'], '#3366e6')
    x, y = frame_origin(c)
    assert board_pixel(c, x, y + 40) == (204, 51, 26)
    grid = board_pixel(c, x + 6 + 16, y + 100)
    expected = tuple(round(5 * 0.65 + v * 0.35) for v in (51, 102, 230))
    assert all(abs(a - b) <= 2 for a, b in zip(grid, expected)), (grid, expected)
    saved = json.loads((check.config_dir / 'settings.json').read_text())
    assert saved['border_rgb'] == [204, 51, 26] and saved['grid_rgb'] == [51, 102, 230], saved
    check.ok('colours_render_and_persist')
    for name in ('border-color', 'grid-color'):
        before = rgb(w[name])
        set_rgb(w[name], '#ff3333')
        assert rgb(w[name]) == before, name
        assert w['appearance-message'].get_visible()
        assert 'reserved' in w['appearance-message'].get_label().lower()
    assert json.loads((check.config_dir / 'settings.json').read_text()) == saved
    check.ok('reserved_red_rejected_and_not_saved')
    yield 300  # let GTK present a frame before capturing
    check.artifacts['options_screenshot'] = screenshot('options')
    w['options-back'].emit('clicked')
    assert not w['options-panel'].get_visible() and w['main-menu-panel'].get_visible()
    w['main-popover'].popdown()
    check.ok('options_back_returns_to_menu')

    # Finishing a run stores the per-difficulty best in the (temporary) state dir.
    game.score = 50
    game.snake, game.direction, game.queued_turns, game.foods = list(COLLISION), 'Right', [], set()
    yield until(lambda: game.game_over, label='self collision')
    scores = json.loads((check.state_dir / 'scores.json').read_text())
    assert scores['high_scores'] == {'Easy': 50, 'Normal': 42, 'Hard': 42}, scores
    check.ok('best_score_saved_per_difficulty')


def second_launch(c, check):
    w = c.widgets
    isolate_from_desktop_focus(c)
    yield 300
    assert c.appearance == {'border_rgb': (204, 51, 26), 'grid_rgb': (51, 102, 230)}, c.appearance
    assert rgb(w['border-color']) == (204, 51, 26)
    assert 'Best 50' in w['hud'].get_label(), w['hud'].get_label()
    x, y = frame_origin(c)
    assert board_pixel(c, x, y + 40) == (204, 51, 26)
    check.ok('appearance_and_best_score_restored_on_next_launch')


if __name__ == '__main__':
    shared = tempfile.TemporaryDirectory(prefix='omarchy-snake-ui-')
    try:
        first = NativeCheck('ui', [], factory, shared_temp=shared).run(first_launch)
        second = NativeCheck('ui_relaunch', [], factory, shared_temp=shared).run(second_launch)
    finally:
        shared.cleanup()
    raise SystemExit(max(first, second))
