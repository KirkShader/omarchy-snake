"""Run explicitly: distinct loss and victory presentation, contrast under a light palette."""
import json
import random
import sys
from pathlib import Path

from native_support import (NativeCheck, board_pixel, choose_and_start, frame_origin, isolate_from_desktop_focus,
                            screenshot, set_rgb, until)

from gi.repository import GLib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MovementPreview  # noqa: E402
from omarchy_snake.theme import OVERLAY_BACKGROUND, build_css, contrast_ratio  # noqa: E402

COLLISION = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
             (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]
LATTE = {'background': '#eff1f5', 'foreground': '#4c4f69', 'accent': '#1e66f5', 'selection': '#acb0be'}


def factory():
    return MovementPreview(rng=random.Random(26), difficulty='Easy')


def hex_color(rgba):
    return '#' + ''.join(f'{round(v * 255):02x}' for v in (rgba.red, rgba.green, rgba.blue))


def centred(c, name):
    root = c.window.get_child()
    ok, bounds = c.widgets[name].compute_bounds(root)
    return ok and abs(bounds.get_x() + bounds.get_width() / 2 - root.get_width() / 2) <= 1 and \
        abs(bounds.get_y() + bounds.get_height() / 2 - root.get_height() / 2) <= 1


def serpentine(cells):
    path = []
    for y in range(cells):
        xs = range(cells) if y % 2 == 0 else range(cells - 1, -1, -1)
        path.extend((x, y) for x in xs)
    return path


def scenario(c, check):
    game, w = c.game, c.widgets
    isolate_from_desktop_focus(c)
    # Pin a light palette (Catppuccin Latte) so contrast is checked under a light theme.
    GLib.source_remove(c.theme_timer)
    c.theme_timer = None
    c.css.load_from_string(build_css(LATTE))
    set_rgb(w['border-color'], '#508cdc')
    set_rgb(w['grid-color'], '#a0c864')
    yield until(lambda: game.ticks >= 1, label='running')

    # Loss.
    game.snake, game.direction, game.queued_turns, game.foods, game.score = list(COLLISION), 'Right', [], set(), 8
    yield until(lambda: game.game_over, label='collision')
    assert w['game-over-overlay'].get_visible() and not w['victory-overlay'].get_visible()
    assert w['game-over-title'].get_label() == 'Game Over'
    assert 'Self collision' in w['game-over-detail'].get_label()
    assert 'Game over' in w['movement-status'].get_label()
    assert centred(c, 'game-over-overlay')
    x, y = frame_origin(c)
    assert board_pixel(c, x, y + 20) == (255, 51, 51)
    assert board_pixel(c, x + 6 + 16, y + 100) == (255, 51, 51)
    assert c.appearance == {'border_rgb': (80, 140, 220), 'grid_rgb': (160, 200, 100)}
    assert c.session.timer is None
    assert c.window.get_focus() is w['game-over-new-game']
    check.ok('loss_shows_centred_game_over_red_board_choices_kept')
    button = w['game-over-new-game']
    foreground = hex_color(button.get_color())
    ratio = contrast_ratio(foreground, OVERLAY_BACKGROUND)
    assert ratio >= 4.5, (foreground, ratio)
    assert contrast_ratio(LATTE['foreground'], OVERLAY_BACKGROUND) < 4.5  # the reviewed defect
    check.artifacts['light_theme_button'] = {'foreground': foreground, 'background': OVERLAY_BACKGROUND,
                                             'contrast': round(ratio, 2)}
    check.ok('game_over_button_readable_under_light_palette')
    yield 300
    check.artifacts['game_over_screenshot'] = screenshot('game-over-light-theme')
    scores = json.loads((check.state_dir / 'scores.json').read_text())
    assert scores['high_scores']['Easy'] == 8

    button.emit('clicked')
    assert w['difficulty-overlay'].get_visible() and not w['game-over-overlay'].get_visible()
    w['difficulty-hard'].emit('clicked')  # preview only: the lost run stays lost
    assert w['difficulty-details-page'].get_visible() and game.game_over and game.score == 8
    assert c.on_key(None, 0xff1b, 0, 0) and w['difficulty-choices-page'].get_visible()  # Esc: Back
    assert c.on_key(None, 0xff1b, 0, 0)  # Esc on the choices page cancels
    assert w['game-over-overlay'].get_visible() and not w['difficulty-overlay'].get_visible()
    assert (game.state, game.score, game.difficulty) == ('lost', 8, 'Easy')
    assert c.window.get_focus() is w['game-over-new-game']
    check.ok('restart_chooser_preview_then_escape_restores_game_over')

    # Victory on the real 32 x 32 Hard board: the last orange fills the final free cell.
    button.emit('clicked')
    choose_and_start(c, 'Hard')
    assert not game.finished and game.score == 0 and len(game.foods) == 10
    path = serpentine(32)
    c.session.pause('menu')
    game.snake = list(reversed(path[:-1]))
    game.direction, game.queued_turns = 'Left', []
    game.foods, game.green_dot, game.score = {path[-1]}, None, 1013
    c.session.resume('menu')
    yield until(lambda: game.won, label='board complete')
    assert len(set(game.snake)) == 1024 and game.score == 1014 and game.foods == set()
    assert w['victory-overlay'].get_visible() and not w['game-over-overlay'].get_visible()
    assert w['victory-title'].get_label() == '★ Victory!'
    assert 'every cell' in w['victory-detail'].get_label()
    assert 'Board complete' in w['movement-status'].get_label()
    assert centred(c, 'victory-overlay')
    assert board_pixel(c, x, y + 20) != (255, 51, 51)
    assert c.session.timer is None
    ticks = game.ticks
    yield 500
    assert game.ticks == ticks and c.session.timer is None
    assert c.on_key(None, 0xff1b, 0, 0) is False  # Escape: no pause after a finished run
    check.ok('victory_distinct_from_loss_and_stops_all_movement')
    yield 300
    check.artifacts['victory_screenshot'] = screenshot('victory')
    scores = json.loads((check.state_dir / 'scores.json').read_text())
    assert scores['high_scores']['Hard'] == 1014, scores
    w['victory-new-game'].emit('clicked')
    w['difficulty-easy'].emit('clicked')
    w['difficulty-back'].emit('clicked')
    assert game.won and w['difficulty-choices-page'].get_visible()  # victory kept until Start
    choose_and_start(c, 'Normal')
    assert (game.state, game.score, len(game.snake), game.grid_cells) == ('playing', 0, 6, 48)
    assert not w['victory-overlay'].get_visible()
    yield until(lambda: game.ticks >= 1, label='new run moving')
    x, y = frame_origin(c)
    assert board_pixel(c, x, y + 20) == (80, 140, 220)
    check.ok('new_game_after_victory_resets_and_restores_colours')


if __name__ == '__main__':
    raise SystemExit(NativeCheck('game_over', [], factory).run(scenario))
