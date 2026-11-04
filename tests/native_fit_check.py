"""Run explicitly: display fit with real GTK allocation on the actual monitor.

Phases (sequential, each a separate isolated app run):
  real    — the monitor the window opens on, default zoom, Easy.
  1080p   — --fit-limit simulating a 1920x1080 scale-1 usable area.
  2x1080p — --fit-limit simulating 1920x1080 at scale 2 (scroll fallback for Easy).
  monitor — Hard; a controlled monitor provider shrinks the logical geometry (enter-monitor,
            then a geometry change), then leave-monitor returns to the real monitor; the
            real allocation must follow each time, and close must disconnect the watch.
--fit-limit and the controlled monitor only change the area the app fits into; the real
monitor configuration is untouched.
"""
import json
import random
import sys
from pathlib import Path

from native_support import (NativeCheck, choose_and_start, frame_origin, hypr_client, hypr_monitor,
                            isolate_from_desktop_focus, screenshot, until)
from gi.repository import Gdk, GObject  # noqa: E402  (versions pinned by native_support)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake.geometry import SCREEN_ALLOWANCE, fit_board, logical_size  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402


def factory():
    return MovementPreview(rng=random.Random(7), difficulty='Easy')


def hard_factory():
    return MovementPreview(rng=random.Random(7), difficulty='Hard')


def board_fits_allocation(c):
    board = c.widgets['playing-board']
    return board.get_width() >= c.fit.frame_pixels and board.get_height() >= c.fit.frame_pixels


def real_monitor(c, check):
    isolate_from_desktop_focus(c)
    yield until(lambda: c.window.get_mapped() and c.chrome != (32, 170), label='chrome measured')
    yield 300
    width, height = c.usable_area()
    assert (c.fit.cells, c.fit.cell_pixels) == (64, 16), c.fit
    assert board_fits_allocation(c)
    assert c.window.get_height() <= height and c.window.get_width() <= width, (c.window.get_height(), height)
    x, y = frame_origin(c)
    assert isinstance(x, int) and isinstance(y, int)
    check.ok('easy_default_16px_fits_real_monitor')
    client = hypr_client()
    if client:
        monitor = hypr_monitor(client['monitor'])
        mw, mh = logical_size(monitor['width'], monitor['height'], monitor['scale'])
        cx, cy = client['at'][0] - monitor['x'], client['at'][1] - monitor['y']
        assert 0 <= cx and 0 <= cy and cx + client['size'][0] <= mw and cy + client['size'][1] <= mh, (client, monitor)
        check.artifacts['real_monitor'] = {'name': monitor['name'], 'mode': [monitor['width'], monitor['height']],
                                           'scale': monitor['scale'], 'window_at': client['at'],
                                           'window_size': client['size'], 'chrome': list(c.chrome)}
        check.ok('hyprland_reports_window_fully_on_monitor')
    # Hard with Auto fit grows cells; the number of cells and snake coordinates stay the same.
    c.window.lookup_action('new-game').activate(None)
    choose_and_start(c, 'Hard')
    c.session.pause('menu')  # hold the snake still while zoom changes
    snake = list(c.game.snake)
    c.widgets['zoom-select'].set_selected(0)  # Auto fit
    yield until(lambda: c.zoom == 'auto' and board_fits_allocation(c), label='auto fit applied')
    yield 300
    assert c.game.grid_cells == 32 and c.fit.cell_pixels > 16, c.fit
    assert c.game.snake == snake, 'zoom must not move or rescale snake coordinates'
    c.session.resume('menu')
    assert c.window.get_height() <= height, (c.window.get_height(), height)
    saved = json.loads((check.config_dir / 'settings.json').read_text())
    assert saved['zoom'] == 'auto' and saved['version'] == 1, saved
    check.artifacts['hard_auto_cell_pixels'] = c.fit.cell_pixels
    check.artifacts['hard_auto_screenshot'] = screenshot('fit-hard-auto')
    check.ok('auto_fit_scales_rendering_not_cells_and_persists_zoom')
    c.widgets['zoom-select'].set_selected(1)  # 50%
    yield until(lambda: c.fit.cell_pixels == 8 and board_fits_allocation(c), label='50% zoom')
    check.ok('zoom_50_percent_applies')


