"""Cairo rendering helpers for the board, frame and snake."""
from math import atan2, pi

from .theme import TEXT_RGB, board_colors

BORDER_PIXELS = 6
BOARD_RGB = (5, 5, 5)
ORANGE_RGB = (0.98, 0.69, 0.31)
GREEN_RGB = (0.15, 0.95, 0.35)


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
    """Keep a clear head and fade only the final three body squares; the tip stays visible."""
    if index == 0:
        return (0.65, 0.91, 0.50)
    body = (0.36, 0.68, 0.37)
    distance_from_tip = length - 1 - index
    if distance_from_tip >= 2:
        return body
    strength = 0.70 if distance_from_tip == 1 else 0.42
    return tuple(0.02 + (channel - 0.02) * strength for channel in body)


def draw_board(cr, game, appearance, cell, origin=(0, 0)):
    """Frame plus playable board at a whole-pixel cell size; cells and rules are unchanged."""
    colors = board_colors(game.game_over, appearance)
    frame = game.grid_cells * cell + 2 * BORDER_PIXELS
    board = game.grid_cells * cell
    cr.save()
    cr.set_source_rgb(*(channel / 255 for channel in BOARD_RGB))
    cr.paint()
    cr.translate(*origin)
    cr.save()
    cr.rectangle(0, 0, frame, frame)
    cr.clip()
    draw_board_border(cr, frame, frame, color=colors['border_rgb'])
    cr.restore()
    cr.translate(BORDER_PIXELS, BORDER_PIXELS)
    cr.rectangle(0, 0, board, board)
    cr.clip()
    cr.set_source_rgba(*(channel / 255 for channel in colors['grid_rgb']),
                       1.0 if game.game_over else 0.35)
    cr.set_line_width(1)
    for n in range(1, game.grid_cells):
        coordinate = n * cell + 0.5
        cr.move_to(coordinate, 0)
        cr.line_to(coordinate, board)
        cr.move_to(0, coordinate)
        cr.line_to(board, coordinate)
    cr.stroke()
    inset = max(1, round(cell / 8))
    # Tail shading follows the final three squares at any length.
    for index in range(len(game.snake) - 1, -1, -1):
        x, y = game.snake[index]
        cr.set_source_rgb(*segment_color(index, len(game.snake)))
        cr.rectangle(x * cell + inset, y * cell + inset, cell - 2 * inset, cell - 2 * inset)
        cr.fill()
    _draw_head_marker(cr, game, cell)
    for x, y in game.foods:
        # Orange: round dot.
        cr.set_source_rgb(*ORANGE_RGB)
        cr.arc((x + 0.5) * cell, (y + 0.5) * cell, cell * 0.28, 0, 2 * pi)
        cr.fill()
    if game.green_dot is not None:
        # Green: diamond, so the two rewards differ by shape as well as colour.
        x, y = game.green_dot
        cx, cy, half = (x + 0.5) * cell, (y + 0.5) * cell, cell * 0.45
        cr.set_source_rgb(*GREEN_RGB)
        cr.move_to(cx, cy - half)
        cr.line_to(cx + half, cy)
        cr.line_to(cx, cy + half)
        cr.line_to(cx - half, cy)
        cr.close_path()
        cr.fill()
    cr.restore()


def _draw_head_marker(cr, game, cell):
    """Chevron rotated to the actual heading, scaled with the cell."""
    x, y = game.snake[0]
    scale = cell / 16
    cr.save()
    cr.translate((x + 0.5) * cell, (y + 0.5) * cell)
    dx, dy = game.DIRECTIONS[game.direction]
    cr.rotate(atan2(dy, dx))
    cr.scale(scale, scale)
    cr.set_source_rgb(0.055, 0.075, 0.09)
    cr.set_line_width(1.5)
    cr.move_to(-2, -3)
    cr.line_to(2.5, 0)
    cr.line_to(-2, 3)
    cr.stroke()
    cr.restore()
