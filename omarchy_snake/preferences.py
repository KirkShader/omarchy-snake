"""Versioned local JSON for appearance/zoom (XDG config) and best scores (XDG state).

Ordinary, non-secret game data: files are 0644, written atomically. Missing, corrupted or
out-of-range data falls back to defaults per field; failed writes never stop gameplay.
"""
import json
import os
import tempfile
from pathlib import Path

from .geometry import DEFAULT_ZOOM, ZOOM_LEVELS
from .rules import DIFFICULTIES
from .theme import TEXT_RGB, is_reserved_color

SCHEMA_VERSION = 1
APP_DIR = 'omarchy-snake'
SCORE_LIMIT = 10 ** 9
DEFAULT_SETTINGS = {'border_rgb': TEXT_RGB, 'grid_rgb': (255, 255, 255), 'zoom': DEFAULT_ZOOM}
DEFAULT_AUDIO = {'music_enabled': True, 'sfx_enabled': True, 'master_volume': 0.3}


def default_dirs(env=None):
    """XDG config and state directories; relative XDG values are ignored per the spec."""
    env = os.environ if env is None else env
    home = Path(env.get('HOME') or Path.home())

    def base(name, fallback):
        value = env.get(name)
        return Path(value) if value and Path(value).is_absolute() else home / fallback

    return (base('XDG_CONFIG_HOME', '.config') / APP_DIR,
            base('XDG_STATE_HOME', '.local/state') / APP_DIR)


def valid_rgb(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    if not all(type(channel) is int and 0 <= channel <= 255 for channel in value):
        return None
    return None if is_reserved_color(value) else tuple(value)


def valid_score(value):
    return value if type(value) is int and 0 <= value <= SCORE_LIMIT else 0


def valid_volume(value):
    """A range check also rejects NaN and infinity; bool is excluded by the exact type test."""
    return type(value) in (int, float) and 0 <= value <= 1


def valid_audio(audio):
    return (type(audio.get('music_enabled')) is bool and type(audio.get('sfx_enabled')) is bool
            and valid_volume(audio.get('master_volume')))


def record_score(scores, difficulty, score):
    """Raise a difficulty's best score; True when this is a new best."""
    if score > scores.get(difficulty, 0):
        scores[difficulty] = score
        return True
    return False


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('version') != SCHEMA_VERSION:
        return None
    return data


def atomic_write_json(path, data):
    """Write via a same-directory temporary file and rename; raises OSError on failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class BestScores:
    """In-memory bests that never go down. A best whose save failed stays dirty, so the
    next commit (finish, New Game or close) retries it even when that run scored less."""

    def __init__(self, store):
        self.store = store
        self.scores = store.load_scores()
        self.dirty = False

    def get(self, difficulty):
        return self.scores.get(difficulty, 0)

    def commit(self, difficulty, score):
        """Record a score and write any unsaved best; True when nothing is left unsaved."""
        if record_score(self.scores, difficulty, score):
            self.dirty = True
        if self.dirty:
            self.dirty = not self.store.save_scores(self.scores)
        return not self.dirty


class PreferenceStore:
    def __init__(self, config_dir=None, state_dir=None, log=None):
        default_config, default_state = default_dirs()
        self.config_dir = Path(config_dir) if config_dir else default_config
        self.state_dir = Path(state_dir) if state_dir else default_state
        self.log = log or (lambda *_args, **_kwargs: None)

    @property
    def settings_path(self):
        return self.config_dir / 'settings.json'

    @property
    def scores_path(self):
        return self.state_dir / 'scores.json'

    def load_settings(self):
        data = _read(self.settings_path) or {}
        settings = dict(DEFAULT_SETTINGS)
        for key in ('border_rgb', 'grid_rgb'):
            settings[key] = valid_rgb(data.get(key)) or DEFAULT_SETTINGS[key]
        zoom = data.get('zoom')
        settings['zoom'] = zoom if isinstance(zoom, str) and zoom in ZOOM_LEVELS else DEFAULT_ZOOM
        return settings

    def load_audio(self):
        data = _read(self.settings_path) or {}
        audio = dict(DEFAULT_AUDIO)
        for key in ('music_enabled', 'sfx_enabled'):
            if type(data.get(key)) is bool:
                audio[key] = data[key]
        if valid_volume(data.get('master_volume')):
            audio['master_volume'] = data['master_volume']
        return audio

    def load_scores(self):
        data = _read(self.scores_path) or {}
        stored = data.get('high_scores')
        stored = stored if isinstance(stored, dict) else {}
        return {difficulty: valid_score(stored.get(difficulty, 0)) for difficulty in DIFFICULTIES}

    def save_settings(self, settings, audio=None):
        """Without `audio`, whatever audio settings the file already holds are kept."""
        colours = [valid_rgb(settings.get(key)) for key in ('border_rgb', 'grid_rgb')]
        if audio is None and self.settings_path.exists():
            audio = self.load_audio()
        if (None in colours or settings.get('zoom') not in ZOOM_LEVELS
                or (audio is not None and not valid_audio(audio))):
            self.log('preferences_rejected', path=str(self.settings_path))
            return False
        data = {'version': SCHEMA_VERSION, 'border_rgb': list(colours[0]),
                'grid_rgb': list(colours[1]), 'zoom': settings['zoom']}
        if audio is not None:
            data.update({key: audio[key] for key in DEFAULT_AUDIO})
        return self._save(self.settings_path, data)

    def save_scores(self, scores):
        return self._save(self.scores_path, {
            'version': SCHEMA_VERSION,
            'high_scores': {d: valid_score(scores.get(d, 0)) for d in DIFFICULTIES}})

    def _save(self, path, data):
        try:
            atomic_write_json(path, data)
        except OSError as error:
            self.log('preferences_write_failed', path=str(path), error=str(error))
            return False
        return True
