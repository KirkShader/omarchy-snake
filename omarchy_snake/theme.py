"""Read-only Omarchy palette support and reserved warning colours."""
import os
import re
import tomllib
from pathlib import Path

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


OVERLAY_BACKGROUND = '#050505'  # Overlay cards sit on the near-black board in every theme.
VICTORY_HEX = '#ffd166'
LIGHT_TEXT, DARK_TEXT = '#f2f2f2', '#111111'
MIN_TEXT_CONTRAST = 4.5  # WCAG AA for normal text.


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def readable_on(foreground, background, minimum=MIN_TEXT_CONTRAST):
    """Keep the theme colour when readable; otherwise the better of light or dark text."""
    if contrast_ratio(foreground, background) >= minimum:
        return foreground
    return max((LIGHT_TEXT, DARK_TEXT), key=lambda text: contrast_ratio(text, background))


def overlay_button_colors(palette):
    """Foreground, background and hover chosen together so all states stay readable."""
    foreground = readable_on(palette['foreground'], OVERLAY_BACKGROUND)
    for hover in (palette['selection'], '#26332b', '#181818'):
        if contrast_ratio(foreground, hover) >= MIN_TEXT_CONTRAST:
            break
    else:
        foreground, hover = LIGHT_TEXT, '#26332b'
    return {'foreground': foreground, 'background': OVERLAY_BACKGROUND, 'hover': hover}


def build_css(palette):
    background = palette['background']
    foreground = readable_on(palette['foreground'], background)
    selection = palette['selection']
    if contrast_ratio(foreground, selection) < MIN_TEXT_CONTRAST:
        selection = background
    overlay = overlay_button_colors(palette)
    return f'''
        .snake-window, .snake-window headerbar {{
            background-color: {background};
            background-image: none;
            color: {foreground};
            opacity: 1;
        }}
        .snake-window label, .snake-window button,
        .snake-menu-popover label, .snake-menu-popover button {{
            color: {foreground};
        }}
        .snake-window .snake-title {{ font-weight: bold; font-size: 18px; }}
        .snake-window .snake-hud {{ font-weight: bold; }}
        .snake-window headerbar button, .snake-difficulty-card button {{
            background-color: {background};
            background-image: none;
        }}
        .snake-window headerbar button:hover,
        .snake-window headerbar button:checked,
        .snake-difficulty-card button:hover,
        .snake-difficulty-card button:focus-visible {{
            background-color: {selection};
        }}
        .snake-window button:focus-visible, .snake-menu-popover button:focus-visible {{
            outline: 2px solid {foreground};
            outline-offset: 1px;
        }}
        .snake-menu-popover > contents {{
            background: transparent;
            border: none;
            border-radius: 0;
            box-shadow: none;
            padding: 0;
        }}
        .snake-menu-panel {{ background-color: {background}; }}
        .snake-menu-panel button {{
            background: {background};
            border: none;
            border-radius: 0;
            box-shadow: none;
            padding: 8px 12px;
        }}
        .snake-menu-panel button:hover {{ background: {selection}; }}
        .snake-menu-panel .snake-appearance-warning {{ color: {readable_on(GAME_OVER_HEX, background)}; }}
        .snake-modal-shade {{ background-color: rgba(0, 0, 0, 0.65); }}
        .snake-difficulty-card {{
            background-color: {background};
            color: {foreground};
            border: 1px solid {palette['accent']};
            padding: 22px;
        }}
        .snake-difficulty-card .snake-difficulty-detail {{ font-size: 12px; }}
        .snake-overlay-card {{
            background-color: {overlay['background']};
            border: 2px solid {overlay['foreground']};
            padding: 26px 40px;
        }}
        .snake-overlay-card.snake-lost {{ border-color: {GAME_OVER_HEX}; }}
        .snake-overlay-card.snake-won {{ border-color: {VICTORY_HEX}; }}
        .snake-window .snake-overlay-card label {{ color: {overlay['foreground']}; }}
        .snake-window .snake-overlay-title {{ font-size: 42px; font-weight: bold; }}
        .snake-window .snake-lost .snake-overlay-title {{ color: {GAME_OVER_HEX}; }}
        .snake-window .snake-won .snake-overlay-title {{ color: {VICTORY_HEX}; }}
        .snake-window .snake-overlay-card button {{
            background: {overlay['background']};
            background-image: none;
            color: {overlay['foreground']};
            border: 1px solid {overlay['foreground']};
            padding: 10px 22px;
        }}
        .snake-window .snake-overlay-card button:hover,
        .snake-window .snake-overlay-card button:focus-visible {{
            background: {overlay['hover']};
            color: {overlay['foreground']};
        }}
    '''
