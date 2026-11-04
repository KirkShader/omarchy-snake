"""Plays synthesized PCM through GStreamer: appsrc ! volume ! audioconvert ! audioresample ! sink.

Importing this module needs GI and GStreamer, so only audio.create_backend imports it, and its
failures become silent gameplay. There are two reused pipelines, so a cue never interrupts the
music. Each is fed small chunks on demand and releases its audio stream (READY) when idle.

Three PipeWire behaviours (measured on 1.6.9) shape the effects channel; a pipeline can report
success through all of them, so tests/native_audio_check.py measures the recorded audio:
- One large buffer plays as silence, so PCM is pushed in small chunks.
- Opening a stream swallows its first 46 ms or more, which is most of a short beep. So the stream
  stays open with silence during active play, and a cold start leads in with silence first.
- EOS arrives about 100 ms before the sound has finished, so silence follows the last cue.
"""
import os

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst  # noqa: E402

from . import synth  # noqa: E402

SINK_CANDIDATES = ('pipewiresink', 'pulsesink', 'autoaudiosink', 'alsasink')
CHUNK_BYTES = 1024  # 23 ms
QUEUED_CHUNKS = 2
LEAD_IN_CHUNKS = 7  # 162 ms
CUE_TAIL_CHUNKS = 14  # 325 ms
MAX_FAILURES = 3  # A channel that keeps failing goes silent for this launch.
CAPS = f'audio/x-raw,format=S16LE,rate={synth.RATE},channels=1,layout=interleaved'
SILENCE = bytes(CHUNK_BYTES)


def _make(factory):
    element = Gst.ElementFactory.make(factory)
    if element is None:
        raise OSError(f'GStreamer element {factory} is unavailable')
    return element


def _open_sink(candidates, stream):
    """The first candidate that exists and can reach its sound server or device. It is named
    before opening, because pipewiresink creates its stream on the way to READY."""
    tried = []
    for name in candidates:
        sink = Gst.ElementFactory.make(name)
        if sink is None:
            tried.append(f'{name}: missing')
            continue
        _describe_stream(sink, stream)
        if sink.set_state(Gst.State.READY) == Gst.StateChangeReturn.FAILURE:
            sink.set_state(Gst.State.NULL)
            tried.append(f'{name}: cannot connect')
        else:
            return name, sink
    raise OSError('no usable audio sink (' + ', '.join(tried) + ')')


def _describe_stream(sink, name):
    """Name the stream in the desktop's audio tools; sinks without these properties skip it."""
    if sink.find_property('sync'):
        sink.set_property('sync', True)
    if sink.find_property('client-name'):
        sink.set_property('client-name', 'Omarchy Snake')
    if sink.find_property('stream-properties'):
        properties = Gst.Structure.new_empty('stream-properties')
        properties.set_value('media.name', f'Omarchy Snake {name}')
        properties.set_value('media.role', 'Game')
        properties.set_value('node.name', f'omarchy-snake-{name}-{os.getpid()}')
        sink.set_property('stream-properties', properties)


class _Channel:
    def __init__(self, name, candidates, on_error, on_finished, on_need_data):
        self.name = name
        self.on_error, self.on_finished, self.on_need_data = on_error, on_finished, on_need_data
        self.failures = 0
        self.disabled = False
        self.bytes_pushed = self.buffers_pushed = self.largest_buffer = self.cue_bytes = 0
        self.sink_name, self.sink = _open_sink(candidates, name)
        try:
            self.source, self.volume = _make('appsrc'), _make('volume')
            convert, resample = _make('audioconvert'), _make('audioresample')
        except OSError:
            self.sink.set_state(Gst.State.NULL)
            raise
        self.source.set_property('caps', Gst.Caps.from_string(CAPS))
        self.source.set_property('format', Gst.Format.TIME)
        self.source.set_property('max-bytes', CHUNK_BYTES * QUEUED_CHUNKS)
        self.pipeline = Gst.Pipeline.new(f'omarchy-snake-{name}')
        elements = [self.source, self.volume, convert, resample, self.sink]
        for element in elements:  # One at a time: gst-python's add(*many) override is optional.
            self.pipeline.add(element)
        if not all(a.link(b) for a, b in zip(elements, elements[1:])):
            self.pipeline.set_state(Gst.State.NULL)
            raise OSError(f'cannot link the {name} audio pipeline')
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.handlers = [(self.bus, self.bus.connect('message::error', self._bus_error)),
                         (self.bus, self.bus.connect('message::eos', self._bus_eos)),
                         (self.source, self.source.connect('need-data', self._need_data))]
        self.watching = True
        self.stop()

    def reset_counts(self):
        self.bytes_pushed = self.buffers_pushed = self.largest_buffer = 0

    def _bus_error(self, _bus, message):
        error, _debug = message.parse_error()
        self.on_error(self, error.message)

    def _bus_eos(self, _bus, _message):
        self.on_finished(self)

    def _need_data(self, _source, _length):
        # Runs on GStreamer's streaming thread, which set_state(READY) joins before returning.
        self.on_need_data(self)

    def stop(self):
        """Drop queued audio and pending bus messages, so nothing stale can act afterwards."""
        self.bus.set_flushing(True)
        self.pipeline.set_state(Gst.State.NULL)  # READY alone leaves a stream that later stutters.
        self.pipeline.set_state(Gst.State.READY)
        self.bus.set_flushing(False)

    def start(self):
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            self.on_error(self, 'cannot start playing')
            return False
        return True

    def push(self, pcm, first_sample):
        """Timestamped by sample count, so a looping stream never drifts."""
        buffer = Gst.Buffer.new_wrapped(pcm)
        count = len(pcm) // synth.BYTES_PER_SAMPLE
        buffer.pts = first_sample * Gst.SECOND // synth.RATE
        buffer.duration = (first_sample + count) * Gst.SECOND // synth.RATE - buffer.pts
        self.bytes_pushed += len(pcm)
        self.buffers_pushed += 1
        self.largest_buffer = max(self.largest_buffer, len(pcm))
        self.source.emit('push-buffer', buffer)
        return first_sample + count

    def close(self):
        self.pipeline.set_state(Gst.State.NULL)
        if self.watching:
            for owner, handler in self.handlers:
                owner.disconnect(handler)
            self.bus.remove_signal_watch()
            self.watching = False


