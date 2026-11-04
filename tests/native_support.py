"""Shared harness for explicit native GTK checks (not collected by unittest discovery).

Each check runs the real app with its own GApplication ID and temporary config/state
directories, so it never attaches to or writes over the user's game. Scenarios are
generators: yield a number to wait that many ms, or a predicate to wait (polling) until
it holds. The window is always closed at the end, on failure, or on a global timeout.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import grid_preview  # noqa: E402
from omarchy_snake.drawing import draw_board  # noqa: E402
from omarchy_snake.geometry import board_layout  # noqa: E402


def scratch_dir():
    """Screenshots/reports: $OMARCHY_SNAKE_SCRATCH, else runtime dir, else the system temp dir."""
    configured = os.environ.get('OMARCHY_SNAKE_SCRATCH')
    base = Path(configured) if configured else Path(os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir())
    path = base if configured else base / 'omarchy-snake-checks'
    path.mkdir(parents=True, exist_ok=True)
    return path


class Wait:
    def __init__(self, predicate, timeout_ms=3000, label=None):
        self.predicate, self.timeout_ms = predicate, timeout_ms
        self.label = label or getattr(predicate, '__name__', 'condition')


def until(predicate, timeout_ms=3000, label=None):
    return Wait(predicate, timeout_ms, label)


def rgb(widget):
    color = widget.get_rgba()
    return tuple(round(v * 255) for v in (color.red, color.green, color.blue))


def set_rgb(widget, text):
    color = Gdk.RGBA()
    assert color.parse(text)
    widget.set_rgba(color)


def board_pixel(controller, x, y):
    """Render the real board draw path at its allocated size and read one pixel."""
    board = controller.widgets['playing-board']
    width, height = board.get_width(), board.get_height()
    image = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    controller.draw(board, cairo.Context(image), width, height)
    image.flush()
    raw = struct.unpack_from('=I', image.get_data(), y * image.get_stride() + x * 4)[0]
    return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)


def frame_origin(controller):
    board = controller.widgets['playing-board']
    return board_layout(controller.fit, board.get_width(), board.get_height())


def hypr_client(pid=None):
    """This process's window as Hyprland reports it, or None outside Hyprland."""
    if not shutil.which('hyprctl') or not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        return None
    clients = json.loads(subprocess.check_output(['hyprctl', 'clients', '-j']))
    pid = os.getpid() if pid is None else pid
    return next((c for c in clients if c.get('pid') == pid), None)


def hypr_monitor(monitor_id):
    monitors = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j']))
    return next(m for m in monitors if m['id'] == monitor_id)


def screenshot(name):
    """Capture this process's window with grim; returns the path, or None if unavailable."""
    client = hypr_client()
    if client is None or not shutil.which('grim'):
        return None
    x, y = client['at']
    width, height = client['size']
    path = scratch_dir() / f'omarchy-snake-{name}.png'
    subprocess.run(['grim', '-g', f'{x},{y} {width}x{height}', str(path)], check=True)
    return str(path)


def choose_and_start(controller, difficulty):
    """With the chooser open: click a difficulty (details only, nothing reset), then Start."""
    w, game = controller.widgets, controller.game
    before = (game.difficulty, game.grid_cells, game.score, game.state)
    w['difficulty-' + difficulty.lower()].emit('clicked')
    assert w['difficulty-details-page'].get_visible() and not w['difficulty-choices-page'].get_visible()
    assert w['difficulty-details-title'].get_label() == difficulty
    assert (game.difficulty, game.grid_cells, game.score, game.state) == before, 'choosing must not reset'
    w['difficulty-start'].emit('clicked')
    assert not w['difficulty-overlay'].get_visible() and game.difficulty == difficulty


def isolate_from_desktop_focus(controller):
    """Detach the focus policy so the user's pointer/focus cannot pause a scripted check.

    The focus policy itself is covered by unit tests and native_pause_check's real
    focus-loss scenario.
    """
    controller.window.disconnect(controller.focus_handler)
    controller.session.resume('focus')
    if 'manual' in controller.session.reasons and not controller.args.show_difficulty:
        controller.session.resume('manual')


