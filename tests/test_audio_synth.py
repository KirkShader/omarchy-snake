"""Deterministic offline synthesis: format, bounds, silence at the edges, distinct cues."""
import array
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake import synth  # noqa: E402


def samples(pcm):
    data = array.array('h')
    data.frombytes(pcm)
    return data


class CueFormatTests(unittest.TestCase):
    def test_orange_is_a_short_audible_s16_mono_beep(self):
        pcm = synth.cue('orange')
        self.assertEqual(len(pcm) % synth.BYTES_PER_SAMPLE, 0)
        self.assertLess(len(pcm) / synth.BYTES_PER_SAMPLE / synth.RATE, 0.2)
        self.assertGreater(max(abs(v) for v in samples(pcm)), 1000)

    def test_every_cue_is_bounded_and_starts_and_ends_silent(self):
        for name, limit in [('orange', 0.2), ('green', 0.4), ('start', 0.4),
                            ('game_over', 1.2), ('victory', 1.5)]:
            with self.subTest(cue=name):
                data = samples(synth.cue(name))
                self.assertLessEqual(len(data) / synth.RATE, limit)
                self.assertEqual((data[0], data[-1]), (0, 0))
                self.assertLessEqual(max(abs(v) for v in data), synth.FULL_SCALE)

    def test_envelope_rises_and_falls_gradually_instead_of_clicking(self):
        data = samples(synth.cue('orange'))
        self.assertLess(abs(data[1]), 0.2 * synth.FULL_SCALE)
        self.assertLess(abs(data[-2]), 0.2 * synth.FULL_SCALE)

    def test_cues_are_distinct_and_the_green_notes_descend(self):
        names = ('orange', 'green', 'start', 'game_over', 'victory')
        self.assertEqual(len({synth.cue(name) for name in names}), len(names))
        pitches = [hz for hz, _ in synth.CUE_NOTES['green']]
        self.assertEqual(len(pitches), 2)
        self.assertGreater(pitches[0], pitches[1])
        self.assertEqual(len(synth.CUE_NOTES['start']), 3)
        low = [hz for hz, _ in synth.CUE_NOTES['game_over']]
        self.assertEqual(low, sorted(low, reverse=True))
        self.assertLess(low[0], 300)

    def test_rendering_is_deterministic(self):
        for name in ('orange', 'victory'):
            self.assertEqual(synth.render_cue(name), synth.render_cue(name))
        self.assertEqual(synth.render_music(), synth.render_music())


class MusicTests(unittest.TestCase):
    def test_loop_is_bounded_monophonic_and_silent_at_the_seam(self):
        data = samples(synth.music_loop())
        self.assertLessEqual(len(data) / synth.RATE, 8.0)
        self.assertGreaterEqual(len(data) / synth.RATE, 2.0)
        self.assertEqual((data[0], data[-1]), (0, 0))
        for note in synth.MUSIC_NOTES:  # a note table of single pitches cannot hold a chord
            self.assertTrue(note is None or isinstance(note, int), note)

    def test_loop_begins_with_a_rest_that_leaves_room_for_the_start_cue(self):
        start_cue = len(synth.cue('start')) / synth.BYTES_PER_SAMPLE
        data = samples(synth.music_loop())
        self.assertEqual(max(abs(v) for v in data[:int(start_cue)]), 0)

    def test_music_is_mixed_quieter_than_effects(self):
        music = max(abs(v) for v in samples(synth.music_loop())) * synth.MUSIC_GAIN
        effect = max(abs(v) for v in samples(synth.cue('orange')))
        self.assertLess(music, effect / 2)


if __name__ == '__main__':
    unittest.main()
