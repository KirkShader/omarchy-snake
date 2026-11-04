"""Original offline arcade sounds: deterministic S16LE mono PCM computed from note tables.

No samples, recordings or downloads are involved; the same code always gives the same bytes.
"""
import array
import sys
from functools import lru_cache

RATE = 22050
BYTES_PER_SAMPLE = 2
FULL_SCALE = 32767
ATTACK_SECONDS = 0.003
RELEASE_SECONDS = 0.012
CUE_PEAK = 0.6
MUSIC_PEAK = 0.5
MUSIC_GAIN = 0.35  # The music channel's level relative to the effects channel.
MUSIC_STEP_SECONDS = 0.18


def _square(phase):
    return 1.0 if phase < 0.5 else -1.0


def _triangle(phase):
    return 4.0 * abs(phase - 0.5) - 1.0


def _saw(phase):
    return 2.0 * phase - 1.0


def _render(notes, wave, peak):
    """Notes are (Hz or None for a rest, seconds), played one at a time, each with its own
    short envelope, so every note begins and ends at silence without clicks."""
    output = array.array('h')
    for frequency, seconds in notes:
        count = round(seconds * RATE)
        if frequency is None:
            output.extend([0] * count)
            continue
        attack, release = ATTACK_SECONDS * RATE, RELEASE_SECONDS * RATE
        for index in range(count):
            envelope = min(1.0, index / attack, (count - 1 - index) / release)
            value = wave(index * frequency / RATE % 1.0) * envelope * peak
            output.append(round(value * FULL_SCALE))
    if sys.byteorder == 'big':
        output.byteswap()
    return output.tobytes()


CUE_NOTES = {
    'orange': [(1568.0, 0.08)],                                 # bright single beep
    'green': [(784.0, 0.09), (523.25, 0.13)],                   # two descending notes
    'start': [(523.25, 0.07), (659.25, 0.07), (783.99, 0.09)],  # quick rising three notes
    'game_over': [(196.0, 0.11), (164.81, 0.11), (138.59, 0.11), (110.0, 0.13),
                  (87.31, 0.15), (65.41, 0.24)],                # low descending buzz
    'victory': [(523.25, 0.1), (659.25, 0.1), (783.99, 0.1), (1046.5, 0.18),
                (783.99, 0.1), (1046.5, 0.36)],                 # short celebratory jingle
}
_CUE_WAVES = {'game_over': _saw, 'green': _triangle}

# MIDI note numbers, one per step; None is a rest. The two opening rests leave room for the
# start cue, so a new run's melody enters just after it without needing a timer.
MUSIC_NOTES = (None, None, 57, 60, 64, 60, 65, 64, 60, 57, 55, 59, 62, 59, 64, 62, 59, 55,
               57, 60, 64, 69, 67, 64, 60, 64, 65, 62, 59, 62, 60, 59, 57, None)


def _hertz(note):
    return None if note is None else 440.0 * 2 ** ((note - 69) / 12)


def render_cue(name):
    return _render(CUE_NOTES[name], _CUE_WAVES.get(name, _square), CUE_PEAK)


def render_music():
    notes = [(_hertz(note), MUSIC_STEP_SECONDS) for note in MUSIC_NOTES]
    return _render(notes, _triangle, MUSIC_PEAK)


@lru_cache(maxsize=None)
def cue(name):
    return render_cue(name)


@lru_cache(maxsize=1)
def music_loop():
    return render_music()
