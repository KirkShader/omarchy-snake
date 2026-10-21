"""Explicit native checks for game-over presentation and reserved colour rejection."""
import json
import os
import random
import struct
import subprocess
import sys
import traceback
from pathlib import Path

import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grid_preview as app_module

checks, failures, models = [], [], []
draw_functions = {}
BaseGame = app_module.MovementPreview
original_action = Gtk.ApplicationWindow.add_action
original_draw = Gtk.DrawingArea.set_draw_func


class ObservedGame(BaseGame):
    def __init__(self):
        super().__init__(rng=random.Random(26))
        models.append(self)


def remember_draw(widget, function, *args):
    draw_functions[widget] = function
    return original_draw(widget, function, *args)


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


def rgb(picker):
    color = picker.get_rgba()
    return tuple(round(v * 255) for v in (color.red, color.green, color.blue))


def set_rgb(picker, text):
    color = Gdk.RGBA()
    assert color.parse(text)
    picker.set_rgba(color)


def rendered_pixel(widget, x, y):
    width, height = widget.get_width(), widget.get_height()
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw_functions[widget](widget, cairo.Context(image), width, height)
    image.flush()
    raw = struct.unpack_from('=I', image.get_data(), y * image.get_stride() + x * 4)[0]
    return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)


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

    def begin():
        set_rgb(find(window, 'border-color'), '#508cdc')
        set_rgb(find(window, 'grid-color'), '#a0c864')
        model = models[0]
        model.snake = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
                       (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]
        model.direction = 'Right'
        model.pending_direction = None
        model.foods = set()
        model.green_dot = None
        model.score = 8
        GLib.timeout_add(300, guarded(window, verify_game_over))

    def verify_game_over():
        assert models[0].game_over
        overlay = find(window, 'game-over-overlay')
        assert overlay.get_visible(), 'Game Over panel is not visible'
        assert find(window, 'game-over-title').get_label() == 'Game Over'
        assert find(window, 'game-over-new-game').get_label() == 'New Game'
        root = window.get_child()
        ok, bounds = overlay.compute_bounds(root)
        assert ok and abs(bounds.get_x() + bounds.get_width() / 2 - root.get_width() / 2) <= 1
        assert abs(bounds.get_y() + bounds.get_height() / 2 - root.get_height() / 2) <= 1
        assert rendered_pixel(find(window, 'playing-board'), 16, 100) == (255, 51, 51)
        assert rendered_pixel(find(window, 'board-border'), 0, 20) == (255, 51, 51)
        assert rgb(find(window, 'border-color')) == (80, 140, 220)
        assert rgb(find(window, 'grid-color')) == (160, 200, 100)
        checks.extend(['collision_shows_centered_game_over', 'board_and_grid_render_red',
                       'chosen_colours_preserved_during_game_over'])
        clients = json.loads(subprocess.check_output(['hyprctl', 'clients', '-j']))
        target = next(c for c in clients if c.get('pid') == os.getpid())
        x, y = target['at']
        width, height = target['size']
        snapshot = Path(os.environ.get('TMPDIR', str(Path.home() / '.hermes/cache/scratch'))) / 'omarchy-snake-game-over.png'
        subprocess.run(['grim', '-g', f'{x},{y} {width}x{height}', str(snapshot)], check=True)
        print(json.dumps({'game_over_screenshot': str(snapshot)}), flush=True)
        find(window, 'game-over-new-game').emit('clicked')
        assert find(window, 'difficulty-overlay').get_visible()
        assert not overlay.get_visible()
        find(window, 'difficulty-cancel').emit('clicked')
        assert overlay.get_visible()
        checks.append('restart_opens_difficulty_and_cancel_restores_game_over')
        find(window, 'game-over-new-game').emit('clicked')
        find(window, 'difficulty-normal').emit('clicked')
        GLib.timeout_add(450, guarded(window, verify_restart))

    def verify_restart():
        assert not models[0].game_over and models[0].score == 0
        assert not find(window, 'game-over-overlay').get_visible()
        board = find(window, 'playing-board')
        assert (board.get_width(), board.get_height()) == (768, 768)
        assert rendered_pixel(find(window, 'board-border'), 0, 20) == (80, 140, 220)
        expected = tuple(round(5 * 0.65 + v * 0.35) for v in (160, 200, 100))
        assert all(abs(a - b) <= 2 for a, b in zip(rendered_pixel(board, 16, 100), expected))
        checks.append('restart_restores_selected_colours_and_resets_game')
        window.lookup_action('options').activate(None)
        for name, expected in [('border-color', (80, 140, 220)), ('grid-color', (160, 200, 100))]:
            picker = find(window, name)
            set_rgb(picker, '#ff3333')
            assert rgb(picker) == expected, f'Reserved red was accepted by {name}'
            assert find(window, 'appearance-message').get_visible()
            assert 'reserved' in find(window, 'appearance-message').get_label().lower()
        checks.append('reserved_red_rejected_by_both_options')
        set_rgb(find(window, 'border-color'), '#3366e6')
        assert rgb(find(window, 'border-color')) == (51, 102, 230)
        assert not find(window, 'appearance-message').get_visible()
        checks.append('allowed_colour_accepted_and_warning_cleared')
        window.close()

    GLib.timeout_add(1000, guarded(window, begin))


app_module.MovementPreview = ObservedGame
Gtk.DrawingArea.set_draw_func = remember_draw
Gtk.ApplicationWindow.add_action = add_action
sys.argv = [app_module.__file__]
app_module.main()
print(json.dumps({'native_checks': checks, 'failures': failures}), flush=True)
raise SystemExit(1 if failures else 0)
