"""GTK4 window and controller: builds widgets and routes events to the tested models."""
import argparse
import json
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .audio import AudioDirector, create_backend  # noqa: E402
from .chooser import NewGameChooser  # noqa: E402
from .drawing import BORDER_PIXELS, draw_board, draw_board_border  # noqa: E402
from .geometry import (  # noqa: E402
    SCREEN_ALLOWANCE, ZOOM_LABELS, ZOOM_LEVELS, board_layout, fit_board, scroll_to_keep_visible)
from .log import GameLog  # noqa: E402
from .monitor import MonitorWatch  # noqa: E402
from .preferences import BestScores, PreferenceStore  # noqa: E402
from .rules import DIFFICULTIES, GREEN_INTERVAL_MS, MovementPreview  # noqa: E402
from .session import FOCUS_LOSS_CONFIRM_MS, GameSession, escape_action  # noqa: E402
from .text import DIFFICULTY_DETAILS, REWARD_HELP, hud_text, status_text  # noqa: E402
from .theme import GAME_OVER_HEX, board_colors, build_css, is_reserved_color, load_omarchy_palette  # noqa: E402

APPLICATION_ID = 'local.omarchy.snake.preview'  # Stable: the user's window rules match it.
CHROME_ESTIMATE = (32, 170)  # Replaced by the measured header/footer size once mapped.
NAVIGATION_KEYS = {'Tab': 1, 'ISO_Left_Tab': -1, 'Right': 1, 'Down': 1, 'Left': -1, 'Up': -1}


def rgb_to_rgba(rgb):
    rgba = Gdk.RGBA()
    rgba.parse('#' + ''.join(f'{channel:02x}' for channel in rgb))
    return rgba


def rgba_to_rgb(rgba):
    return tuple(round(channel * 255) for channel in (rgba.red, rgba.green, rgba.blue))


class GLibScheduler:
    def add(self, interval_ms, callback):
        return GLib.timeout_add(interval_ms, callback)

    def remove(self, source):
        GLib.source_remove(source)


class ColorSwatchButton(Gtk.Button):
    """Swatch button opening Gtk.ColorDialog; open/close are reported so the game pauses."""
    __gtype_name__ = 'OmarchySnakeColorSwatchButton'

    def __init__(self, title, rgb, on_dialog, on_change):
        super().__init__()
        self.title, self.rgb = title, tuple(rgb)
        self.on_dialog, self.on_change = on_dialog, on_change
        swatch = Gtk.DrawingArea()
        swatch.set_content_width(36)
        swatch.set_content_height(18)
        swatch.set_draw_func(self._draw)
        self.swatch = swatch
        self.set_child(swatch)
        self.set_tooltip_text(title)
        self.update_property([Gtk.AccessibleProperty.LABEL], [title])
        self.connect('clicked', self._open)

    def _draw(self, _area, cr, width, height):
        cr.set_source_rgb(*(channel / 255 for channel in self.rgb))
        cr.rectangle(0, 0, width, height)
        cr.fill()

    def get_rgba(self):
        return rgb_to_rgba(self.rgb)

    def set_rgba(self, rgba):
        """Apply a chosen colour through the same validation as the native dialog."""
        self.on_change(self, rgba_to_rgb(rgba))

    def show_rgb(self, rgb):
        self.rgb = tuple(rgb)
        self.swatch.queue_draw()

    def _open(self, _button):
        dialog = Gtk.ColorDialog()
        dialog.set_title(self.title)
        dialog.set_with_alpha(False)
        dialog.set_modal(True)
        self.on_dialog(True)
        dialog.choose_rgba(self.get_root(), self.get_rgba(), None, self._chosen)

    def _chosen(self, dialog, result):
        try:
            rgba = dialog.choose_rgba_finish(result)
        except GLib.Error:  # Cancelled or dismissed: keep the current colour.
            rgba = None
        if rgba is not None:
            self.set_rgba(rgba)
        self.on_dialog(False)


