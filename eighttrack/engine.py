"""PortAudio transport. Device callbacks never access desktop widgets or files."""

import math

import numpy as np
import sounddevice as sd
from scipy.signal import correlate, correlation_lags

from eighttrack.model import MAX_FRAMES, SAMPLE_RATE, Song, Track


BLOCK_SIZE = 512


def estimate_recording_offset(reference: np.ndarray, recorded: np.ndarray) -> int:
    if reference.ndim != 1 or recorded.shape != reference.shape or not np.isfinite(recorded).all():
        raise ValueError("Invalid loopback recording.")
    if np.max(np.abs(recorded)) >= 0.99:
        raise ValueError("The calibration input clipped. Reduce interface gain and retry.")
    correlation = correlate(recorded, reference, mode="full", method="fft")
    lags = correlation_lags(len(recorded), len(reference))
    valid = (lags >= 0) & (lags <= SAMPLE_RATE * 2)
    strengths = np.abs(correlation[valid])
    peak = int(np.argmax(strengths))
    energy = float(np.linalg.norm(reference) * np.linalg.norm(recorded))
    if energy < 1e-8 or strengths[peak] / energy < 0.2:
        raise ValueError("No reliable loopback signal. Check the cable and selected channels.")
    return int(lags[valid][peak])


class AudioEngine:
    def __init__(self, song: Song):
        self.song = song
        self.position = 0
        self.mode = "stopped"
        self.stream = None
        self.input_device: int | None = None
        self.output_device: int | None = None
        self.input_channel = 0
        self.output_channel = 0
        self.input_gain = 1.0
        self.metronome = False
        self.input_peak = 0.0
        self.output_peak = 0.0
        self.track_peaks = [0.0] * len(self.song.tracks)
        self.clipped = False
        self.warning = ""
        self.finished = False
        self.record_track: int | None = None
        self._monitor_track: int | None = None
        self.record_start = 0
        self.recorded_frames = 0
        self.record_buffer = np.zeros(0, dtype=np.float32)
        self._record_channels = 1
        self.recording_offset = 0
        self.count_remaining = 0
        self.count_elapsed = 0
        self.record_end = MAX_FRAMES
        self._punch = False
        self._offset = 0
        self._fraction = 0.0

    @property
    def monitor_track(self) -> int | None:
        return self._monitor_track

    @monitor_track.setter
    def monitor_track(self, track: int | None) -> None:
        if track is not None and not 0 <= track < len(self.song.tracks):
            raise ValueError("Select one track to monitor.")
        if self._monitor_track != track:
            self._monitor_track = track
            self.update_monitoring()

    @property
    def running(self) -> bool:
        return self.mode != "stopped"

    def update_monitoring(self) -> None:
        if self.mode != "stopped":
            return
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
                self.stream = None
        if self._monitor_track is None or not 0 <= self._monitor_track < len(self.song.tracks):
            self.input_peak = self.output_peak = 0.0
            return
        track = self.song.tracks[self._monitor_track]
        channels = track.channels
        try:
            self.stream = sd.Stream(
                samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, dtype="float32",
                channels=(self.input_channel + channels, self.output_channel + 2),
                device=(self.input_device, self.output_device), callback=self._monitor_callback,
            )
            self.stream.start()
        except Exception as error:
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self.warning = f"Could not start input monitoring: {error}"

    def calibrate_latency(self) -> int:
        if self.running:
            raise ValueError("Stop before calibrating.")
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
                self.stream = None
        try:
            reference = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
            burst = np.random.default_rng(8).uniform(-0.03, 0.03, SAMPLE_RATE // 20).astype(np.float32)
            reference[SAMPLE_RATE // 10:SAMPLE_RATE // 10 + len(burst)] = burst
            output = np.column_stack((reference, reference))
            recorded = sd.playrec(output, samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                  device=(self.input_device, self.output_device),
                                  input_mapping=[self.input_channel + 1],
                                  output_mapping=[self.output_channel + 1, self.output_channel + 2], blocking=True)
            return estimate_recording_offset(reference, recorded[:, 0])
        finally:
            self.update_monitoring()

    def seek(self, frame: int) -> None:
        if self.running:
            raise ValueError("Stop the transport before moving the playhead.")
        self.position = max(0, min(int(frame), max(MAX_FRAMES, self.song.playback_length) - 1))

    def start(self, record_track: int | None = None) -> None:
        if self.running:
            return
        if record_track is not None and not 0 <= record_track < len(self.song.tracks):
            raise ValueError("Select one track to record.")
        if record_track is not None and self.position >= MAX_FRAMES:
            raise ValueError("Move the playhead before the ten-minute recording limit.")
        if self.song.loop or (record_track is not None and self.song.punch):
            self.song.tape_range()
        if record_track is None and self.song.loop:
            if not self.song.marker_a <= self.position < self.song.marker_b:
                self.position = self.song.marker_a
        if record_track is None and not self.song.loop and self.position >= self.song.playback_length:
            raise ValueError("The playhead is at the end. Rewind or record a new take.")
        if record_track is not None and self.song.tape_speed != 1:
            raise ValueError("Set tape speed to 100% before recording.")
        self._punch = record_track is not None and self.song.punch
        if self._punch and self.position > self.song.marker_a:
            self.position = self.song.marker_a

        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
                self.stream = None

        exclude = None if self._punch else (record_track if record_track is not None else self._monitor_track)
        self.song.prepare_effects(exclude=exclude)
        self.record_track = record_track
        self.record_start = self.song.marker_a if self._punch else self.position
        self.record_end = self.song.marker_b if self._punch else MAX_FRAMES
        self._offset = max(0, min(int(self.recording_offset), SAMPLE_RATE * 2))
        self.count_remaining = round(self.song.count_in * SAMPLE_RATE * 60 / self.song.bpm) if record_track is not None else 0
        self.count_elapsed = 0
        self._fraction = 0.0
        self.recorded_frames = 0
        self.warning = ""
        self.finished = False
        self.clipped = False
        self.input_peak = self.output_peak = 0.0
        self.mode = "recording" if record_track is not None else "playing"
        try:
            if record_track is None:
                if self._monitor_track is not None:
                    mon_channels = self.song.tracks[self._monitor_track].channels
                    self.stream = sd.Stream(
                        samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, dtype="float32",
                        channels=(self.input_channel + mon_channels, self.output_channel + 2),
                        device=(self.input_device, self.output_device), callback=self._play_monitor_callback,
                        finished_callback=self._finished,
                    )
                else:
                    self.stream = sd.OutputStream(
                        samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, dtype="float32",
                        channels=self.output_channel + 2, device=self.output_device, callback=self._play_callback,
                        finished_callback=self._finished,
                    )
            else:
                self._record_channels = self.song.tracks[record_track].channels
                length = self.record_end - self.record_start
                shape = length if self._record_channels == 1 else (length, self._record_channels)
                self.record_buffer = np.empty(shape, dtype=np.float32)
                self.stream = sd.Stream(
                    samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, dtype="float32",
                    channels=(self.input_channel + self._record_channels, self.output_channel + 2),
                    device=(self.input_device, self.output_device), callback=self._record_callback,
                    finished_callback=self._finished,
                )
            self.stream.start()
        except Exception:
            if self.stream is not None:
                self.stream.close()
            self.stream = None
            self.mode = "stopped"
            self.record_buffer = np.zeros(0, dtype=np.float32)
            self.record_track = None
            self.count_remaining = 0
            self._punch = False
            self.update_monitoring()
            raise

    def stop(self) -> tuple[int, np.ndarray] | None:
        """Finish a take on the main thread and return the previous audio for undo."""
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
                self.stream = None
        undo = None
        if self.record_track is not None and self.recorded_frames:
            track = self.song.tracks[self.record_track]
            undo = (self.record_track, track.audio.copy())
            track.write(self.record_start, self.record_buffer[:self.recorded_frames])
        self.record_track = None
        self.recorded_frames = 0
        self.record_buffer = np.zeros(0, dtype=np.float32)
        self.count_remaining = 0
        self.mode = "stopped"
        self.finished = False
        self.input_peak = self.output_peak = 0.0
        self.track_peaks = [0.0] * len(self.song.tracks)
        self.update_monitoring()
        return undo

    def _finished(self) -> None:
        self.finished = True

    def _render_monitor(self, track: Track, samples: np.ndarray) -> np.ndarray:
        has_solo = any(t.solo for t in self.song.tracks)
        if track.muted or (has_solo and not track.solo):
            return np.zeros((len(samples), 2), dtype=np.float32)
        mon = samples * track.volume * self.song.master
        if track.channels == 1:
            angle = (track.pan + 1) * math.pi / 4
            left_gain, right_gain = math.cos(angle), math.sin(angle)
            left = mon * left_gain
            right = mon * right_gain
        else:
            left_gain = math.cos(max(0, track.pan) * math.pi / 2)
            right_gain = math.cos(min(0, track.pan) * math.pi / 2)
            left = mon[:, 0] * left_gain
            right = mon[:, 1] * right_gain
        return np.column_stack((left, right)).astype(np.float32)

    def _render(self, frames: int) -> np.ndarray:
        exclude = self.record_track if self.record_track is not None else self._monitor_track
        if self._punch and not self.record_start <= self.position < self.record_end:
            exclude = None
        block, track_peaks = self.song.mix_with_peaks(self.position, frames, exclude=exclude)
        self.track_peaks = track_peaks
        active_mon = self.record_track if self.record_track is not None else self._monitor_track
        if active_mon is not None and 0 <= active_mon < len(self.track_peaks):
            self.track_peaks[active_mon] = self.input_peak
        if self.metronome:
            block += self._click(self.position, frames)[:, None]
        self.output_peak = float(np.max(np.abs(block))) if frames else 0.0
        self.clipped = self.clipped or self.output_peak >= 1
        return np.clip(block, -1, 1)

    def _click(self, position: int, frames: int) -> np.ndarray:
        beat_frames = round(SAMPLE_RATE * 60 / self.song.bpm)
        phase = (np.arange(frames) + position) % beat_frames
        envelope = np.maximum(0, 1 - phase / (SAMPLE_RATE * 0.025))
        return np.sin(2 * np.pi * 1200 * phase / SAMPLE_RATE) * envelope * 0.18 * self.song.master

    def _monitor_callback(self, incoming, output, frames, timing, status) -> None:
        output.fill(0)
        out_slice = output[:, self.output_channel:self.output_channel + 2]
        try:
            if status:
                self.warning = str(status)
            if self._monitor_track is None or not 0 <= self._monitor_track < len(self.song.tracks):
                self.input_peak = self.output_peak = 0.0
                return
            track = self.song.tracks[self._monitor_track]
            channels = track.channels
            if channels == 1:
                samples = incoming[:, self.input_channel] * self.input_gain
            else:
                samples = incoming[:, self.input_channel:self.input_channel + channels] * self.input_gain
            self.input_peak = float(np.max(np.abs(samples))) if frames else 0.0
            self.clipped = self.clipped or self.input_peak >= 1
            if self._monitor_track is not None and 0 <= self._monitor_track < len(self.track_peaks):
                self.track_peaks[self._monitor_track] = self.input_peak
            monitored = self._render_monitor(track, samples)
            out_slice[:] = np.clip(monitored, -1, 1)
            self.output_peak = float(np.max(np.abs(out_slice))) if frames else 0.0
            self.clipped = self.clipped or self.output_peak >= 1
        except Exception as error:
            self.warning = f"Monitoring stopped: {error}"
            raise sd.CallbackAbort from error

    def _play_callback(self, output, frames, timing, status) -> None:
        output.fill(0)
        out_slice = output[:, self.output_channel:self.output_channel + 2]
        try:
            if status:
                self.warning = str(status)
            written = 0
            end = self.song.marker_b if self.song.loop else self.song.playback_length
            while written < frames and self.position < end:
                cursor = self.position + self._fraction
                count = min(frames - written, math.ceil((end - cursor) / self.song.tape_speed))
                if self.song.tape_speed == 1:
                    block = self._render(count)
                else:
                    block, track_peaks = self.song.mix_tape_with_peaks(cursor, count)
                    self.track_peaks = track_peaks
                    if self.metronome:
                        phase = (cursor + np.arange(count) * self.song.tape_speed).astype(np.int64)
                        beat = round(SAMPLE_RATE * 60 / self.song.bpm)
                        phase %= beat
                        envelope = np.maximum(0, 1 - phase / (SAMPLE_RATE * 0.025))
                        block += (np.sin(2 * np.pi * 1200 * phase / SAMPLE_RATE) * envelope * 0.18 * self.song.master)[:, None]
                out_slice[written:written + count] = np.clip(block, -1, 1)
                self.clipped = self.clipped or bool(np.any(np.abs(block) >= 1))
                cursor += count * self.song.tape_speed
                self.position = min(end, int(cursor))
                self._fraction = cursor - int(cursor)
                written += count
                if self.song.loop and self.position >= end:
                    self.position = self.song.marker_a
                    self._fraction = 0.0
            self.output_peak = float(np.max(np.abs(out_slice))) if frames else 0.0
        except Exception as error:
            self.warning = f"Playback stopped: {error}"
            raise sd.CallbackAbort from error
        if not self.song.loop and self.position >= self.song.playback_length:
            raise sd.CallbackStop

    def _play_monitor_callback(self, incoming, output, frames, timing, status) -> None:
        output.fill(0)
        out_slice = output[:, self.output_channel:self.output_channel + 2]
        try:
            if status:
                self.warning = str(status)
            track = self.song.tracks[self._monitor_track] if self._monitor_track is not None else None
            if track is not None:
                channels = track.channels
                if channels == 1:
                    samples = incoming[:, self.input_channel] * self.input_gain
                else:
                    samples = incoming[:, self.input_channel:self.input_channel + channels] * self.input_gain
                self.input_peak = float(np.max(np.abs(samples))) if frames else 0.0
                self.clipped = self.clipped or self.input_peak >= 1
            else:
                samples = None
                self.input_peak = 0.0
            written = 0
            end = self.song.marker_b if self.song.loop else self.song.playback_length
            while written < frames and self.position < end:
                cursor = self.position + self._fraction
                count = min(frames - written, math.ceil((end - cursor) / self.song.tape_speed))
                if self.song.tape_speed == 1:
                    block, track_peaks = self.song.mix_with_peaks(self.position, count, exclude=self._monitor_track)
                    self.track_peaks = track_peaks
                    if self._monitor_track is not None and 0 <= self._monitor_track < len(self.track_peaks):
                        self.track_peaks[self._monitor_track] = self.input_peak
                    if self.metronome:
                        block += self._click(self.position, count)[:, None]
                else:
                    block, track_peaks = self.song.mix_tape_with_peaks(cursor, count, exclude=self._monitor_track)
                    self.track_peaks = track_peaks
                    if self._monitor_track is not None and 0 <= self._monitor_track < len(self.track_peaks):
                        self.track_peaks[self._monitor_track] = self.input_peak
                    if self.metronome:
                        phase = (cursor + np.arange(count) * self.song.tape_speed).astype(np.int64)
                        beat = round(SAMPLE_RATE * 60 / self.song.bpm)
                        phase %= beat
                        envelope = np.maximum(0, 1 - phase / (SAMPLE_RATE * 0.025))
                        block += (np.sin(2 * np.pi * 1200 * phase / SAMPLE_RATE) * envelope * 0.18 * self.song.master)[:, None]
                if track is not None and samples is not None:
                    block += self._render_monitor(track, samples[written:written + count])
                out_slice[written:written + count] = np.clip(block, -1, 1)
                self.clipped = self.clipped or bool(np.any(np.abs(block) >= 1))
                cursor += count * self.song.tape_speed
                self.position = min(end, int(cursor))
                self._fraction = cursor - int(cursor)
                written += count
                if self.song.loop and self.position >= end:
                    self.position = self.song.marker_a
                    self._fraction = 0.0
            if written < frames and track is not None and samples is not None:
                mon = self._render_monitor(track, samples[written:])
                out_slice[written:] = np.clip(mon, -1, 1)
            self.output_peak = float(np.max(np.abs(out_slice))) if frames else 0.0
            self.clipped = self.clipped or self.output_peak >= 1
        except Exception as error:
            self.warning = f"Playback stopped: {error}"
            raise sd.CallbackAbort from error
        if not self.song.loop and self.position >= self.song.playback_length:
            raise sd.CallbackStop

    def _record_callback(self, incoming, output, frames, timing, status) -> None:
        output.fill(0)
        out_slice = output[:, self.output_channel:self.output_channel + 2]
        try:
            if status:
                self.warning = str(status)
            if self._record_channels == 1:
                samples = incoming[:, self.input_channel] * self.input_gain
            else:
                samples = incoming[:, self.input_channel:self.input_channel + self._record_channels] * self.input_gain
            self.input_peak = float(np.max(np.abs(samples))) if frames else 0.0
            self.clipped = self.clipped or self.input_peak >= 1
            if self.record_track is not None and 0 <= self.record_track < len(self.track_peaks):
                self.track_peaks[self.record_track] = self.input_peak
            consumed = min(frames, self.count_remaining)
            if consumed:
                out_slice[:consumed] = self._click(self.count_elapsed, consumed)[:, None]
                if self.record_track is not None:
                    track = self.song.tracks[self.record_track]
                    out_slice[:consumed] += self._render_monitor(track, samples[:consumed])
                self.count_elapsed += consumed
                self.count_remaining -= consumed
            capture_start = self.record_start + self._offset
            capture_end = self.record_end + self._offset
            while consumed < frames and self.position < capture_end:
                boundaries = [capture_end]
                if self._punch:
                    boundaries.extend(boundary for boundary in (self.record_start, self.record_end)
                                      if boundary > self.position)
                count = min(frames - consumed, min(boundaries) - self.position)
                block = self._render(count)
                in_record_region = (not self._punch) or (self.record_start <= self.position < self.record_end)
                if in_record_region and self.record_track is not None:
                    track = self.song.tracks[self.record_track]
                    block += self._render_monitor(track, samples[consumed:consumed + count])
                out_slice[consumed:consumed + count] = np.clip(block, -1, 1)
                first = max(self.position, capture_start)
                last = min(self.position + count, capture_end)
                if first < last:
                    source = consumed + first - self.position
                    target = first - capture_start
                    self.record_buffer[target:target + last - first] = np.clip(samples[source:source + last - first], -1, 1)
                    self.recorded_frames = target + last - first
                self.position += count
                consumed += count
            self.output_peak = float(np.max(np.abs(out_slice))) if frames else 0.0
            self.clipped = self.clipped or self.output_peak >= 1
        except Exception as error:
            self.warning = f"Recording stopped: {error}"
            raise sd.CallbackAbort from error
        if self.position >= self.record_end + self._offset:
            raise sd.CallbackStop