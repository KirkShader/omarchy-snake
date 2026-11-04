"""Display fit: choose a rendered cell size; board cell counts and coordinates never change."""
from dataclasses import dataclass
from math import floor

from .drawing import BORDER_PIXELS

TARGET_CELL_PIXELS = 16
MIN_CELL_PIXELS = 6  # Smallest readable cell; below this the board scrolls instead.
AUTO_MAX_CELL_PIXELS = 48
# Whole-pixel cell sizes keep grid lines sharp. 'auto' fills the usable area.
ZOOM_LEVELS = {'auto': None, '50': 8, '75': 12, '100': 16, '125': 20, '150': 24, '200': 32}
ZOOM_LABELS = {'auto': 'Auto fit', '50': '50%', '75': '75%', '100': '100%',
               '125': '125%', '150': '150%', '200': '200%'}
DEFAULT_ZOOM = '100'
# GTK cannot report compositor bars/gaps on Wayland, so leave a conservative logical margin.
SCREEN_ALLOWANCE = (40, 72)


def logical_size(width, height, scale):
    """Logical (GTK) size of a monitor whose physical mode is width x height at a scale."""
    return floor(width / scale), floor(height / scale)


@dataclass(frozen=True)
class BoardFit:
    cells: int
    cell_pixels: int
    requested_cell_pixels: int
    limited: bool
    scroll_fallback: bool

    @property
    def board_pixels(self):
        return self.cells * self.cell_pixels

    @property
    def frame_pixels(self):
        return self.board_pixels + 2 * BORDER_PIXELS


def fit_board(cells, available_width, available_height, chrome_width, chrome_height,
              zoom=DEFAULT_ZOOM):
    """Largest whole-pixel cell not above the zoom request that keeps the window on screen."""
    if zoom not in ZOOM_LEVELS:
        raise ValueError(f'Unknown zoom level: {zoom}')
    space = min(available_width - chrome_width, available_height - chrome_height) - 2 * BORDER_PIXELS
    fitting = max(0, space // cells)
    requested = ZOOM_LEVELS[zoom]
    if requested is None:
        requested = max(MIN_CELL_PIXELS, min(fitting, AUTO_MAX_CELL_PIXELS))
    cell = max(MIN_CELL_PIXELS, min(requested, fitting))
    frame = cells * cell + 2 * BORDER_PIXELS
    fallback = frame + chrome_width > available_width or frame + chrome_height > available_height
    return BoardFit(cells, cell, requested, cell < requested, fallback)


def window_size(fit, chrome_width, chrome_height, available_width, available_height):
    """Requested window size; capped to the usable area when the board must scroll."""
    return (min(fit.frame_pixels + chrome_width, available_width),
            min(fit.frame_pixels + chrome_height, available_height))


def board_layout(fit, allocated_width, allocated_height):
    """Whole-pixel origin of the frame, centred in whatever space GTK allocated."""
    return (max(0, (allocated_width - fit.frame_pixels) // 2),
            max(0, (allocated_height - fit.frame_pixels) // 2))


def scroll_to_keep_visible(offset, viewport, extent, cell_start, cell_size, margin_cells=4):
    """Scroll offset that keeps a cell (the head) inside the viewport with a margin."""
    if viewport >= extent:
        return 0
    margin = margin_cells * cell_size
    if cell_start - margin < offset:
        offset = cell_start - margin
    elif cell_start + cell_size + margin > offset + viewport:
        offset = cell_start + cell_size + margin - viewport
    return max(0, min(offset, extent - viewport))
