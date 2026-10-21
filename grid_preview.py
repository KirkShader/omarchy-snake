"""Native offline Omarchy Snake prototype; no network or installation."""
import argparse
import json
import os
import random
import re
import tomllib
from math import atan2
from pathlib import Path
from time import monotonic

GRID_CELLS = 64
CELL_PIXELS = 16
BOARD_PIXELS = GRID_CELLS * CELL_PIXELS
DIFFICULTIES = {'Easy': 64, 'Normal': 48, 'Hard': 32}
STEP_INTERVAL_MS = 150
HARD_SPEEDUP_MS = 2.3
MIN_STEP_INTERVAL_MS = 1  # Technical floor: never schedule a zero-delay busy loop.
GREEN_INTERVAL_MS = 30000
BORDER_PIXELS = 6
TEXT_RGB = (220, 225, 230)  # Default off-white frame; surrounding text follows the theme.
GAME_OVER_RGB = (255, 51, 51)
GAME_OVER_HEX = '#' + ''.join(f'{channel:02x}' for channel in GAME_OVER_RGB)


def board_colors(game_over, appearance):
    """Warning colours are temporary overrides, not changes to player settings."""
    if game_over:
        return {'border_rgb': GAME_OVER_RGB, 'grid_rgb': GAME_OVER_RGB}
    return dict(appearance)


def is_reserved_color(color):
    return tuple(color) == GAME_OVER_RGB


def load_omarchy_palette(paths=None):
    """Read the user's active Omarchy colours without altering their theme."""
    palette = {'background': '#050505', 'foreground': '#dce1e6',
               'accent': '#dce1e6', 'selection': '#26332b'}
    if paths is None:
        state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
        config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        paths = [state / 'omarchy/current/theme/colors.toml',
                 config / 'omarchy/current/theme/colors.toml']
    for path in paths:
        try:
            colors = tomllib.loads(Path(path).read_text())
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            continue
        for key in palette:
            value = colors.get(key)
            if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                palette[key] = value.lower()
        break
    return palette


def draw_board_border(cr, width, height, color=TEXT_RGB):
    """Opaque outer coloured rim, shading inward to the near-black board."""
    cr.save()
    cr.set_source_rgb(5 / 255, 5 / 255, 5 / 255)
    cr.paint()
    cr.set_line_width(1)
    for inset in range(BORDER_PIXELS):
        fade = max(0, inset - 1) / (BORDER_PIXELS - 2)
        ring_color = [round(channel + (5 - channel) * fade) / 255 for channel in color]
        cr.set_source_rgb(*ring_color)
        cr.rectangle(inset + 0.5, inset + 0.5,
                     width - 2 * inset - 1, height - 2 * inset - 1)
        cr.stroke()
    cr.restore()


def segment_color(index, length):
    """Keep a clear head and fade only the final three body squares."""
    if index == 0:
        return (0.65, 0.91, 0.50)
    body = (0.36, 0.68, 0.37)
    distance_from_tip = length - 1 - index
    if distance_from_tip >= 2:
        return body
    strength = 0.55 if distance_from_tip == 1 else 0.10
    return tuple(0.02 + (channel - 0.02) * strength for channel in body)


