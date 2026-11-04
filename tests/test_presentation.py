"""Rendering shapes, tail visibility, HUD text and explanatory copy."""
import random
import struct
import sys
import unittest
from pathlib import Path

import cairo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake import text  # noqa: E402
from omarchy_snake.drawing import BORDER_PIXELS, BOARD_RGB, draw_board, segment_color  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402
from omarchy_snake.theme import contrast_ratio  # noqa: E402

APPEARANCE = {'border_rgb': (220, 225, 230), 'grid_rgb': (255, 255, 255)}


def hex_of(rgb):
    return '#' + ''.join(f'{round(c * 255):02x}' for c in rgb)


def render(game, cell, origin=(0, 0), extra=0, appearance=APPEARANCE):
    size = game.grid_cells * cell + 2 * BORDER_PIXELS + extra
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    draw_board(cairo.Context(surface), game, appearance, cell, origin)
    surface.flush()

    def pixel(x, y):
        raw = struct.unpack_from('=I', surface.get_data(), y * surface.get_stride() + x * 4)[0]
        return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255)
    return pixel


def centre(cell_xy, cell, origin=(0, 0)):
    return tuple(o + BORDER_PIXELS + c * cell + cell // 2 for o, c in zip(origin, cell_xy))


class DrawingTests(unittest.TestCase):
    def setUp(self):
        self.game = MovementPreview(rng=random.Random(2), difficulty='Hard')
        self.game.foods = {(10, 20)}
        self.game.green_dot = (20, 20)

    def test_green_reward_is_a_diamond_and_orange_a_round_dot(self):
        pixel = render(self.game, 16)
        gx, gy = centre((20, 20), 16)
        ox, oy = centre((10, 20), 16)
        green, orange = pixel(gx, gy), pixel(ox, oy)
        self.assertGreater(green[1], 200)
        self.assertGreater(orange[0], 200)
        self.assertEqual(pixel(gx + 5, gy), green)  # diamond reaches further along axes
        self.assertNotEqual(pixel(ox + 5, oy), orange)  # circle does not
        self.assertNotEqual(pixel(gx + 4, gy + 4), green)  # and it is not a square

    def test_board_scales_with_cell_size_without_changing_cells(self):
        for cell in (8, 16, 24):
            with self.subTest(cell=cell):
                pixel = render(self.game, cell, origin=(7, 3), extra=20)
                x, y = centre(self.game.snake[0], cell, (7, 3))
                self.assertGreater(pixel(x - cell // 4, y - cell // 4)[1], 150)  # head body fill
                self.assertEqual(self.game.grid_cells, 32)
                self.assertEqual(pixel(7, 3 + 20), (220, 225, 230))  # frame outer rim at origin
                self.assertEqual(pixel(2, 2), BOARD_RGB)  # outside the frame: plain background

    def test_game_over_turns_grid_red_and_victory_keeps_player_colours(self):
        self.game.game_over = True
        self.assertEqual(render(self.game, 16)(0, 40), (255, 51, 51))
        self.game.game_over, self.game.won = False, True
        self.assertEqual(render(self.game, 16)(0, 40), (220, 225, 230))

    def test_tail_tip_is_visible_against_the_board(self):
        board = hex_of(tuple(c / 255 for c in BOARD_RGB))
        for length in (4, 6, 30):
            tip = segment_color(length - 1, length)
            self.assertGreaterEqual(contrast_ratio(hex_of(tip), board), 1.9)


class TextTests(unittest.TestCase):
    def test_hud_shows_score_length_and_best(self):
        game = MovementPreview(difficulty='Normal')
        game.score = 3
        game.snake = game.snake + [(0, 0), (0, 1), (0, 2)]
        self.assertEqual(text.hud_text(game, best=12), 'Score 3  ·  Length 9  ·  Best 12')
        game.score = 15
        self.assertEqual(text.hud_text(game, best=12), 'Score 15  ·  Length 9  ·  Best 15')

    def test_difficulty_details_explain_edges_collisions_green_and_pace(self):
        self.assertIn('wrap', text.DIFFICULTY_DETAILS['Easy'].lower())
        self.assertIn('wrap', text.DIFFICULTY_DETAILS['Normal'].lower())
        hard = text.DIFFICULTY_DETAILS['Hard'].lower()
        self.assertIn('wall', hard)
        self.assertIn('0.05', hard)
        self.assertIn('steady', text.DIFFICULTY_DETAILS['Easy'].lower())
        self.assertIn('green', text.REWARD_HELP.lower())
        self.assertIn('30', text.REWARD_HELP)

    def test_states_are_named_not_only_coloured(self):
        game = MovementPreview(difficulty='Hard')
        self.assertIn('Esc', text.status_text(game, paused=True))
        menu_pause = text.status_text(game, paused=True, manual=False)
        self.assertIn('Paused', menu_pause)
        self.assertNotIn('Resume', menu_pause)
        game.game_over, game.game_over_reason = True, 'wall collision'
        self.assertIn('Game over', text.status_text(game, paused=False))
        self.assertIn('wall collision', text.status_text(game, paused=False))
        game.game_over, game.won = False, True
        self.assertIn('Board complete', text.status_text(game, paused=False))
        game.won = False
        running = text.status_text(game, paused=False)
        self.assertIn('0.15 sec', running)
        self.assertIn('Solid walls', running)
        self.assertIn('Esc', running)


if __name__ == '__main__':
    unittest.main()