class NativeCheck:
    def __init__(self, name, extra_args=(), game_factory=None, global_timeout_ms=60000, shared_temp=None):
        """`shared_temp` (a TemporaryDirectory) lets sequential launches share settings/state."""
        self.name = name
        self.app_id = f'local.omarchy.snake.check.{name.replace("_", "-")}.p{os.getpid()}'
        self.owns_temp = shared_temp is None
        self.temp = shared_temp or tempfile.TemporaryDirectory(prefix=f'omarchy-snake-{name}-')
        self.config_dir = Path(self.temp.name) / 'config'
        self.state_dir = Path(self.temp.name) / 'state'
        self.extra_args = list(extra_args)
        self.game_factory = game_factory
        self.global_timeout_ms = global_timeout_ms
        self.checks, self.failures, self.artifacts = [], [], {}
        self.controller = None
        self.scenario_factory = None

    def argv(self):
        return ['--application-id', self.app_id, '--config-dir', str(self.config_dir),
                '--state-dir', str(self.state_dir)] + self.extra_args

    def ok(self, label):
        self.checks.append(label)
        print(json.dumps({'check': label}), flush=True)

    def run(self, scenario_factory, after_close=None):
        """`after_close(controller, check)` runs once the app has exited (cleanup checks)."""
        self.scenario_factory = scenario_factory
        try:
            code = grid_preview.main(self.argv(), self.game_factory, self._ready)
            if after_close and self.controller and not self.failures:
                try:
                    after_close(self.controller, self)
                except Exception:
                    self.failures.append(traceback.format_exc())
        finally:
            leftover = [w for w in Gtk.Window.list_toplevels() if w.get_visible()]
            if self.owns_temp:
                self.temp.cleanup()
        summary = {'native_check': self.name, 'app_id': self.app_id, 'checks': self.checks,
                   'failures': self.failures, 'artifacts': self.artifacts,
                   'visible_windows_after_exit': len(leftover), 'app_exit_code': code}
        print(json.dumps(summary, indent=2), flush=True)
        return 1 if self.failures or code else 0

    def _ready(self, controller, kind):
        if kind != 'activated':
            self.on_reactivated(controller)
            return
        self.controller = controller
        GLib.timeout_add(self.global_timeout_ms, self._timeout)
        steps = self.scenario_factory(controller, self)
        GLib.timeout_add(300, lambda: self._advance(steps) and False)

    def on_reactivated(self, controller):
        self.artifacts.setdefault('reactivations', 0)
        self.artifacts['reactivations'] += 1

    def _timeout(self):
        self.failures.append(f'global timeout after {self.global_timeout_ms} ms')
        self._close()
        return GLib.SOURCE_REMOVE

    def _close(self):
        for window in list(Gtk.Window.list_toplevels()):
            if window.get_visible() and window is not self.controller.window:
                window.close()
        self.controller.window.close()

    def _advance(self, steps, _value=None):
        try:
            item = next(steps)
        except StopIteration:
            self._close()
            return False
        except Exception:
            self.failures.append(traceback.format_exc())
            self._close()
            return False
        if isinstance(item, Wait):
            self._poll(steps, item, 0)
        else:
            GLib.timeout_add(int(item), lambda: self._advance(steps) and False)
        return False

    def _poll(self, steps, wait, waited):
        try:
            satisfied = wait.predicate()
        except Exception:
            self.failures.append(traceback.format_exc())
            self._close()
            return
        if satisfied:
            GLib.idle_add(lambda: self._advance(steps) and False)
        elif waited >= wait.timeout_ms:
            self.failures.append(f'timed out after {wait.timeout_ms} ms waiting for: {wait.label}')
            self._close()
        else:
            GLib.timeout_add(20, lambda: self._poll(steps, wait, waited + 20) and False)