class SnakeWindow:
    """One game window. Native checks reach widgets through `widgets` by name."""

    def __init__(self, application, args, game, store, log):
        self.args, self.game, self.store, self.log = args, game, store, log
        settings = store.load_settings()
        self.appearance = {'border_rgb': settings['border_rgb'], 'grid_rgb': settings['grid_rgb']}
        self.zoom = settings['zoom']
        self.best_scores = BestScores(store)
        self.widgets = {}
        self.palette = None
        self.chrome = CHROME_ESTIMATE
        self.chrome_measure = None  # (frame clock, after-paint handler) while a re-measure waits
        self.fit = self.fit_usable = None
        self.monitor_provider = self.current_monitor  # native checks substitute a controlled one
        self.monitor_watch = MonitorWatch(self.refit_for_monitor, GLib.idle_add, GLib.source_remove)
        self.focus_before_modal = None
        self.modal_visible = False
        self.focus_check = None
        self.audio = AudioDirector(create_backend(log), store.load_audio())
        self.session = GameSession(game, GLibScheduler(), listener=self.on_session)
        self.chooser = NewGameChooser()
        self.window = Gtk.ApplicationWindow(application=application)
        self.window.add_css_class('snake-window')
        self.window.set_title('Omarchy Snake')
        self.window.set_resizable(False)
        self.css = Gtk.CssProvider()
        self.refresh_theme()
        Gtk.StyleContext.add_provider_for_display(
            self.window.get_display(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._build_header()
        self._build_body()
        self._build_chooser()
        self._build_state_cards()
        self._install_actions()
        self._install_input()
        self.theme_timer = GLib.timeout_add_seconds(1, self.refresh_theme)
        self.window.connect('close-request', self.on_close)
        self.focus_handler = self.window.connect('notify::is-active', self.on_active_changed)
        self.window.connect('realize', self.on_realize)
        self.window.connect('map', lambda _w: GLib.idle_add(self.measure_chrome))
        self.apply_fit()
        self.refresh_labels()

    # ---- construction -------------------------------------------------------------
    def name(self, widget, name):
        widget.set_name(name)
        self.widgets[name] = widget
        return widget

    def _build_header(self):
        header = Gtk.HeaderBar()
        title = self.name(Gtk.Label(label='Omarchy Snake'), 'header-title')
        title.add_css_class('snake-title')
        header.set_title_widget(title)
        menu = self.name(Gtk.MenuButton(label='Menu'), 'main-menu')
        popover = self.name(Gtk.Popover(), 'main-popover')
        popover.set_has_arrow(False)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_halign(Gtk.Align.START)
        popover.add_css_class('snake-menu-popover')
        popover.connect('notify::visible', self.on_popover_visible)
        frame = self.name(Gtk.Overlay(), 'menu-frame')
        menu_border = Gtk.DrawingArea()
        menu_border.set_content_width(200)
        menu_border.set_content_height(176)
        menu_border.set_draw_func(lambda _w, cr, w, h:
                                  draw_board_border(cr, w, h, color=self.appearance['border_rgb']))
        self.menu_border = menu_border
        frame.set_child(menu_border)
        menu_panel = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), 'main-menu-panel')
        menu_panel.add_css_class('snake-menu-panel')
        self._margins(menu_panel, BORDER_PIXELS)
        self.menu_buttons = []
        for label, action, name in [('New Game', 'win.new-game', 'menu-new-game'),
                                    ('Pause', 'win.pause', 'menu-pause'),
                                    ('Options', 'win.options', 'menu-options'),
                                    ('Quit', 'win.quit', 'menu-quit')]:
            button = self.name(Gtk.Button(label=label), name)
            button.set_hexpand(True)
            button.set_vexpand(True)
            button.set_action_name(action)
            menu_panel.append(button)
            self.menu_buttons.append(button)
        frame.add_overlay(menu_panel)
        frame.set_measure_overlay(menu_panel, True)
        frame.add_overlay(self._build_options())
        frame.set_measure_overlay(self.widgets['options-panel'], True)
        popover.set_child(frame)
        popover.connect('closed', self.show_main_menu)
        menu.set_popover(popover)
        header.pack_start(menu)
        hud = self.name(Gtk.Label(), 'hud')
        hud.add_css_class('snake-hud')
        header.pack_end(hud)
        self.window.set_titlebar(header)

    def _build_options(self):
        panel = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6), 'options-panel')
        panel.add_css_class('snake-menu-panel')
        self._margins(panel, BORDER_PIXELS)
        panel.append(Gtk.Label(label='Appearance'))
        message = self.name(Gtk.Label(), 'appearance-message')
        message.add_css_class('snake-appearance-warning')
        message.set_wrap(True)
        message.set_max_width_chars(26)
        message.set_margin_start(12)
        message.set_margin_end(12)
        message.set_visible(False)
        panel.append(message)
        for label, key, name in [('Border colour', 'border_rgb', 'border-color'),
                                 ('Grid-line colour', 'grid_rgb', 'grid-color')]:
            picker = ColorSwatchButton(label, self.appearance[key], self.on_color_dialog,
                                       lambda button, rgb, key=key: self.on_color_chosen(button, key, rgb))
            self.name(picker, name)
            panel.append(self._row(label, picker))
        zoom = self.name(Gtk.DropDown.new_from_strings([ZOOM_LABELS[z] for z in ZOOM_LEVELS]), 'zoom-select')
        zoom.set_selected(list(ZOOM_LEVELS).index(self.zoom))
        zoom.connect('notify::selected', self.on_zoom_selected)
        zoom.update_property([Gtk.AccessibleProperty.LABEL], ['Board zoom'])
        panel.append(self._row('Board zoom', zoom))
        panel.append(Gtk.Label(label='Sound'))
        for label, key, name in [('Music', 'music_enabled', 'music-switch'),
                                 ('Sound Effects', 'sfx_enabled', 'sfx-switch')]:
            switch = self.name(Gtk.Switch(active=self.audio.settings[key]), name)
            switch.set_valign(Gtk.Align.CENTER)
            switch.update_property([Gtk.AccessibleProperty.LABEL], [label])
            switch.connect('notify::active', self.on_audio_switch, key)
            panel.append(self._row(label, switch))
        volume = self.name(Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5), 'volume-scale')
        volume.set_value(round(self.audio.settings['master_volume'] * 100))
        volume.set_round_digits(0)
        volume.set_digits(0)
        volume.set_draw_value(True)
        volume.set_value_pos(Gtk.PositionType.RIGHT)
        volume.set_size_request(140, -1)
        volume.update_property([Gtk.AccessibleProperty.LABEL], ['Volume'])
        volume.connect('value-changed', self.on_volume_changed)
        panel.append(self._row('Volume', volume))
        back = self.name(Gtk.Button(label='Back'), 'options-back')
        back.connect('clicked', self.options_back)
        panel.append(back)
        panel.set_visible(False)
        return panel

    def _row(self, label, control):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_start(12)
        row.set_margin_end(12)
        caption = Gtk.Label(label=label, xalign=0)
        caption.set_hexpand(True)
        row.append(caption)
        row.append(control)
        return row

    def _build_body(self):
        box = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12), 'content')
        self._margins(box, 16)
        scroller = self.name(Gtk.ScrolledWindow(), 'board-scroller')
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_width(True)
        scroller.set_propagate_natural_height(True)
        scroller.set_halign(Gtk.Align.CENTER)
        board = self.name(Gtk.DrawingArea(), 'playing-board')
        board.set_focusable(True)
        board.set_draw_func(self.draw)
        board.update_property([Gtk.AccessibleProperty.LABEL], ['Snake board'])
        scroller.set_child(board)
        box.append(scroller)
        for name in ('board-info', 'movement-status'):
            label = self.name(Gtk.Label(), name)
            label.set_wrap(True)
            label.set_max_width_chars(60)
            label.set_justify(Gtk.Justification.CENTER)
            box.append(label)
        self.root = Gtk.Overlay()
        self.root.set_child(box)
        self.window.set_child(self.root)

    def _build_chooser(self):
        layer = self.name(Gtk.Overlay(), 'difficulty-overlay')
        layer.add_css_class('snake-modal-shade')
        backdrop = Gtk.Box()
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)
        layer.set_child(backdrop)
        card = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), 'difficulty-card')
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.CENTER)
        card.add_css_class('snake-difficulty-card')
        # Page 1: only the three difficulties (Escape cancels). Choosing one previews it.
        choices_page = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14),
                                 'difficulty-choices-page')
        heading = Gtk.Label(label='New Game')
        heading.add_css_class('snake-title')
        choices_page.append(heading)
        choices = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18, homogeneous=True)
        self.difficulty_buttons = {}
        for difficulty in DIFFICULTIES:
            button = self.name(Gtk.Button(label=difficulty), 'difficulty-' + difficulty.lower())
            button.set_size_request(120, 44)
            button.connect('clicked', lambda _b, choice=difficulty: self.choose_difficulty(choice))
            choices.append(button)
            self.difficulty_buttons[difficulty] = button
        choices_page.append(choices)
        card.append(choices_page)
        # Page 2: the chosen difficulty's rules; only Start commits and resets the run.
        details_page = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14),
                                 'difficulty-details-page')
        title = self.name(Gtk.Label(), 'difficulty-details-title')
        title.add_css_class('snake-title')
        details_page.append(title)
        rules = self.name(Gtk.Label(justify=Gtk.Justification.CENTER), 'difficulty-details-text')
        rules.add_css_class('snake-difficulty-detail')
        details_page.append(rules)
        help_label = self.name(Gtk.Label(label=REWARD_HELP), 'difficulty-help')
        help_label.set_wrap(True)
        help_label.set_max_width_chars(58)
        help_label.set_justify(Gtk.Justification.CENTER)
        help_label.add_css_class('snake-difficulty-detail')
        details_page.append(help_label)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER)
        self.details_buttons = []
        for name, label, callback in [('difficulty-back', 'Back', self.show_difficulty_choices),
                                      ('difficulty-start', 'Start', self.start_selected)]:
            button = self.name(Gtk.Button(label=label), name)
            button.set_size_request(120, 44)
            button.connect('clicked', lambda _b, callback=callback: callback())
            row.append(button)
            self.details_buttons.append(button)
        details_page.append(row)
        details_page.set_visible(False)
        card.append(details_page)
        layer.add_overlay(card)
        layer.set_visible(False)
        self.root.add_overlay(layer)

    def _build_state_cards(self):
        specs = [('pause-overlay', 'snake-paused', '❚❚ Paused', [('pause-resume', 'Resume'),
                                                                ('pause-new-game', 'New Game')]),
                 ('game-over-overlay', 'snake-lost', 'Game Over', [('game-over-new-game', 'New Game')]),
                 ('victory-overlay', 'snake-won', '★ Victory!', [('victory-new-game', 'New Game')])]
        self.card_buttons = {}
        for name, css_class, title, buttons in specs:
            card = self.name(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14), name)
            card.add_css_class('snake-overlay-card')
            card.add_css_class(css_class)
            card.set_halign(Gtk.Align.CENTER)
            card.set_valign(Gtk.Align.CENTER)
            heading = self.name(Gtk.Label(label=title), name.replace('overlay', 'title'))
            heading.add_css_class('snake-overlay-title')
            card.append(heading)
            detail = self.name(Gtk.Label(), name.replace('overlay', 'detail'))
            detail.set_justify(Gtk.Justification.CENTER)
            card.append(detail)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER)
            self.card_buttons[name] = []
            for button_name, label in buttons:
                button = self.name(Gtk.Button(label=label), button_name)
                button.set_size_request(150, 44)
                row.append(button)
                self.card_buttons[name].append(button)
            card.append(row)
            card.set_visible(False)
            self.root.add_overlay(card)
        self.widgets['pause-resume'].connect('clicked', lambda _b: self.session.resume('manual'))
        for name in ('pause-new-game', 'game-over-new-game', 'victory-new-game'):
            self.widgets[name].connect('clicked', lambda _b: self.open_new_game())

    def _install_actions(self):
        for name, callback in [('new-game', lambda *_a: self.open_new_game()),
                               ('pause', lambda *_a: self.manual_pause_from_menu()),
                               ('options', lambda *_a: self.show_options()),
                               ('quit', lambda *_a: self.window.close())]:
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', callback)
            self.window.add_action(action)

    def _install_input(self):
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect('key-pressed', self.on_key)
        keys.connect('key-released', self.on_key_released)
        self.window.add_controller(keys)

    @staticmethod
    def _margins(widget, value):
        for setter in (widget.set_margin_top, widget.set_margin_bottom,
                       widget.set_margin_start, widget.set_margin_end):
            setter(value)

    # ---- theme, fit and drawing ---------------------------------------------------
    def refresh_theme(self):
        palette = load_omarchy_palette()
        if palette != self.palette:
            self.css.load_from_string(build_css(palette))
            self.palette = palette
            self.log.event('theme', palette=palette)
        return GLib.SOURCE_CONTINUE

    def current_monitor(self):
        display = self.window.get_display()
        surface = self.window.get_surface()
        monitor = display.get_monitor_at_surface(surface) if surface else None
        if monitor is None:
            monitors = display.get_monitors()
            monitor = monitors.get_item(0) if monitors.get_n_items() else None
        return monitor

    def usable_area(self):
        if self.args.fit_limit:
            return self.args.fit_limit
        monitor = self.monitor_provider()
        if monitor is None:
            return (1280 - SCREEN_ALLOWANCE[0], 720 - SCREEN_ALLOWANCE[1])
        geometry = monitor.get_geometry()  # logical pixels; scale already applied by GDK
        return (geometry.width - SCREEN_ALLOWANCE[0], geometry.height - SCREEN_ALLOWANCE[1])

    def on_realize(self, window):
        self.monitor_watch.watch(window.get_surface(), window.get_display().get_monitors())
        self.refit_for_monitor()

    def refit_for_monitor(self):
        """Monitor entered/left, changed geometry or scale, or was (un)plugged."""
        self.monitor_watch.track(self.monitor_provider())
        if self.usable_area() != self.fit_usable:
            self.apply_fit()

    def apply_fit(self):
        width, height = self.fit_usable = self.usable_area()
        self.fit = fit_board(self.game.grid_cells, width, height, *self.chrome, zoom=self.zoom)
        frame = self.fit.frame_pixels
        board, scroller = self.widgets['playing-board'], self.widgets['board-scroller']
        board.set_content_width(frame)
        board.set_content_height(frame)
        scroller.set_max_content_width(max(1, width - self.chrome[0]))
        scroller.set_max_content_height(max(1, height - self.chrome[1]))
        board.queue_draw()
        self.refresh_labels()
        self.measure_chrome_after_layout()
        GLib.timeout_add(100, self.align_menu_with_board)
        self.log.event('fit', cells=self.fit.cells, cell_pixels=self.fit.cell_pixels,
                       zoom=self.zoom, limited=self.fit.limited, scroll=self.fit.scroll_fallback,
                       usable=[width, height], chrome=list(self.chrome))

    def measure_chrome_after_layout(self):
        """A refit can rewrap the footer (e.g. 'reduced to fit screen'), so measure again
        once GTK has laid it out; a burst of refits waits for a single measurement."""
        clock = self.window.get_frame_clock()
        if clock is None or self.chrome_measure is not None:
            return  # not realized yet: the map handler measures

        def after_paint(clock):
            self.cancel_chrome_measure()
            self.measure_chrome()
        self.chrome_measure = (clock, clock.connect('after-paint', after_paint))

    def cancel_chrome_measure(self):
        if self.chrome_measure is not None:
            clock, handler = self.chrome_measure
            clock.disconnect(handler)
            self.chrome_measure = None

    def measured_chrome(self):
        content, scroller = self.widgets['content'], self.widgets['board-scroller']
        if scroller.get_width() <= 0:
            return None
        footer = sum(self.widgets[name].get_height() + content.get_spacing()
                     for name in ('board-info', 'movement-status'))
        return (self.window.get_width() - content.get_width(),
                self.window.get_height() - content.get_height() + footer)

    def measure_chrome(self):
        """Replace the chrome with the real header/footer size and refit if it changed.

        Width: only the content margins; a header wider than the board is centring slack.
        Height: header and margins plus the footer rows, not space left below them while
        the window is still at its previous size. So a stable layout re-measures the same.
        """
        measured = self.measured_chrome()
        if measured is not None and measured != self.chrome and all(0 < value < 600 for value in measured):
            self.chrome = measured
            self.apply_fit()
        return GLib.SOURCE_REMOVE

    def draw(self, _area, cr, width, height):
        draw_board(cr, self.game, self.appearance, self.fit.cell_pixels,
                   board_layout(self.fit, width, height))

    def keep_head_visible(self):
        if not self.fit.scroll_fallback:
            return
        scroller = self.widgets['board-scroller']
        cell = self.fit.cell_pixels
        for adjustment, coordinate in zip((scroller.get_hadjustment(), scroller.get_vadjustment()),
                                          self.game.snake[0]):
            adjustment.set_value(scroll_to_keep_visible(
                adjustment.get_value(), adjustment.get_page_size(), adjustment.get_upper(),
                BORDER_PIXELS + coordinate * cell, cell))

    def align_menu_with_board(self):
        menu, board = self.widgets['main-menu'], self.widgets['playing-board']
        menu_ok, menu_bounds = menu.compute_bounds(self.window)
        board_ok, board_bounds = board.compute_bounds(self.window)
        if menu_ok and board_ok:
            frame_x = board_bounds.get_x() + board_layout(self.fit, board.get_width(), board.get_height())[0]
            adjustment = round(frame_x - menu_bounds.get_x())
            menu.set_margin_start(max(0, menu.get_margin_start() + adjustment))
        return GLib.SOURCE_REMOVE

    # ---- state presentation -------------------------------------------------------
    @property
    def best(self):
        return self.best_scores.get(self.game.difficulty)

    def refresh_labels(self):
        game, fit = self.game, self.fit
        self.widgets['hud'].set_label(hud_text(game, self.best))
        self.widgets['movement-status'].set_label(
            status_text(game, self.session.paused, self.session.manually_paused))
        note = ' · scrolls to fit screen' if fit.scroll_fallback else (
            ' · reduced to fit screen' if fit.limited else '')
        self.widgets['board-info'].set_label(
            f'{game.difficulty}  ·  {game.grid_cells} × {game.grid_cells} cells  ·  '
            f'{fit.cell_pixels} px each ({ZOOM_LABELS[self.zoom]}{note})  ·  '
            f'{fit.board_pixels} × {fit.board_pixels} playing area')
        self.widgets['pause-detail'].set_label(
            'The board and green-dot timer are frozen.\nPress Esc or Resume to continue.')
        self.widgets['game-over-detail'].set_label(
            f'{(game.game_over_reason or "").capitalize()}\n{hud_text(game, self.best)}')
        self.widgets['victory-detail'].set_label(
            f'Board complete — every cell filled!\n{hud_text(game, self.best)}')

    def visible_modal(self):
        if self.widgets['difficulty-overlay'].get_visible():
            return 'difficulty-overlay'
        for name in ('game-over-overlay', 'victory-overlay', 'pause-overlay'):
            if self.widgets[name].get_visible():
                return name
        return None

    def modal_buttons(self):
        modal = self.visible_modal()
        if modal == 'difficulty-overlay':
            if self.chooser.page == 'details':
                return list(self.details_buttons)
            return list(self.difficulty_buttons.values())
        return list(self.card_buttons.get(modal, []))

    def update_overlays(self):
        reasons, game = self.session.reasons, self.game
        chooser = 'difficulty' in reasons
        if chooser and self.chooser.page is None:
            self.chooser.open()
        elif not chooser:
            self.chooser.close()
        details = self.chooser.page == 'details'
        self.widgets['difficulty-choices-page'].set_visible(chooser and not details)
        self.widgets['difficulty-details-page'].set_visible(chooser and details)
        if details:
            self.widgets['difficulty-details-title'].set_label(self.chooser.selected)
            self.widgets['difficulty-details-text'].set_label(DIFFICULTY_DETAILS[self.chooser.selected])
        self.widgets['difficulty-overlay'].set_visible(chooser)
        self.widgets['game-over-overlay'].set_visible(not chooser and game.game_over)
        self.widgets['victory-overlay'].set_visible(not chooser and game.won)
        self.widgets['pause-overlay'].set_visible(
            not chooser and not game.finished and 'manual' in reasons)
        modal = self.visible_modal()
        # Modal: header and board are neither focusable nor clickable behind the card.
        self.widgets['main-menu'].set_sensitive(modal is None)
        self.widgets['content'].set_can_target(modal is None)
        self.widgets['content'].set_can_focus(modal is None)
        self.widgets['menu-pause'].set_sensitive(not game.finished)
        if modal and not self.modal_visible:
            self.focus_before_modal = self.window.get_focus()
        if modal:
            buttons = self.modal_buttons()
            if self.window.get_focus() not in buttons:
                preferred = buttons[0]
                if modal == 'difficulty-overlay' and details:
                    preferred = self.widgets['difficulty-start']
                elif modal == 'difficulty-overlay':
                    preferred = self.difficulty_buttons[self.chooser.selected or game.difficulty]
                preferred.grab_focus()
        elif self.modal_visible:
            previous = self.focus_before_modal
            if previous is None or not previous.get_mapped() or not previous.grab_focus():
                self.widgets['playing-board'].grab_focus()
            self.focus_before_modal = None
        self.modal_visible = modal is not None
        self.refresh_labels()

    # ---- events -------------------------------------------------------------------
    def on_session(self, event, session):
        game = session.game
        self.audio.on_event(event, session)
        if event == 'step':
            self.widgets['playing-board'].queue_draw()
            self.refresh_labels()
            self.keep_head_visible()
            self.log.debug('movement', tick=game.ticks, head=game.snake[0], segments=game.snake,
                           direction=game.direction)
        elif event == 'finished':
            self.save_best()
            self.log.event('finished', state=game.state, reason=game.game_over_reason,
                           score=game.score, length=len(game.snake), best=self.best)
            self.widgets['playing-board'].queue_draw()
            self.update_overlays()
        elif event == 'pause_changed':
            self.log.event('pause', reasons=sorted(session.reasons))
            self.update_overlays()
        elif event == 'new_game':
            self.log.event('new_game', difficulty=game.difficulty, length=len(game.snake))

    def on_key(self, _controller, keyval, _keycode, _state):
        key = Gdk.keyval_name(keyval)
        popover = self.widgets['main-popover']
        if self.chooser.key_pressed(key):
            return True  # Enter/Space still held from the previous page: no repeat-through
        if key == 'Escape':
            action = escape_action(self.chooser.page is not None, popover.get_visible(),
                                   self.game.finished, chooser_details=self.chooser.page == 'details')
            if action == 'chooser-back':
                self.show_difficulty_choices()
            elif action == 'close-chooser':
                self.cancel_difficulty()
            elif action == 'close-menu':
                popover.popdown()
            elif action == 'toggle-pause':
                self.session.toggle_manual()
            return action != 'none'
        if self.visible_modal() and key in NAVIGATION_KEYS:
            self.move_modal_focus(NAVIGATION_KEYS[key])
            return True
        if key in MovementPreview.DIRECTIONS and not popover.get_visible():
            if self.session.paused or self.game.finished:
                return False
            accepted = self.session.steer(key)
            self.log.event('control', key=key, accepted=accepted, queued=list(self.game.queued_turns))
            return True
        return False

    def on_key_released(self, _controller, keyval, _keycode, _state):
        self.chooser.key_released(Gdk.keyval_name(keyval))

    def move_modal_focus(self, delta):
        """Focus trap: Tab, Shift+Tab and arrows cycle only through the open card's buttons."""
        buttons = [b for b in self.modal_buttons() if b.get_sensitive()]
        if not buttons:
            return
        focus = self.window.get_focus()
        index = buttons.index(focus) if focus in buttons else (-1 if delta > 0 else 0)
        buttons[(index + delta) % len(buttons)].grab_focus()

    def on_popover_visible(self, popover, _param):
        if popover.get_visible():
            self.session.pause('menu')
        else:
            self.session.resume('menu')

    def on_active_changed(self, window, _param):
        active = window.is_active()
        self.chooser.release_all()  # a key released in another window is never reported here
        self.session.focus_changed(active)
        if not active and self.focus_check is None:
            self.focus_check = GLib.timeout_add(FOCUS_LOSS_CONFIRM_MS, self.confirm_focus_loss)
        self.log.event('focus', active=active, reasons=sorted(self.session.reasons))

    def confirm_focus_loss(self):
        self.focus_check = None
        self.session.confirm_focus_loss(own_dialog='color' in self.session.reasons)
        return GLib.SOURCE_REMOVE

    def on_color_dialog(self, opened):
        if opened:
            self.session.pause('color')
        else:
            self.session.resume('color')

    def on_color_chosen(self, picker, key, selected):
        message = self.widgets['appearance-message']
        if is_reserved_color(selected):
            picker.show_rgb(self.appearance[key])
            message.set_label(f'That red ({GAME_OVER_HEX.upper()}) is reserved for Game Over. '
                              'Choose another colour.')
            message.set_visible(True)
            if not self.widgets['main-popover'].get_visible():
                self.widgets['main-menu'].popup()
            self.show_options()
            self.log.event('appearance_rejected', setting=key, reserved_color=selected)
            return
        if selected == self.appearance[key]:
            return
        self.appearance[key] = selected
        picker.show_rgb(selected)
        message.set_visible(False)
        self.save_settings()
        self.widgets['playing-board'].queue_draw()
        self.menu_border.queue_draw()
        self.log.event('appearance', **self.appearance)

    def on_zoom_selected(self, dropdown, _param):
        zoom = list(ZOOM_LEVELS)[dropdown.get_selected()]
        if zoom != self.zoom:
            self.zoom = zoom
            self.save_settings()
            self.apply_fit()

    def on_audio_switch(self, switch, _param, key):
        self.audio.update(self.session, **{key: switch.get_active()})
        self.save_settings()
        self.log.event('audio_settings', **self.audio.settings)

    def on_volume_changed(self, scale):
        volume = round(scale.get_value()) / 100
        if volume != self.audio.settings['master_volume']:
            self.audio.update(self.session, master_volume=volume)
            self.save_settings()
            self.log.event('audio_settings', **self.audio.settings)

    def save_settings(self):
        self.store.save_settings({**self.appearance, 'zoom': self.zoom}, audio=self.audio.settings)

    def show_options(self):
        self.widgets['main-menu-panel'].set_visible(False)
        self.widgets['options-panel'].set_visible(True)
        self.widgets['border-color'].grab_focus()

    def options_back(self, *_args):
        self.show_main_menu()
        self.widgets['menu-options'].grab_focus()

    def show_main_menu(self, *_args):
        self.widgets['options-panel'].set_visible(False)
        self.widgets['main-menu-panel'].set_visible(True)

    def manual_pause_from_menu(self):
        self.widgets['main-popover'].popdown()
        self.session.pause('manual')

    def open_new_game(self):
        """Menu, Paused, Game Over, Victory and --show-difficulty all open the choices page."""
        self.widgets['main-popover'].popdown()
        self.chooser.open()
        self.session.pause('difficulty')
        self.update_overlays()

    def choose_difficulty(self, difficulty):
        """Preview only: the current run, score and pause reasons are untouched."""
        self.chooser.choose(difficulty)
        self.update_overlays()

    def show_difficulty_choices(self):
        self.chooser.back()
        self.update_overlays()

    def start_selected(self):
        difficulty = self.chooser.start()
        if difficulty is not None:
            self.start_game(difficulty)

    def cancel_difficulty(self):
        self.chooser.close()
        self.session.resume('difficulty')
        self.update_overlays()

    def start_game(self, difficulty):
        self.save_best()
        cells_before = self.game.grid_cells
        self.session.start(difficulty)
        if self.game.grid_cells != cells_before or self.fit.cells != self.game.grid_cells:
            self.apply_fit()
        self.update_overlays()
        self.widgets['playing-board'].queue_draw()

    def save_best(self):
        """Shared by finish, New Game and close: records the run and retries an unsaved best."""
        self.best_scores.commit(self.game.difficulty, self.game.score)

    def on_close(self, _window):
        self.save_best()
        self.session.stop()
        self.audio.shutdown()
        self.monitor_watch.close()
        self.cancel_chrome_measure()
        if self.focus_check is not None:
            GLib.source_remove(self.focus_check)
            self.focus_check = None
        if self.theme_timer is not None:
            GLib.source_remove(self.theme_timer)
            self.theme_timer = None
        return False

    def report_geometry(self):
        game, window, board = self.game, self.window, self.widgets['playing-board']
        data = {'title': window.get_title(), 'difficulty': game.difficulty,
                'grid_cells': game.grid_cells, 'cell_pixels': self.fit.cell_pixels,
                'zoom': self.zoom, 'fit_limited': self.fit.limited,
                'scroll_fallback': self.fit.scroll_fallback, 'chrome': list(self.chrome),
                'usable_area': list(self.usable_area()),
                'board_widget': [board.get_width(), board.get_height()],
                'frame_pixels': self.fit.frame_pixels,
                'window': [window.get_width(), window.get_height()], 'mapped': window.get_mapped(),
                'state': game.state, 'pause_reasons': sorted(self.session.reasons),
                'timer_active': self.session.timer is not None,
                'step_interval_ms': game.step_interval_ms, 'score': game.score,
                'length': len(game.snake), 'best': self.best,
                'hud': self.widgets['hud'].get_label(), 'modal': self.visible_modal(),
                'chooser_page': self.chooser.page, 'chooser_selected': self.chooser.selected,
                'appearance': self.appearance, 'palette': self.palette,
                'effective_board_colors': board_colors(game.game_over, self.appearance),
                'green_interval_ms': GREEN_INTERVAL_MS, 'audio': self.audio.settings,
                'music_state': self.audio.music_state}
        if self.args.geometry_report:
            Path(self.args.geometry_report).write_text(json.dumps(data, indent=2, default=list) + '\n')
        self.log.event('geometry', **data)
        return data


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Omarchy Snake — native offline GTK4 Snake.')
    parser.add_argument('--show-difficulty', action='store_true',
                        help='Open the New Game chooser before the first move')
    parser.add_argument('--show-menu', action='store_true', help='Open the dropdown for visual review')
    parser.add_argument('--show-options', action='store_true', help='Open appearance options for visual review')
    parser.add_argument('--geometry-report', type=Path, help='Write a JSON layout/state report')
    parser.add_argument('--verbose', action='store_true', help='Log notable events as JSON lines')
    parser.add_argument('--debug', action='store_true', help='Also log every move with full segments')
    parser.add_argument('--application-id', default=APPLICATION_ID,
                        help='GApplication ID (tests use their own so they never attach to your game)')
    parser.add_argument('--config-dir', type=Path, help='Settings directory (default: XDG config)')
    parser.add_argument('--state-dir', type=Path, help='Best-score directory (default: XDG state)')
    parser.add_argument('--fit-limit', type=lambda text: tuple(int(v) for v in text.lower().split('x')),
                        metavar='WxH', help='Pretend the usable screen area is WxH logical px (testing)')
    return parser.parse_args(argv)


