"""The real GStreamer backend's lifecycle against fakesink: no device or sound is involved.

Skipped where GI or GStreamer is unavailable. tests/native_audio_check.py covers the real sink.
"""
import io
import json
import sys
import time
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake import synth  # noqa: E402
from omarchy_snake.log import GameLog  # noqa: E402

try:
    from gi.repository import GLib
    from omarchy_snake import gst_audio
    from omarchy_snake.gst_audio import GstBackend, Gst
except (ImportError, ValueError) as error:
    gst_audio = None
    IMPORT_ERROR = error


def pump(predicate, timeout=3.0):
    """Run the default main context, as the GTK loop does, until the predicate holds."""
    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    with warnings.catch_warnings():
        # PyGObject's asyncio integration warns on every iteration under Python 3.14.
        warnings.simplefilter('ignore', DeprecationWarning)
        while time.monotonic() < deadline:
            while context.iteration(False):
                pass
            if predicate():
                return True
            time.sleep(0.005)
    return False


def state_of(channel):
    return channel.pipeline.get_state(Gst.SECOND)[1]


@unittest.skipIf(gst_audio is None, 'GStreamer bindings unavailable')
class BackendRig(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.backend = GstBackend(GameLog('verbose', self.stream), sinks=('fakesink',))
        self.addCleanup(self.backend.shutdown)
        self.cues = self.backend.channels['sfx']
        self.music = self.backend.channels['music']

    def events(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]


class CueTests(BackendRig):
    def test_a_cue_without_a_held_stream_plays_out_then_releases_the_pipeline(self):
        self.backend.play_cue('orange')
        self.assertEqual(state_of(self.cues), Gst.State.PLAYING)
        self.assertTrue(pump(lambda: state_of(self.cues) == Gst.State.READY))
        self.assertEqual(self.cues.cue_bytes, len(synth.cue('orange')))
        self.assertGreaterEqual(self.cues.bytes_pushed, len(synth.cue('orange')))

    def test_a_cold_start_leads_in_with_silence_because_stream_startup_swallows_audio(self):
        # Measured: 46 ms or more of a cue was lost when its stream opened with the cue.
        self.assertGreaterEqual(gst_audio.LEAD_IN_CHUNKS * gst_audio.CHUNK_BYTES
                                / synth.BYTES_PER_SAMPLE / synth.RATE, 0.1)
        self.backend.play_cue('orange')
        self.assertTrue(pump(lambda: self.backend.cue_pending is None))  # taken after the lead-in
        self.assertGreaterEqual(self.cues.buffers_pushed, gst_audio.LEAD_IN_CHUNKS)

    def test_silence_follows_a_final_cue_because_pipewire_reports_its_end_early(self):
        # Measured: EOS came about 100 ms before the audio finished, and stopping then cut it.
        self.backend.play_cue('orange')
        self.assertTrue(pump(lambda: state_of(self.cues) == Gst.State.READY))
        padding = self.cues.bytes_pushed - len(synth.cue('orange'))
        self.assertGreaterEqual(padding / synth.BYTES_PER_SAMPLE / synth.RATE, 0.2)

    def test_pcm_is_pushed_in_small_chunks_because_pipewire_silences_a_large_buffer(self):
        self.backend.play_cue('victory')
        self.assertTrue(pump(lambda: self.cues.buffers_pushed > 2))
        self.assertLessEqual(self.cues.largest_buffer, gst_audio.CHUNK_BYTES)

    def test_a_held_stream_stays_open_with_silence_between_cues(self):
        self.backend.hold_effects(True)
        self.assertEqual(state_of(self.cues), Gst.State.PLAYING)
        self.backend.play_cue('orange')
        self.assertTrue(pump(lambda: self.backend.cue_pcm is None and self.backend.cue_pending is None
                             and self.backend.lead_chunks == 0))
        pushed = self.cues.buffers_pushed
        self.assertTrue(pump(lambda: self.cues.buffers_pushed > pushed + 5))
        self.assertEqual(state_of(self.cues), Gst.State.PLAYING)

    def test_a_cue_on_a_held_stream_does_not_reopen_it_or_lead_in_again(self):
        self.backend.hold_effects(True)
        self.assertTrue(pump(lambda: self.backend.lead_chunks == 0))
        pushed = self.cues.buffers_pushed
        self.backend.play_cue('green')
        self.assertEqual(self.backend.lead_chunks, 0)
        self.assertGreaterEqual(self.cues.buffers_pushed, pushed)
        self.assertEqual(self.cues.cue_bytes, len(synth.cue('green')))

    def test_a_new_cue_replaces_the_old_one_and_releasing_ends_after_it(self):
        self.backend.hold_effects(True)
        self.backend.play_cue('victory')
        self.backend.play_cue('orange')
        self.assertEqual(self.cues.cue_bytes, len(synth.cue('orange')))
        self.backend.hold_effects(False)
        self.assertEqual(state_of(self.cues), Gst.State.PLAYING)
        self.assertTrue(pump(lambda: state_of(self.cues) == Gst.State.READY, 2.0))

    def test_a_cue_after_the_stream_has_begun_ending_still_plays(self):
        self.backend.hold_effects(True)
        self.backend.hold_effects(False)
        self.assertTrue(pump(lambda: self.backend.sfx_ending or state_of(self.cues) == Gst.State.READY))
        self.backend.play_cue('green')
        self.assertEqual(state_of(self.cues), Gst.State.PLAYING)
        self.assertFalse(self.backend.sfx_ending)
        self.assertTrue(pump(lambda: state_of(self.cues) == Gst.State.READY, 2.0))
        self.assertEqual(self.cues.cue_bytes, len(synth.cue('green')))

    def test_stop_cues_cuts_a_long_jingle_and_no_callback_restarts_it(self):
        self.backend.hold_effects(True)
        self.backend.play_cue('victory')
        self.backend.stop_cues()
        self.assertEqual(state_of(self.cues), Gst.State.READY)
        self.assertIsNone(self.backend.cue_pcm)
        pushed = self.cues.buffers_pushed
        pump(lambda: False, 0.1)
        self.assertEqual(state_of(self.cues), Gst.State.READY)
        self.assertEqual(self.cues.buffers_pushed, pushed)

    def test_levels_reach_the_volume_elements(self):
        self.backend.set_levels(0.1, 0.4)
        self.assertAlmostEqual(self.music.volume.get_property('volume'), 0.1)
        self.assertAlmostEqual(self.cues.volume.get_property('volume'), 0.4)


class MusicTests(BackendRig):
    def setUp(self):
        super().setUp()
        self.backend.music_pcm = synth.render_cue('green')  # short, so tests see it wrap

    def test_music_keeps_feeding_past_the_end_of_the_loop(self):
        self.backend.music('playing')
        self.assertTrue(pump(lambda: self.music.bytes_pushed > 2 * len(self.backend.music_pcm)))
        self.assertLessEqual(self.music.largest_buffer, gst_audio.CHUNK_BYTES)
        self.assertLessEqual(self.music.source.get_property('current-level-bytes'),
                             self.music.source.get_property('max-bytes'))

    def test_pause_releases_the_stream_and_resume_continues_from_the_same_place(self):
        self.backend.music('playing')
        self.assertTrue(pump(lambda: self.music.bytes_pushed > 4 * gst_audio.CHUNK_BYTES
                             and self.backend.music_offset > 0))
        self.backend.music('paused')
        self.assertEqual(state_of(self.music), Gst.State.READY)
        position = self.backend.music_offset
        self.assertGreater(position, 0)
        settled = self.music.bytes_pushed
        pump(lambda: False, 0.2)
        self.assertEqual((self.music.bytes_pushed, self.backend.music_offset), (settled, position))
        self.backend.music('playing')
        self.assertEqual(state_of(self.music), Gst.State.PLAYING)
        self.assertTrue(pump(lambda: self.music.bytes_pushed > settled))

    def test_stop_rewinds_and_the_next_play_starts_from_the_top(self):
        self.backend.music('playing')
        self.assertTrue(pump(lambda: self.backend.music_offset > 0))
        self.backend.music('stopped')
        self.assertEqual(state_of(self.music), Gst.State.READY)
        self.assertEqual(self.backend.music_offset, 0)
        pushed = self.music.bytes_pushed
        pump(lambda: False, 0.1)
        self.assertEqual(self.music.bytes_pushed, pushed)  # no late need-data resurrects it
        self.backend.music('playing')
        self.assertEqual(state_of(self.music), Gst.State.PLAYING)
        self.assertTrue(pump(lambda: self.music.bytes_pushed > pushed))


class ShutdownTests(BackendRig):
    def test_shutdown_is_final_idempotent_and_releases_everything(self):
        self.backend.music('playing')
        self.backend.play_cue('victory')
        self.backend.shutdown()
        self.backend.shutdown()
        for channel in (self.cues, self.music):
            self.assertEqual(state_of(channel), Gst.State.NULL)
            self.assertFalse(channel.watching)
        self.backend.music('playing')
        self.backend.play_cue('orange')
        self.backend.hold_effects(True)
        self.backend.stop_cues()
        self.backend.set_levels(0.2, 0.2)
        for channel in (self.cues, self.music):
            self.assertEqual(state_of(channel), Gst.State.NULL)


class FailureTests(BackendRig):
    def post_error(self, channel):
        element = channel.source
        error = GLib.Error('device went away')
        channel.pipeline.get_bus().post(Gst.Message.new_error(element, error, 'debug detail'))

    def test_a_pipeline_error_stops_that_channel_with_a_useful_diagnostic(self):
        self.backend.music('playing')
        self.post_error(self.music)
        self.assertTrue(pump(lambda: state_of(self.music) == Gst.State.READY))
        events = [e for e in self.events() if e['event'] == 'audio_error']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['channel'], 'music')
        self.assertIn('device went away', events[0]['message'])

    def test_repeated_errors_disable_the_channel_with_bounded_logging(self):
        for _ in range(gst_audio.MAX_FAILURES + 4):
            self.backend.play_cue('victory')
            self.post_error(self.cues)
            pump(lambda: state_of(self.cues) == Gst.State.READY, 0.5)
        self.assertIsNone(self.backend.cue_pending)
        names = [e['event'] for e in self.events()]
        self.assertEqual(names.count('audio_error'), gst_audio.MAX_FAILURES)
        self.assertEqual(names.count('audio_channel_disabled'), 1)
        self.backend.play_cue('orange')
        self.assertEqual(state_of(self.cues), Gst.State.READY)

    def test_a_failed_music_channel_does_not_silence_effects(self):
        self.backend.music('playing')
        self.post_error(self.music)
        pump(lambda: state_of(self.music) == Gst.State.READY)
        self.backend.play_cue('orange')
        self.assertEqual(state_of(self.cues), Gst.State.PLAYING)


@unittest.skipIf(gst_audio is None, 'GStreamer bindings unavailable')
class SinkChoiceTests(unittest.TestCase):
    def test_the_first_usable_candidate_is_used_and_reported(self):
        stream = io.StringIO()
        backend = GstBackend(GameLog('verbose', stream), sinks=('no-such-sink', 'fakesink'))
        self.addCleanup(backend.shutdown)
        self.assertEqual(backend.sink_name, 'fakesink')
        self.assertIn('audio_backend', stream.getvalue())

    def test_no_usable_sink_raises_so_create_backend_falls_back_to_silence(self):
        with self.assertRaises(OSError) as raised:
            GstBackend(GameLog('quiet'), sinks=('no-such-sink',))
        self.assertIn('no-such-sink', str(raised.exception))

    def test_default_candidates_prefer_pipewire_and_include_fallbacks(self):
        self.assertEqual(gst_audio.SINK_CANDIDATES[0], 'pipewiresink')
        self.assertGreater(len(gst_audio.SINK_CANDIDATES), 1)


if __name__ == '__main__':
    unittest.main()
