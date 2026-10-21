"""Native difficulty-dialog checks. Run explicitly, not during headless discovery."""
import json
import random
import struct
import sys
import traceback
from pathlib import Path

import gi
import cairo
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import grid_preview as game_module

failures = []
checks = []
instances = []
BaseGame = game_module.MovementPreview


class ObservedGame(BaseGame):
    def __init__(self):
        super().__init__(rng=random.Random(900))
        instances.append(self)


game_module.MovementPreview = ObservedGame
original_add_action = Gtk.ApplicationWindow.add_action
original_draw_func = Gtk.DrawingArea.set_draw_func
draw_functions = {}
border_colors = []
original_border = game_module.draw_board_border


def remember_draw(widget, function, *args):
    draw_functions[widget] = function
    return original_draw_func(widget, function, *args)


def remember_border(cr, width, height, color=game_module.TEXT_RGB):
    border_colors.append(tuple(color))
    return original_border(cr, width, height, color=color)


Gtk.DrawingArea.set_draw_func = remember_draw
game_module.draw_board_border = remember_border


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
    original_add_action(window, action)
    if action.get_name() != 'quit':
        return

    def start():
        window.lookup_action('new-game').activate(None)
        assert find(window, 'difficulty-overlay').get_visible()
        tick = instances[0].ticks
        def verify_pause():
            assert instances[0].ticks == tick, 'Snake moved while difficulty chooser was open'
            checks.append('difficulty_chooser_pauses_game')
            find(window, 'difficulty-cancel').emit('clicked')
            GLib.timeout_add(350, guarded(window, lambda: verify_resume(tick)))
        GLib.timeout_add(350, guarded(window, verify_pause))

    def verify_resume(tick):
        assert instances[0].ticks > tick, 'Cancel did not resume movement'
        checks.append('cancel_resumes_existing_game')
        choose(0)

    presets = [('Normal', 48, 768), ('Hard', 32, 512), ('Easy', 64, 1024)]
    def choose(index):
        if index == len(presets):
            test_options()
            return
        name, cells, pixels = presets[index]
        window.lookup_action('new-game').activate(None)
        instances[0].score = 42
        find(window, 'difficulty-' + name.lower()).emit('clicked')
        def verify():
            model = instances[0]
            assert (model.difficulty, model.grid_cells, model.score) == (name, cells, 0)
            assert len(model.foods) == (10 if name == 'Hard' else 5) and not model.game_over
            assert not find(window, 'difficulty-overlay').get_visible()
            board = find(window, 'playing-board')
            assert (board.get_width(), board.get_height()) == (pixels, pixels), (name, board.get_width(), board.get_height())
            checks.append(name.lower() + '_board_dimensions_and_reset')
            choose(index + 1)
        GLib.timeout_add(450, guarded(window, verify))

    def test_options():
        action = window.lookup_action('options')
        assert action is not None, 'Options action is not implemented'
        find(window, 'main-menu').popup()
        action.activate(None)
        assert find(window, 'options-panel').get_visible()
        border_picker = find(window, 'border-color')
        grid_picker = find(window, 'grid-color')
        red = Gdk.RGBA()
        red.parse('#cc331a')
        blue = Gdk.RGBA()
        blue.parse('#3366e6')
        border_picker.set_rgba(red)
        grid_picker.set_rgba(blue)
        GLib.timeout_add(300, guarded(window, verify_colors))

    def verify_colors():
        assert (204, 51, 26) in border_colors, 'Changed border colour was not rendered'
        board = find(window, 'playing-board')
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, board.get_width(), board.get_height())
        draw_functions[board](board, cairo.Context(surface), board.get_width(), board.get_height())
        surface.flush()
        raw = struct.unpack_from('=I', surface.get_data(), 100 * surface.get_stride() + 16 * 4)[0]
        pixel = ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)
        expected = tuple(round(5 * 0.65 + channel * 0.35) for channel in (51, 102, 230))
        assert all(abs(a - b) <= 2 for a, b in zip(pixel, expected)), (pixel, expected)
        checks.extend(['options_submenu_opens', 'border_colour_rendered', 'grid_colour_rendered'])
        find(window, 'options-back').emit('clicked')
        assert not find(window, 'options-panel').get_visible()
        checks.append('options_back_returns_to_menu')
        window.lookup_action('new-game').activate(None)
        find(window, 'difficulty-normal').emit('clicked')
        GLib.timeout_add(300, guarded(window, verify_color_retention))

    def verify_color_retention():
        color = find(window, 'border-color').get_rgba()
        assert abs(color.red - 0.8) < 0.01
        assert instances[0].difficulty == 'Normal'
        checks.append('appearance_retained_across_new_game')
        picker = find(window, 'border-color')
        trigger = picker.get_first_child()
        assert isinstance(trigger, Gtk.Button), 'Native colour-picker button is missing'
        trigger.emit('clicked')
        GLib.timeout_add(450, guarded(window, verify_color_dialog))

    def verify_color_dialog():
        dialogs = [w for w in Gtk.Window.list_toplevels()
                   if w is not window and w.get_visible() and w.get_title() == 'Border colour']
        assert len(dialogs) == 1, 'Native colour chooser did not open'
        checks.append('native_colour_chooser_opens')
        dialogs[0].close()
        GLib.timeout_add(100, guarded(window, window.close))

    GLib.timeout_add(1000, guarded(window, start))


Gtk.ApplicationWindow.add_action = add_action
sys.argv = [game_module.__file__]
game_module.main()
print(json.dumps({'native_checks': checks, 'failures': failures}), flush=True)
raise SystemExit(1 if failures else 0)
