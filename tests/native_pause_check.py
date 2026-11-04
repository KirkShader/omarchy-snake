"""Run explicitly: pause reasons, launch chooser, colour dialog and focus loss in real GTK."""
import random
import sys

from native_support import NativeCheck, isolate_from_desktop_focus, screenshot, until

from gi.repository import Gdk, Gtk

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
from omarchy_snake.rules import MovementPreview  # noqa: E402


def factory():
    game = MovementPreview(rng=random.Random(41), difficulty='Easy')
    return game


def press(c, name):
    return c.on_key(None, Gdk.keyval_from_name(name), 0, 0)


def scenario(c, check):
    game, session, w = c.game, c.session, c.widgets
    isolate_from_desktop_focus(c)

    # Launch chooser is up before the first move; nothing moves while it is open.
    assert w['difficulty-overlay'].get_visible() and session.reasons == {'difficulty'}, session.reasons
    yield 500
    assert game.ticks == 0 and session.timer is None, (game.ticks, session.timer)
    check.ok('launch_chooser_open_before_first_move')
    assert press(c, 'Escape')
    assert not w['difficulty-overlay'].get_visible()
    yield until(lambda: game.ticks >= 2, label='movement after closing chooser')
    check.ok('escape_closes_chooser_and_starts_run')

    # Manual pause via Escape freezes board and green cooldown; steering is not consumed.
    game.foods = set()
    game.green_elapsed_ms = 29000
    assert press(c, 'Escape')
    assert w['pause-overlay'].get_visible() and w['pause-title'].get_label() == '❚❚ Paused'
    assert 'Paused' in w['movement-status'].get_label()
    frozen = (list(game.snake), game.ticks, game.green_elapsed_ms)
    press(c, 'Up')  # moves focus within the Paused card instead of steering
    assert game.queued_turns == [] and c.window.get_focus() in c.modal_buttons()
    check.ok('steering_not_consumed_while_paused')
    yield 1200
    assert (game.snake, game.ticks, game.green_elapsed_ms) == frozen
    assert session.timer is None
    assert not w['main-menu'].get_sensitive()
    check.ok('manual_pause_freezes_board_and_green_timer')
    check.artifacts['paused_screenshot'] = screenshot('paused')

    # Resume button restarts with a reset timestamp: no catch-up credit for 1.2 s paused.
    w['pause-resume'].emit('clicked')
    assert not w['pause-overlay'].get_visible() and session.timer is not None
    yield until(lambda: game.ticks > frozen[1], label='first move after resume')
    credited = game.green_elapsed_ms - frozen[2]
    assert 0 < credited <= 2 * game.step_interval_ms, credited
    yield until(lambda: game.green_dot is not None, timeout_ms=2500, label='green after remaining 1 s')
    check.ok('resume_resets_clock_no_catch_up_and_cooldown_completes')

    # Menu pauses; the menu's Pause item engages a manual pause that closing the menu keeps.
    w['main-menu'].popup()
    yield until(lambda: w['main-popover'].get_visible(), label='menu open')
    assert 'menu' in session.reasons and session.timer is None
    ticks = game.ticks
    yield 450
    assert game.ticks == ticks
    check.ok('menu_open_pauses_movement')
    c.window.lookup_action('pause').activate(None)
    yield until(lambda: not w['main-popover'].get_visible(), label='menu closed')
    assert session.reasons == {'manual'}, session.reasons
    yield 400
    assert game.ticks == ticks and w['pause-overlay'].get_visible()
    check.ok('closing_menu_does_not_resume_manual_pause')
    # Escape closes the innermost surface only: chooser over a manual pause stays paused.
    w['pause-new-game'].emit('clicked')
    assert w['difficulty-overlay'].get_visible() and session.reasons == {'manual', 'difficulty'}
    w['difficulty-normal'].emit('clicked')  # details page: still both reasons, no reset
    assert w['difficulty-details-page'].get_visible() and session.reasons == {'manual', 'difficulty'}
    assert press(c, 'Escape') is True and w['difficulty-choices-page'].get_visible()
    assert session.reasons == {'manual', 'difficulty'} and game.difficulty == 'Easy'
    assert press(c, 'Escape') is True
    assert not w['difficulty-overlay'].get_visible() and w['pause-overlay'].get_visible()
    assert session.reasons == {'manual'} and c.window.get_focus() in c.modal_buttons()
    check.ok('escape_from_chooser_keeps_manual_pause')
    assert press(c, 'Escape') is True and not session.paused
    yield until(lambda: game.ticks > ticks, label='moving after Escape resume')
    w['main-menu'].popup()
    yield until(lambda: w['main-popover'].get_visible(), label='menu open for Escape')
    assert press(c, 'Escape') is True
    yield until(lambda: not w['main-popover'].get_visible(), label='Escape closed menu')
    assert not session.paused
    ticks = game.ticks
    yield until(lambda: game.ticks > ticks, label='moving after Escape closed menu')
    check.ok('escape_closes_menu_without_manual_pause')

    # Colour chooser keeps the run paused even after the popover closes.
    w['main-menu'].popup()
    yield until(lambda: w['main-popover'].get_visible(), label='menu open for options')
    c.window.lookup_action('options').activate(None)
    w['border-color'].emit('clicked')
    yield until(lambda: any(t.get_visible() and t.get_title() == 'Border colour'
                            for t in Gtk.Window.list_toplevels() if t is not c.window),
                label='native colour dialog')
    assert 'color' in session.reasons
    w['main-popover'].popdown()
    ticks = game.ticks
    yield 450
    assert 'color' in session.reasons and game.ticks == ticks and session.timer is None, session.reasons
    check.ok('colour_dialog_keeps_pause_after_popover_closes')
    for toplevel in Gtk.Window.list_toplevels():
        if toplevel is not c.window and toplevel.get_title() == 'Border colour':
            toplevel.close()
    yield until(lambda: 'color' not in session.reasons, label='dialog close releases colour pause')
    yield until(lambda: game.ticks > ticks, label='moving after colour dialog closes')
    check.ok('closing_colour_dialog_resumes_when_no_other_reason')

    # Real focus loss: reconnect the policy, then let a second toplevel take compositor focus.
    c.focus_handler = c.window.connect('notify::is-active', c.on_active_changed)
    c.window.present()
    yield 400
    if c.window.is_active():
        # Opening the menu blips is-active on Wayland; it must not leave a manual pause.
        w['main-menu'].popup()
        yield 700
        blip_ok = c.window.is_active()
        if blip_ok:
            assert session.reasons == {'menu'}, session.reasons
        w['main-popover'].popdown()
        yield 400
        if blip_ok and c.window.is_active():
            assert not session.paused, session.reasons
            check.ok('menu_focus_blip_does_not_engage_manual_pause')
        else:
            check.artifacts['menu_blip_check_skipped'] = 'window lost focus to the desktop meanwhile'
            session.resume('manual')
    if c.window.is_active():
        w['main-menu'].popup()
        yield until(lambda: w['main-popover'].get_visible(), label='menu for dialog focus test')
        c.window.lookup_action('options').activate(None)
        w['grid-color'].emit('clicked')
        yield until(lambda: any(t.get_visible() and t.get_title() == 'Grid-line colour'
                                for t in Gtk.Window.list_toplevels() if t is not c.window),
                    label='grid colour dialog open')
        inactive_samples = []
        for _ in range(7):
            yield 100
            inactive_samples.append(not c.window.is_active())
        check.artifacts['main_window_inactive_while_dialog_open'] = inactive_samples
        assert 'color' in session.reasons and 'manual' not in session.reasons, session.reasons
        for toplevel in Gtk.Window.list_toplevels():
            if toplevel is not c.window and toplevel.get_title() == 'Grid-line colour':
                toplevel.close()
        yield until(lambda: 'color' not in session.reasons, label='dialog closed')
        check.ok('focus_moving_to_own_colour_dialog_is_not_a_manual_pause')
        w['main-popover'].popdown()
        yield 500
        if 'manual' in session.reasons:  # desktop focus (follow-mouse) may legitimately pause
            check.artifacts['after_dialog_focus'] = 'window not refocused; manual pause engaged'
            session.resume('manual')
        c.window.present()
        yield 400
    if c.window.is_active():
        helper = Gtk.Window(title='Omarchy Snake focus-check helper')
        helper.set_default_size(240, 80)
        helper.present()
        yield until(lambda: not c.window.is_active(), timeout_ms=3000, label='compositor moves focus')
        assert 'focus' in session.reasons and session.timer is None  # frozen immediately
        yield until(lambda: 'manual' in session.reasons, timeout_ms=1500,
                    label='sustained focus loss confirmed as manual pause')
        ticks = game.ticks
        yield 400
        assert game.ticks == ticks and w['pause-overlay'].get_visible()
        check.ok('real_focus_loss_engages_manual_pause')
        helper.close()
        yield 400
        # Whether focus returns depends on the pointer (follow_mouse); either way, manual remains.
        assert 'manual' in session.reasons
        check.ok('focus_return_does_not_resume_manual_pause')
        check.artifacts['focus_returned_to_game'] = c.window.is_active()
    else:
        check.artifacts['focus_loss_skipped'] = 'compositor did not give the game window focus'
    c.window.disconnect(c.focus_handler)
    session.resume('focus')
    session.resume('manual')

    # Pause is unavailable after a loss.
    game.snake = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
                  (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]
    game.direction, game.queued_turns, game.foods = 'Right', [], set()
    yield until(lambda: game.game_over, label='self collision')
    assert press(c, 'Escape') is False and 'manual' not in session.reasons
    assert w['game-over-overlay'].get_visible() and not w['pause-overlay'].get_visible()
    assert session.timer is None
    check.ok('pause_unavailable_after_loss')


if __name__ == '__main__':
    raise SystemExit(NativeCheck('pause', ['--show-difficulty'], factory).run(scenario))
