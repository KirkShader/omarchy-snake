"""Decides what should sound from session events and settings; needs no audio libraries.

Music plays only while GameSession.running. Any pause reason pauses it and stops effects, a
finished run stops it, and a switched-off or zero-volume channel stays off through every
pause, resume and New Game. The backend in use may be silent (see create_backend).
"""
from .preferences import DEFAULT_AUDIO
from .synth import MUSIC_GAIN


class NullBackend:
    """Silent gameplay: used when no audio library, plugin or device is available."""

    def set_levels(self, music, sfx):
        pass

    def play_cue(self, name):
        pass

    def stop_cues(self):
        pass

    def hold_effects(self, held):
        pass

    def music(self, state):
        pass

    def shutdown(self):
        pass


def _load_gst_backend(log):
    from .gst_audio import GstBackend  # Optional: importing it needs GI and GStreamer.
    return GstBackend(log)


def create_backend(log):
    """The real backend, or a silent one (with a diagnostic) when audio cannot be set up."""
    try:
        return _load_gst_backend(log)
    except (ImportError, ValueError, OSError) as error:
        log.event('audio_unavailable', reason=str(error)[:200])
        return NullBackend()


class AudioDirector:
    def __init__(self, backend, settings=None):
        self.backend = backend
        self.settings = dict(settings or DEFAULT_AUDIO)
        self.music_state = 'stopped'
        self.finish_cued = False
        self.closed = False
        self._apply_levels()

    @property
    def _volume(self):
        return self.settings['master_volume']

    @property
    def _music_audible(self):
        return self.settings['music_enabled'] and self._volume > 0

    @property
    def _sfx_audible(self):
        return self.settings['sfx_enabled'] and self._volume > 0

    def _apply_levels(self):
        self.backend.set_levels(self._volume * MUSIC_GAIN, self._volume)

    def _cue(self, name):
        if self._sfx_audible:
            self.backend.play_cue(name)

    def _set_music(self, state):
        if state != self.music_state:
            self.music_state = state
            self.backend.music(state)

    def on_event(self, event, session):
        if self.closed:
            return
        if event == 'step':
            if session.game.last_reward and not session.game.finished:
                self._cue(session.game.last_reward)
        elif event == 'finished':
            self._set_music('stopped')
            if not self.finish_cued:
                self.finish_cued = True
                self._cue('victory' if session.game.won else 'game_over')
            self.backend.hold_effects(False)  # The stream closes once the cue has played out.
        elif event == 'new_game':
            self.finish_cued = False
            self._set_music('stopped')  # The new run's melody starts from the top.
            if session.running:
                self._cue('start')
            self.sync(session)
        elif event == 'begin':
            if session.running:
                self._cue('start')
            self.sync(session)
        elif event == 'pause_changed':
            if session.paused:
                self.backend.stop_cues()
            self.sync(session)

    def sync(self, session):
        """Bring the music in line with the run and settings; it never starts while paused."""
        if self.closed:
            return
        self.backend.hold_effects(bool(session.running and self._sfx_audible))
        if not self._music_audible or session.game.finished or not session.started:
            self._set_music('stopped')
        elif session.running:
            self._set_music('playing')
        elif self.music_state == 'playing':
            self._set_music('paused')

    def update(self, session, **changes):
        """Apply Options changes at once. Settings stay readable for saving after shutdown."""
        self.settings.update(changes)
        if self.closed:
            return
        self._apply_levels()
        if not self._sfx_audible:
            self.backend.stop_cues()
        self.sync(session)

    def shutdown(self):
        if not self.closed:
            self.closed = True
            self.backend.shutdown()