class MovementPreview:
    """Display-independent Snake rules with an injectable random generator."""

    DIRECTIONS = {'Up': (0, -1), 'Down': (0, 1),
                  'Left': (-1, 0), 'Right': (1, 0)}

    def __init__(self, rng=None, difficulty='Easy'):
        self.rng = rng if rng is not None else random.Random()
        self.reset(difficulty)

    @property
    def board_pixels(self):
        return self.grid_cells * CELL_PIXELS

    def reset(self, difficulty=None):
        if difficulty is not None:
            if difficulty not in DIFFICULTIES:
                raise ValueError('Unknown difficulty')
            self.difficulty = difficulty
        self.grid_cells = DIFFICULTIES[self.difficulty]
        self.snake = [(7, 8), (6, 8), (5, 8), (4, 8), (3, 8), (2, 8)]
        self.ticks = 0
        self.direction = 'Right'
        self.pending_direction = None
        self.score = 0
        self.game_over = False
        self.game_over_reason = None
        self.foods = set()
        self.green_dot = None
        self.green_elapsed_ms = 0
        self.refill_foods()

    @property
    def orange_dot_count(self):
        return 10 if self.difficulty == 'Hard' else 5

    @property
    def step_interval_ms(self):
        if self.difficulty != 'Hard':
            return STEP_INTERVAL_MS
        return max(MIN_STEP_INTERVAL_MS, round(STEP_INTERVAL_MS - self.score * HARD_SPEEDUP_MS, 1))

    def refill_foods(self):
        while len(self.foods) < self.orange_dot_count:
            excluded = self.foods | ({self.green_dot} if self.green_dot else set())
            cell = self.empty_cell(excluded)
            if cell is None:
                break
            self.foods.add(cell)

    def empty_cell(self, excluded=()):
        occupied = set(self.snake) | set(excluded)
        free = [(x, y) for y in range(self.grid_cells) for x in range(self.grid_cells)
                if (x, y) not in occupied]
        return self.rng.choice(free) if free else None

    def request_turn(self, key):
        if self.game_over or key not in self.DIRECTIONS or self.pending_direction is not None:
            return False
        dx, dy = self.DIRECTIONS[self.direction]
        requested = self.DIRECTIONS[key]
        if requested == (dx, dy) or requested == (-dx, -dy):
            return False
        self.pending_direction = key
        return True

    def step(self, elapsed_ms=None):
        if self.game_over:
            return
        if elapsed_ms is None:
            elapsed_ms = self.step_interval_ms
        if self.pending_direction is not None:
            self.direction = self.pending_direction
            self.pending_direction = None
        x, y = self.snake[0]
        dx, dy = self.DIRECTIONS[self.direction]
        head = (x + dx, y + dy)
        if self.difficulty == 'Hard' and not all(0 <= cell < self.grid_cells for cell in head):
            self.game_over = True
            self.game_over_reason = 'wall collision'
            return
        head = (head[0] % self.grid_cells, head[1] % self.grid_cells)
        growing = head in self.foods
        shrinking = head == self.green_dot and len(self.snake) >= 6
        remaining_body = self.snake if growing else self.snake[:-1]
        if (self.difficulty == 'Hard' or len(self.snake) >= 10) and head in remaining_body:
            self.game_over = True
            self.game_over_reason = 'self collision'
            return
        self.snake = [head] + (self.snake if growing else self.snake[:-1])
        if growing:
            self.score += 1
            self.foods.remove(head)
            self.refill_foods()
        if shrinking:
            self.snake = self.snake[:-2]
            self.green_dot = None
            self.green_elapsed_ms = 0
        self.ticks += 1
        if len(self.snake) < 6:
            self.green_dot = None
            self.green_elapsed_ms = 0
        elif self.green_dot is None:
            if not shrinking:
                self.green_elapsed_ms += max(0, elapsed_ms)
            if self.green_elapsed_ms >= GREEN_INTERVAL_MS:
                self.green_dot = self.empty_cell(self.foods)
                self.green_elapsed_ms = 0