def simulated(expected_cell, scroll):
    def scenario(c, check):
        isolate_from_desktop_focus(c)
        yield until(lambda: c.window.get_mapped() and c.chrome != (32, 170), label='chrome measured')
        yield 400
        width, height = c.usable_area()
        assert c.fit.cell_pixels == expected_cell, (c.fit, c.chrome)
        assert c.fit.scroll_fallback == scroll
        assert c.chrome_measure is None and c.measured_chrome() == c.chrome, (c.measured_chrome(), c.chrome)
        assert c.window.get_height() <= height and c.window.get_width() <= width, (
            c.window.get_width(), c.window.get_height(), width, height)
        scroller = c.widgets['board-scroller']
        vadj = scroller.get_vadjustment()
        scrolls = vadj.get_upper() > vadj.get_page_size() + 0.5
        assert scrolls == scroll, (vadj.get_upper(), vadj.get_page_size())
        check.artifacts['allocated'] = {'window': [c.window.get_width(), c.window.get_height()],
                                        'usable': [width, height], 'cell_pixels': c.fit.cell_pixels,
                                        'viewport': [scroller.get_width(), scroller.get_height()],
                                        'board_extent': vadj.get_upper(), 'chrome': list(c.chrome)}
        check.ok(f'allocated_window_within_simulated_area_cell_{expected_cell}')
        if scroll:
            # Send the head toward the bottom edge; the viewport must follow it.
            c.game.foods = set()
            c.game.direction = 'Down'
            c.game.snake = [(30, 50 - i) for i in range(6)]
            yield until(lambda: c.game.snake[0][1] >= 60, timeout_ms=4000, label='head near bottom')
            yield 100
            head_y = 6 + c.game.snake[0][1] * c.fit.cell_pixels
            assert vadj.get_value() <= head_y <= vadj.get_value() + vadj.get_page_size(), (
                head_y, vadj.get_value(), vadj.get_page_size())
            check.ok('scroll_fallback_keeps_head_visible')
        check.artifacts['screenshot'] = screenshot(f'fit-{expected_cell}px')
    return scenario


class ControlledMonitor(GObject.Object):
    """Stand-in for the window's Gdk.Monitor with settable logical geometry and scale.

    The app reads it through its monitor provider; the real display is never changed.
    """
    __gsignals__ = {'invalidate': (GObject.SignalFlags.RUN_LAST, None, ())}
    geometry = GObject.Property(type=object)
    scale = GObject.Property(type=float, default=1.0)

    def get_geometry(self):
        return self.geometry

    def resize(self, width, height):
        rectangle = Gdk.Rectangle()
        rectangle.width, rectangle.height = width, height
        self.geometry = rectangle  # emits notify::geometry like a real monitor


def allocated_within(c, width, height):
    board = c.widgets['playing-board']
    return (c.window.get_width() <= width and c.window.get_height() <= height
            and board.get_width() >= c.fit.frame_pixels and board.get_height() >= c.fit.frame_pixels)


def settled_fit(c, width, height):
    """The model's chrome is what the real allocation measures now (a reduced board rewraps
    the footer), its fit for that chrome is applied, and the real window is inside the area."""
    return (c.chrome_measure is None and c.measured_chrome() == c.chrome
            and c.fit.cell_pixels == fit_board(32, width, height, *c.chrome).cell_pixels
            and allocated_within(c, width, height))


