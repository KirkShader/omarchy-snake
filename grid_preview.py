"""Native offline Omarchy Snake launcher and compatibility façade; no network or installation.

The game lives in the `omarchy_snake` package. This historical filename stays the stable
launcher, and re-exports the public names older tests and tools import from it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from omarchy_snake.rules import (  # noqa: E402,F401  (re-exported for tools and tests)
    BOARD_PIXELS, CELL_PIXELS, DIFFICULTIES, GREEN_INTERVAL_MS, GRID_CELLS, HARD_MIN_STEP_INTERVAL_MS,
    HARD_SPEEDUP_MS, MAX_QUEUED_TURNS, MIN_STEP_INTERVAL_MS, STEP_INTERVAL_MS, MovementPreview)
from omarchy_snake.theme import (  # noqa: E402,F401
    GAME_OVER_HEX, GAME_OVER_RGB, TEXT_RGB, board_colors, is_reserved_color, load_omarchy_palette)
from omarchy_snake.drawing import BORDER_PIXELS, draw_board, draw_board_border, segment_color  # noqa: E402,F401


def main(argv=None, game_factory=None, on_ready=None):
    from omarchy_snake.app import main as run_app  # GTK is only needed when launching
    return run_app(sys.argv[1:] if argv is None else argv, game_factory, on_ready)


if __name__ == '__main__':
    raise SystemExit(main())