def main(argv=None, game_factory=None, on_ready=None):
    """Run the app. `game_factory` and `on_ready` let native checks inject fixtures."""
    args = parse_args(argv)
    log = GameLog('debug' if args.debug else 'verbose' if args.verbose else 'quiet')
    app = Gtk.Application(application_id=args.application_id)
    windows = []

    def activate(application):
        if windows:
            # Second launch: GApplication routes it here; focus the running game instead.
            windows[0].window.present()
            log.event('refocus_existing_window')
            if on_ready:
                on_ready(windows[0], 'reactivated')
            return
        game = game_factory() if game_factory else MovementPreview()
        store = PreferenceStore(args.config_dir, args.state_dir, log=log)
        controller = SnakeWindow(application, args, game, store, log)
        windows.append(controller)
        if args.show_difficulty:
            controller.open_new_game()  # chooser is up before any movement
        controller.session.begin()
        controller.update_overlays()
        controller.window.present()
        if args.show_menu or args.show_options:
            def open_menu():
                controller.widgets['main-menu'].popup()
                if args.show_options:
                    controller.show_options()
                return GLib.SOURCE_REMOVE
            GLib.timeout_add(400, open_menu)
        GLib.timeout_add(800, lambda: (controller.report_geometry(), GLib.SOURCE_REMOVE)[1])
        if on_ready:
            on_ready(controller, 'activated')

    app.connect('activate', activate)
    return app.run([])