def main():
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, Gio, GLib, Gtk

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry-report', type=Path)
    parser.add_argument('--show-menu', action='store_true', help='Open the dropdown for visual review')
    parser.add_argument('--show-difficulty', action='store_true', help='Open the New Game chooser for visual review')
    parser.add_argument('--show-options', action='store_true', help='Open appearance options for visual review')
    args = parser.parse_args()
    app = Gtk.Application(application_id='local.omarchy.snake.preview')

    def activate(application):
        motion = MovementPreview()
        appearance = {'border_rgb': TEXT_RGB, 'grid_rgb': (255, 255, 255)}
        restoring_color = False
        window = Gtk.ApplicationWindow(application=application)
        window.add_css_class('snake-window')
        window.set_opacity(1.0)
        css = Gtk.CssProvider()
        current_palette = None

        def refresh_theme():
            nonlocal current_palette
            palette = load_omarchy_palette()
            if palette != current_palette:
                css.load_from_string(f'''
                    .snake-window, .snake-window headerbar {{
                        background-color: {palette['background']};
                        background-image: none;
                        color: {palette['foreground']};
                        opacity: 1;
                    }}
                    .snake-window label, .snake-window button,
                    .snake-menu-popover label, .snake-menu-popover button {{
                        color: {palette['foreground']};
                    }}
                    .snake-window .snake-title {{ font-weight: bold; font-size: 18px; }}
                    .snake-window headerbar button, .snake-difficulty-card button {{
                        background-color: {palette['background']};
                        background-image: none;
                    }}
                    .snake-window headerbar button:hover,
                    .snake-window headerbar button:checked,
                    .snake-difficulty-card button:hover {{
                        background-color: {palette['selection']};
                    }}
                    .snake-menu-popover > contents {{
                        background: transparent;
                        border: none;
                        border-radius: 0;
                        box-shadow: none;
                        padding: 0;
                    }}
                    .snake-menu-panel {{ background-color: {palette['background']}; }}
                    .snake-menu-panel button {{
                        background: {palette['background']};
                        border: none;
                        border-radius: 0;
                        box-shadow: none;
                        padding: 8px 12px;
                    }}
                    .snake-menu-panel button:hover {{ background: {palette['selection']}; }}
                    .snake-menu-panel .snake-appearance-warning {{ color: {GAME_OVER_HEX}; }}
                    .snake-modal-shade {{ background-color: rgba(0, 0, 0, 0.65); }}
                    .snake-difficulty-card {{
                        background-color: {palette['background']};
                        color: {palette['foreground']};
                        border: 1px solid {palette['accent']};
                        padding: 22px;
                    }}
                    .snake-game-over-card {{
                        background-color: #050505;
                        border: 2px solid {GAME_OVER_HEX};
                        padding: 30px 40px;
                    }}
                    .snake-window .snake-game-over-title {{
                        color: {GAME_OVER_HEX};
                        font-size: 42px;
                        font-weight: bold;
                    }}
                    .snake-game-over button {{
                        background: #050505;
                        color: {palette['foreground']};
                        border: 1px solid {GAME_OVER_HEX};
                        padding: 10px 22px;
                    }}
                    .snake-game-over button:hover {{ background: {palette['selection']}; }}
                ''')
                current_palette = palette
                print(json.dumps({'event': 'theme', 'palette': palette}), flush=True)
            return GLib.SOURCE_CONTINUE

        refresh_theme()
        Gtk.StyleContext.add_provider_for_display(
            window.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window.set_title('Omarchy Snake')
        window.set_resizable(False)
        window.set_default_size(BOARD_PIXELS + 32 + 2 * BORDER_PIXELS,
                                BOARD_PIXELS + 108 + 2 * BORDER_PIXELS)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for setter in (box.set_margin_top, box.set_margin_bottom,
                       box.set_margin_start, box.set_margin_end):
            setter(16)
        header = Gtk.HeaderBar()
        title = Gtk.Label(label='Omarchy Snake')
        title.add_css_class('snake-title')
        header.set_title_widget(title)
        menu = Gtk.MenuButton(label='Menu')
        menu.set_name('main-menu')
        popover = Gtk.Popover()
        popover.set_has_arrow(False)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_halign(Gtk.Align.START)
        popover.add_css_class('snake-menu-popover')
        menu_frame = Gtk.Overlay()
        menu_border = Gtk.DrawingArea()
        menu_border.set_content_width(180)
        menu_border.set_content_height(144)
        menu_border.set_draw_func(lambda _widget, cr, w, h:
                                  draw_board_border(cr, w, h, color=appearance['border_rgb']))
        menu_frame.set_child(menu_border)
        menu_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        menu_panel.set_name('main-menu-panel')
        menu_panel.add_css_class('snake-menu-panel')
        for setter in (menu_panel.set_margin_top, menu_panel.set_margin_bottom,
                       menu_panel.set_margin_start, menu_panel.set_margin_end):
            setter(BORDER_PIXELS)
        menu_buttons = []
        for label, action_name in [('New Game', 'win.new-game'),
                                   ('Options', 'win.options'), ('Quit', 'win.quit')]:
            button = Gtk.Button(label=label)
            button.set_hexpand(True)
            button.set_vexpand(True)
            if action_name:
                button.set_action_name(action_name)
            else:
                button.set_sensitive(False)
                button.set_tooltip_text('Settings will be added in a later step')
                button.set_opacity(0.45)
            menu_panel.append(button)
            menu_buttons.append(button)
        menu_frame.add_overlay(menu_panel)
        menu_frame.set_measure_overlay(menu_panel, True)
        options_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        options_panel.set_name('options-panel')
        options_panel.add_css_class('snake-menu-panel')
        for setter in (options_panel.set_margin_top, options_panel.set_margin_bottom,
                       options_panel.set_margin_start, options_panel.set_margin_end):
            setter(BORDER_PIXELS)
        options_panel.append(Gtk.Label(label='Appearance'))
        appearance_message = Gtk.Label()
        appearance_message.set_name('appearance-message')
        appearance_message.add_css_class('snake-appearance-warning')
        appearance_message.set_wrap(True)
        appearance_message.set_max_width_chars(26)
        appearance_message.set_margin_start(12)
        appearance_message.set_margin_end(12)
        appearance_message.set_visible(False)
        options_panel.append(appearance_message)

        def appearance_changed(picker, _property, key):
            nonlocal restoring_color
            if restoring_color:
                return
            rgba = picker.get_rgba()
            selected = tuple(round(channel * 255) for channel in (rgba.red, rgba.green, rgba.blue))
            if is_reserved_color(selected):
                restoring_color = True
                try:
                    previous = Gdk.RGBA()
                    previous.parse('#' + ''.join(f'{channel:02x}' for channel in appearance[key]))
                    picker.set_rgba(previous)
                finally:
                    restoring_color = False
                appearance_message.set_label('That red (#FF3333) is reserved for Game Over. Choose another colour.')
                appearance_message.set_visible(True)
                if not popover.get_visible():
                    menu.popup()
                menu_panel.set_visible(False)
                options_panel.set_visible(True)
                print(json.dumps({'event': 'appearance_rejected', 'setting': key,
                                  'reserved_color': selected}), flush=True)
                return
            # GObject can deliver the restore notification after this handler returns.
            # A no-op restore must not clear the reserved-colour explanation.
            if selected == appearance[key]:
                return
            appearance[key] = selected
            appearance_message.set_visible(False)
            board.queue_draw()
            border.queue_draw()
            menu_border.queue_draw()
            print(json.dumps({'event': 'appearance', **appearance}), flush=True)

        for label, key, name in [('Border colour', 'border_rgb', 'border-color'),
                                 ('Grid-line colour', 'grid_rgb', 'grid-color')]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_margin_start(12)
            row.set_margin_end(12)
            caption = Gtk.Label(label=label, xalign=0)
            caption.set_hexpand(True)
            row.append(caption)
            dialog = Gtk.ColorDialog()
            dialog.set_title(label)
            dialog.set_with_alpha(False)
            picker = Gtk.ColorDialogButton(dialog=dialog)
            picker.set_name(name)
            rgba = Gdk.RGBA()
            rgba.parse('#' + ''.join(f'{channel:02x}' for channel in appearance[key]))
            picker.set_rgba(rgba)
            picker.connect('notify::rgba', appearance_changed, key)
            row.append(picker)
            options_panel.append(row)
        back_button = Gtk.Button(label='Back')
        back_button.set_name('options-back')
        def show_main_menu(*_args):
            options_panel.set_visible(False)
            menu_panel.set_visible(True)
        back_button.connect('clicked', show_main_menu)
        options_panel.append(back_button)
        options_panel.set_visible(False)
        menu_frame.add_overlay(options_panel)
        menu_frame.set_measure_overlay(options_panel, True)
        popover.connect('closed', show_main_menu)
        popover.set_child(menu_frame)
        menu.set_popover(popover)

        def show_options(_action, _parameter):
            menu_panel.set_visible(False)
            options_panel.set_visible(True)
        options_action = Gio.SimpleAction.new('options', None)
        options_action.connect('activate', show_options)
        window.add_action(options_action)

        def new_game(_action, _parameter):
            game_over_layer.set_visible(False)
            difficulty_layer.set_visible(True)
            popover.popdown()
            difficulty_buttons[motion.difficulty].grab_focus()

        def movement_status():
            edges = 'Solid walls' if motion.difficulty == 'Hard' else 'Edge wrap'
            return (f'Arrow keys to steer  ·  1 cell / {motion.step_interval_ms / 1000:g} sec  ·  '
                    f'Moving {motion.direction.lower()}  ·  {edges}')

        def start_game(difficulty):
            nonlocal timer_id, last_step_time
            if timer_id is not None:
                GLib.source_remove(timer_id)
            motion.reset(difficulty)
            last_step_time = monotonic()
            timer_id = GLib.timeout_add(round(motion.step_interval_ms), advance)
            status.set_label(movement_status())
            score_label.set_label('Score  0')
            difficulty_layer.set_visible(False)
            game_over_layer.set_visible(False)
            popover.popdown()
            pixels = motion.board_pixels
            board.set_content_width(pixels)
            board.set_content_height(pixels)
            board.set_size_request(pixels, pixels)
            border.set_content_width(pixels + 2 * BORDER_PIXELS)
            border.set_content_height(pixels + 2 * BORDER_PIXELS)
            info_label.set_label(f'{difficulty}  ·  {motion.grid_cells} × {motion.grid_cells} cells  ·  '
                                f'{CELL_PIXELS} px each  ·  {pixels} × {pixels} playing area')
            window.set_default_size(pixels + 32 + 2 * BORDER_PIXELS,
                                    pixels + 108 + 2 * BORDER_PIXELS)
            GLib.timeout_add(100, align_menu_with_board)
            board.queue_draw()
            border.queue_draw()
            print(json.dumps({'event': 'new_game', 'head': motion.snake[0],
                              'length': len(motion.snake), 'ticks': motion.ticks,
                              'difficulty': difficulty, 'board_pixels': pixels}), flush=True)

        new_game_action = Gio.SimpleAction.new('new-game', None)
        new_game_action.connect('activate', new_game)
        window.add_action(new_game_action)
        quit_action = Gio.SimpleAction.new('quit', None)
        quit_action.connect('activate', lambda _action, _parameter: window.close())
        window.add_action(quit_action)
        header.pack_start(menu)
        score_label = Gtk.Label(label='Score  0')
        header.pack_end(score_label)
        window.set_titlebar(header)
        board = Gtk.DrawingArea()
        board.set_name('playing-board')
        board.set_content_width(BOARD_PIXELS)
        board.set_content_height(BOARD_PIXELS)
        board.set_size_request(BOARD_PIXELS, BOARD_PIXELS)
        board.set_halign(Gtk.Align.CENTER)
        board.set_valign(Gtk.Align.CENTER)
        board.set_hexpand(False)
        board.set_vexpand(False)

        def draw(_widget, cr, _width, _height):
            cr.set_source_rgb(0.02, 0.02, 0.02)
            cr.paint()
            grid_color = board_colors(motion.game_over, appearance)['grid_rgb']
            cr.set_source_rgba(*(channel / 255 for channel in grid_color),
                               1.0 if motion.game_over else 0.35)
            cr.set_line_width(1)
            for n in range(1, motion.grid_cells):
                coordinate = n * CELL_PIXELS + 0.5
                cr.move_to(coordinate, 0)
                cr.line_to(coordinate, motion.board_pixels)
                cr.move_to(0, coordinate)
                cr.line_to(motion.board_pixels, coordinate)
            cr.stroke()
            # Tail shading follows the final three squares at any length.
            for index in range(len(motion.snake) - 1, -1, -1):
                x, y = motion.snake[index]
                cr.set_source_rgb(*segment_color(index, len(motion.snake)))
                cr.rectangle(x * CELL_PIXELS + 2, y * CELL_PIXELS + 2,
                             CELL_PIXELS - 4, CELL_PIXELS - 4)
                cr.fill()
                if index == 0:
                    # Rotate the centered chevron to match actual movement.
                    cr.save()
                    cr.translate((x + 0.5) * CELL_PIXELS, (y + 0.5) * CELL_PIXELS)
                    dx, dy = motion.DIRECTIONS[motion.direction]
                    cr.rotate(atan2(dy, dx))
                    cr.set_source_rgb(0.055, 0.075, 0.09)
                    cr.set_line_width(1.5)
                    cr.move_to(-2, -3)
                    cr.line_to(2.5, 0)
                    cr.line_to(-2, 3)
                    cr.stroke()
                    cr.restore()
            for dot, color in [(cell, (0.98, 0.69, 0.31)) for cell in motion.foods] + [
                               (motion.green_dot, (0.15, 0.95, 0.35))]:
                if dot is not None:
                    cr.set_source_rgb(*color)
                    cr.arc((dot[0] + 0.5) * CELL_PIXELS,
                           (dot[1] + 0.5) * CELL_PIXELS,
                           CELL_PIXELS * 0.28, 0, 6.283185307179586)
                    cr.fill()

        board.set_draw_func(draw)
        # The frame sits outside the exact-sized playable DrawingArea.
        frame = Gtk.Overlay()
        frame.set_halign(Gtk.Align.CENTER)
        frame.set_valign(Gtk.Align.CENTER)
        border = Gtk.DrawingArea()
        border.set_name('board-border')
        border.set_content_width(BOARD_PIXELS + 2 * BORDER_PIXELS)
        border.set_content_height(BOARD_PIXELS + 2 * BORDER_PIXELS)
        border.set_draw_func(lambda _widget, cr, w, h:
                            draw_board_border(cr, w, h,
                                              color=board_colors(motion.game_over, appearance)['border_rgb']))
        frame.set_child(border)
        frame.add_overlay(board)
        box.append(frame)
        info_label = Gtk.Label(label=f'Easy  ·  {GRID_CELLS} × {GRID_CELLS} cells  ·  '
                               f'{CELL_PIXELS} px each  ·  {BOARD_PIXELS} × {BOARD_PIXELS} playing area')
        info_label.set_wrap(True)
        info_label.set_max_width_chars(60)
        info_label.set_justify(Gtk.Justification.CENTER)
        box.append(info_label)
        status = Gtk.Label(label=movement_status())
        status.set_name('movement-status')
        status.set_wrap(True)
        status.set_max_width_chars(60)
        status.set_justify(Gtk.Justification.CENTER)
        box.append(status)
        root = Gtk.Overlay()
        root.set_child(box)
        difficulty_layer = Gtk.Overlay()
        difficulty_layer.set_name('difficulty-overlay')
        difficulty_layer.add_css_class('snake-modal-shade')
        backdrop = Gtk.Box()
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)
        difficulty_layer.set_child(backdrop)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        card.set_name('difficulty-card')
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.CENTER)
        card.add_css_class('snake-difficulty-card')
        card_title = Gtk.Label(label='New Game — choose difficulty')
        card_title.add_css_class('snake-title')
        card.append(card_title)
        choices = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        difficulty_buttons = {}
        for difficulty, cells in DIFFICULTIES.items():
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            button = Gtk.Button(label=difficulty)
            button.set_name('difficulty-' + difficulty.lower())
            button.connect('clicked', lambda _button, choice=difficulty: start_game(choice))
            column.append(button)
            column.append(Gtk.Label(label=f'{cells * CELL_PIXELS} × {cells * CELL_PIXELS}'))
            choices.append(column)
            difficulty_buttons[difficulty] = button
        card.append(choices)
        cancel_button = Gtk.Button(label='Cancel')
        cancel_button.set_name('difficulty-cancel')
        def cancel_difficulty(_button):
            nonlocal last_step_time
            difficulty_layer.set_visible(False)
            game_over_layer.set_visible(motion.game_over)
            if motion.game_over:
                game_over_button.grab_focus()
            last_step_time = monotonic()
        cancel_button.connect('clicked', cancel_difficulty)
        card.append(cancel_button)
        difficulty_layer.add_overlay(card)
        difficulty_layer.set_visible(False)
        root.add_overlay(difficulty_layer)
        game_over_layer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        game_over_layer.set_name('game-over-overlay')
        game_over_layer.add_css_class('snake-game-over')
        game_over_layer.set_halign(Gtk.Align.CENTER)
        game_over_layer.set_valign(Gtk.Align.CENTER)
        game_over_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        game_over_box.add_css_class('snake-game-over-card')
        game_over_title = Gtk.Label(label='Game Over')
        game_over_title.set_name('game-over-title')
        game_over_title.add_css_class('snake-game-over-title')
        game_over_box.append(game_over_title)
        game_over_layer.append(game_over_box)
        game_over_button = Gtk.Button(label='New Game')
        game_over_button.set_name('game-over-new-game')
        game_over_button.set_size_request(190, 46)
        game_over_button.set_halign(Gtk.Align.CENTER)
        game_over_button.connect('clicked', lambda _button: new_game_action.activate(None))
        game_over_layer.append(game_over_button)
        game_over_layer.set_visible(False)
        root.add_overlay(game_over_layer)
        window.set_child(root)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def key_pressed(_controller, keyval, _keycode, _modifiers):
            if motion.game_over or difficulty_layer.get_visible() or popover.get_visible():
                return False
            key = Gdk.keyval_name(keyval)
            if key not in motion.DIRECTIONS:
                return False
            accepted = motion.request_turn(key)
            print(json.dumps({'event': 'control', 'key': key, 'accepted': accepted,
                              'direction': motion.direction}), flush=True)
            return True

        keys.connect('key-pressed', key_pressed)
        window.add_controller(keys)

        last_step_time = monotonic()

        def advance():
            nonlocal timer_id, last_step_time
            now = monotonic()
            elapsed_ms = (now - last_step_time) * 1000
            last_step_time = now
            if motion.game_over:
                timer_id = None
                return GLib.SOURCE_REMOVE
            if difficulty_layer.get_visible():
                return GLib.SOURCE_CONTINUE
            previous_interval = motion.step_interval_ms
            previous_head = motion.snake[0]
            previous_direction = motion.direction
            previous_effects = (motion.score, len(motion.snake), motion.green_dot)
            motion.step(elapsed_ms=elapsed_ms)
            board.queue_draw()
            score_label.set_label(f'Score  {motion.score}')
            if motion.game_over:
                status.set_label(f'Game over — {motion.game_over_reason}. Choose New Game to restart.')
                border.queue_draw()
                game_over_layer.set_visible(True)
                game_over_button.grab_focus()
            else:
                status.set_label(movement_status())
            if motion.game_over or previous_effects != (motion.score, len(motion.snake), motion.green_dot):
                print(json.dumps({'event': 'mechanics', 'score': motion.score,
                                  'length': len(motion.snake), 'foods': sorted(motion.foods),
                                  'green_dot': motion.green_dot, 'game_over': motion.game_over,
                                  'game_over_reason': motion.game_over_reason,
                                  'step_interval_ms': motion.step_interval_ms}), flush=True)
            wrapped = any(abs(a - b) > 1 for a, b in zip(motion.snake[0], previous_head))
            if motion.ticks <= 4 or wrapped or motion.direction != previous_direction:
                print(json.dumps({'event': 'movement', 'tick': motion.ticks,
                                  'head': motion.snake[0], 'segments': motion.snake,
                                  'direction': motion.direction,
                                  'interval_ms': elapsed_ms, 'wrapped': wrapped}), flush=True)
            if motion.game_over:
                timer_id = None
                return GLib.SOURCE_REMOVE
            if motion.step_interval_ms != previous_interval:
                timer_id = GLib.timeout_add(round(motion.step_interval_ms), advance)
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        timer_id = GLib.timeout_add(round(motion.step_interval_ms), advance)
        theme_timer_id = GLib.timeout_add_seconds(1, refresh_theme)

        def close_preview(_window):
            if timer_id is not None:
                GLib.source_remove(timer_id)
            GLib.source_remove(theme_timer_id)
            return False

        window.connect('close-request', close_preview)

        def align_menu_with_board():
            menu_located, menu_bounds = menu.compute_bounds(window)
            frame_located, frame_bounds = frame.compute_bounds(window)
            if menu_located and frame_located:
                adjustment = round(frame_bounds.get_x() - menu_bounds.get_x())
                menu.set_margin_start(max(0, menu.get_margin_start() + adjustment))
            return GLib.SOURCE_REMOVE

        def report_geometry():
            data = {'title': window.get_title(), 'grid_cells': motion.grid_cells,
                    'difficulty': motion.difficulty, 'difficulty_chooser_open': difficulty_layer.get_visible(),
                    'cell_pixels': CELL_PIXELS,
                    'board_width': board.get_width(), 'board_height': board.get_height(),
                    'window_width': window.get_width(), 'window_height': window.get_height(),
                    'mapped': window.get_mapped(), 'movement_preview': True,
                    'step_interval_ms': motion.step_interval_ms, 'head': motion.snake[0],
                    'orange_dot_target': motion.orange_dot_count,
                    'edge_wrap': motion.difficulty != 'Hard',
                    'score': motion.score, 'score_label': score_label.get_label(),
                    'snake_length': len(motion.snake), 'foods': sorted(motion.foods),
                    'green_dot': motion.green_dot, 'game_over': motion.game_over,
                    'game_over_reason': motion.game_over_reason,
                    'game_over_panel_visible': game_over_layer.get_visible(),
                    'effective_board_colors': board_colors(motion.game_over, appearance),
                    'header_title': title.get_label(), 'menu_label': menu.get_label(),
                    'menu_items': [button.get_label() for button in menu_buttons],
                    'menu_items_enabled': [button.get_sensitive() for button in menu_buttons],
                    'appearance': appearance, 'options_open': options_panel.get_visible(),
                    'green_interval_ms': GREEN_INTERVAL_MS,
                    'palette': current_palette, 'menu_open': popover.get_visible(),
                    'menu_mapped': popover.get_mapped(),
                    'menu_frame_size': [menu_frame.get_width(), menu_frame.get_height()],
                    'dropdown_border_pixels': BORDER_PIXELS}
            located, bounds = title.compute_bounds(window)
            if located:
                data['title_center_x'] = bounds.get_x() + bounds.get_width() / 2
            for name, widget in [('menu', menu), ('board_border', frame)]:
                located, bounds = widget.compute_bounds(window)
                if located:
                    data[name + '_left_x'] = bounds.get_x()
            if difficulty_layer.get_visible():
                located, bounds = card.compute_bounds(root)
                if located:
                    data['difficulty_card_center'] = [bounds.get_x() + bounds.get_width() / 2,
                                                      bounds.get_y() + bounds.get_height() / 2]
                    data['content_center'] = [root.get_width() / 2, root.get_height() / 2]
            print(json.dumps(data), flush=True)
            if args.geometry_report:
                args.geometry_report.write_text(json.dumps(data, indent=2) + '\n')
            return GLib.SOURCE_REMOVE

        window.present()
        GLib.timeout_add(100, align_menu_with_board)
        if args.show_menu:
            GLib.timeout_add(400, lambda: (menu.popup(), GLib.SOURCE_REMOVE)[1])
        if args.show_difficulty:
            GLib.timeout_add(400, lambda: (new_game_action.activate(None), GLib.SOURCE_REMOVE)[1])
        if args.show_options:
            GLib.timeout_add(400, lambda: (menu.popup(), options_action.activate(None), GLib.SOURCE_REMOVE)[2])
        GLib.timeout_add(800, report_geometry)

    app.connect('activate', activate)
    return app.run([])


if __name__ == '__main__':
    raise SystemExit(main())