class GstBackend:
    def __init__(self, log, sinks=None):
        try:
            Gst.init(None)
        except GLib.Error as error:
            raise OSError(f'GStreamer failed to initialize: {error.message}') from error
        self.log = log
        self.closed = False
        self.music_pcm = synth.music_loop()
        self.music_offset = self.music_sample = 0
        self.effects_held = False
        self._reset_effects()
        candidates = SINK_CANDIDATES if sinks is None else sinks
        cues = _Channel('sfx', candidates, self._failed, self._effects_ended, self._feed_effects)
        try:
            music = _Channel('music', candidates, self._failed, self._music_ended, self._feed_music)
        except OSError:
            cues.close()
            raise
        self.channels = {'sfx': cues, 'music': music}
        self.sink_name = cues.sink_name
        log.event('audio_backend', sink=self.sink_name, gstreamer=Gst.version_string())

    def _reset_effects(self):
        self.sfx_live = self.sfx_ending = False
        self.cue_pending = self.cue_pcm = None
        self.cue_offset = self.cue_sample = self.lead_chunks = self.tail_chunks = 0

    def _failed(self, channel, message):
        channel.stop()
        if channel.name == 'music':
            self.music_offset = self.music_sample = 0
        else:
            self._reset_effects()
        channel.failures += 1
        if channel.disabled:
            return
        self.log.event('audio_error', channel=channel.name, sink=channel.sink_name, message=message[:200])
        if channel.failures >= MAX_FAILURES:
            channel.disabled = True
            self.log.event('audio_channel_disabled', channel=channel.name)

    def _effects_ended(self, channel):
        channel.stop()
        self._reset_effects()

    def _music_ended(self, channel):
        channel.stop()

    def _start_effects(self):
        channel = self.channels['sfx']
        channel.stop()
        channel.reset_counts()
        self._reset_effects()
        self.lead_chunks = LEAD_IN_CHUNKS
        self.sfx_live = channel.start()

    def _feed_effects(self, channel):
        """The cue fields belong to this thread while playing; the main thread hands over a new
        cue through the single cue_pending assignment, and resets them only after stop()."""
        if self.lead_chunks > 0:
            self.lead_chunks -= 1
            self.cue_sample = channel.push(SILENCE, self.cue_sample)
            return
        pending = self.cue_pending
        if pending is not None:
            self.cue_pending = None
            self.cue_pcm, self.cue_offset = pending, 0
        if self.cue_pcm is not None:
            chunk = self.cue_pcm[self.cue_offset:self.cue_offset + CHUNK_BYTES]
            self.cue_offset += len(chunk)
            if self.cue_offset >= len(self.cue_pcm):
                self.cue_pcm = None
                self.tail_chunks = CUE_TAIL_CHUNKS
            self.cue_sample = channel.push(chunk + bytes(CHUNK_BYTES - len(chunk)), self.cue_sample)
        elif self.effects_held or self.tail_chunks > 0:
            if not self.effects_held:
                self.tail_chunks -= 1
            self.cue_sample = channel.push(SILENCE, self.cue_sample)
        else:
            self.sfx_ending = True
            channel.source.emit('end-of-stream')

    def _feed_music(self, channel):
        pcm = self.music_pcm[self.music_offset:self.music_offset + CHUNK_BYTES]
        self.music_sample = channel.push(pcm, self.music_sample)
        self.music_offset = (self.music_offset + len(pcm)) % len(self.music_pcm)

    def set_levels(self, music, sfx):
        if not self.closed:
            self.channels['music'].volume.set_property('volume', music)
            self.channels['sfx'].volume.set_property('volume', sfx)

    def hold_effects(self, held):
        """Keep the effects stream open (silent between cues) while cues may be needed. Released,
        it ends by itself after any cue still playing, so a finish jingle plays out."""
        channel = self.channels['sfx'] if not self.closed else None
        if channel is None or channel.disabled:
            return
        self.effects_held = held
        if held and (not self.sfx_live or self.sfx_ending):
            self._start_effects()

    def play_cue(self, name):
        channel = self.channels['sfx'] if not self.closed else None
        if channel is None or channel.disabled:
            return
        if not self.sfx_live or self.sfx_ending:
            self._start_effects()
        if self.sfx_live:
            pcm = synth.cue(name)
            channel.cue_bytes = len(pcm)
            self.cue_pending = pcm

    def stop_cues(self):
        if not self.closed:
            self.channels['sfx'].stop()
            self.effects_held = False
            self._reset_effects()

    def music(self, state):
        channel = self.channels['music'] if not self.closed else None
        if channel is None or channel.disabled:
            return
        if state == 'playing':
            channel.start()
            return
        channel.stop()  # Paused keeps the place in the melody; stopped returns to its top.
        self.music_sample = 0  # Each opening of the stream counts time from zero.
        if state == 'stopped':
            self.music_offset = 0

    def shutdown(self):
        if not self.closed:
            self.closed = True
            for channel in self.channels.values():
                channel.close()