def monitor_change(c, check):
    isolate_from_desktop_focus(c)
    yield until(lambda: c.window.get_mapped() and c.chrome != (32, 170), label='chrome measured')
    yield 300
    c.session.pause('menu')  # hold the snake still; fit is independent of movement
    real = c.monitor_provider()
    assert c.fit.cell_pixels == 16, c.fit
    fits = []
    original_apply_fit = c.apply_fit

    def counted_apply_fit():
        fits.append(list(c.usable_area()))
        original_apply_fit()
    c.apply_fit = counted_apply_fit
    surface = c.window.get_surface()
    controlled = ControlledMonitor()
    controlled.resize(*logical_size(1920, 1080, 1.5))  # 1280x720 logical
    c.monitor_provider = lambda: controlled
    surface.emit('enter-monitor', real)  # the compositor reports the surface on a monitor
    usable = (1280 - SCREEN_ALLOWANCE[0], 720 - SCREEN_ALLOWANCE[1])
    yield until(lambda: settled_fit(c, *usable), label=f'settled refit within {usable}')
    assert c.monitor_watch.monitor is controlled and c.fit.cell_pixels < 16, (c.monitor_watch.monitor, c.fit)
    check.artifacts['enter_monitor_1280x720'] = {'cell_pixels': c.fit.cell_pixels, 'chrome': list(c.chrome),
                                                'window': [c.window.get_width(), c.window.get_height()],
                                                'usable': list(usable)}
    check.artifacts['screenshot_1280x720'] = screenshot('fit-monitor-1280x720')
    check.ok('enter_monitor_refits_to_smaller_logical_geometry')

    controlled.resize(*logical_size(1920, 1080, 2))  # geometry change on the same monitor
    usable = (960 - SCREEN_ALLOWANCE[0], 540 - SCREEN_ALLOWANCE[1])
    smaller = c.fit.cell_pixels
    yield until(lambda: settled_fit(c, *usable), label=f'settled refit within {usable}')
    assert c.fit.cell_pixels < smaller, (c.fit, smaller)
    expected = c.fit.cell_pixels
    check.artifacts['geometry_960x540'] = {'cell_pixels': c.fit.cell_pixels, 'chrome': list(c.chrome),
                                          'window': [c.window.get_width(), c.window.get_height()],
                                          'usable': list(usable)}
    check.ok('monitor_geometry_change_refits_allocation')

    settled = len(fits)
    controlled.scale = 2.0  # property change that leaves the logical area alone
    surface.emit('enter-monitor', real)
    yield 600
    assert len(fits) == settled, fits
    assert c.monitor_watch.pending is None
    check.ok('unchanged_area_and_own_resize_do_not_refit_again')

    c.monitor_provider = c.current_monitor
    surface.emit('leave-monitor', real)
    yield until(lambda: c.fit.cell_pixels == 16 and settled_fit(c, *c.usable_area()),
                label='back to 16px on the real monitor')
    assert c.monitor_watch.monitor is real
    check.ok('leave_monitor_refits_back_to_real_monitor')

    c.monitor_provider = lambda: controlled  # finish on the controlled monitor
    surface.emit('enter-monitor', real)
    yield until(lambda: c.monitor_watch.monitor is controlled and c.fit.cell_pixels == expected
                and settled_fit(c, *usable), label='controlled monitor tracked before close')
    yield 300
    check.artifacts['apply_fit_usable_areas'] = fits
    check.controlled = controlled


def monitor_watch_closed(c, check):
    watch, controlled = c.monitor_watch, check.controlled
    assert watch.closed and watch.pending is None, watch.__dict__
    assert watch.handlers == [] and watch.monitor_handlers == [], watch.__dict__
    assert c.chrome_measure is None, c.chrome_measure
    refits = len(check.artifacts['apply_fit_usable_areas'])
    controlled.resize(800, 600)  # after close: no handler may run
    controlled.emit('invalidate')
    assert watch.pending is None and len(check.artifacts['apply_fit_usable_areas']) == refits
    check.ok('close_disconnects_monitor_watch')


def limit(physical, scale):
    width, height = logical_size(*physical, scale)
    return f'{width - SCREEN_ALLOWANCE[0]}x{height - SCREEN_ALLOWANCE[1]}'


if __name__ == '__main__':
    results = [NativeCheck('fit_real', [], factory).run(real_monitor)]
    # The simulated expectations are recomputed from the measured chrome inside the run;
    # these are the values for this window's real header/footer (see test_geometry for models).
    results.append(NativeCheck('fit_1080p', ['--fit-limit', limit((1920, 1080), 1)], factory)
                   .run(simulated(13, False)))
    results.append(NativeCheck('fit_2x1080p', ['--fit-limit', limit((1920, 1080), 2)], factory)
                   .run(simulated(6, True)))
    results.append(NativeCheck('fit_monitor_change', [], hard_factory)
                   .run(monitor_change, after_close=monitor_watch_closed))
    raise SystemExit(max(results))
