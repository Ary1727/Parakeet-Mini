import os
import queue
import threading
from collections import deque

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.1
SILENCE_LEVEL = 0.01
SILENCE_SECONDS = 0.8
MIN_SPEECH_SECONDS = 0.4
MAX_SEGMENT_SECONDS = 20
PREROLL_BLOCKS = 3
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")


class Segmenter:
    def __init__(
        self,
        sample_rate=SAMPLE_RATE,
        silence_level=SILENCE_LEVEL,
        silence_seconds=SILENCE_SECONDS,
        min_speech_seconds=MIN_SPEECH_SECONDS,
        max_segment_seconds=MAX_SEGMENT_SECONDS,
    ):
        self.silence_level = silence_level
        self.silence_limit = int(silence_seconds * sample_rate)
        self.min_speech = int(min_speech_seconds * sample_rate)
        self.max_segment = int(max_segment_seconds * sample_rate)
        self.preroll = deque(maxlen=PREROLL_BLOCKS)
        self._reset()

    def _reset(self):
        self.chunks = []
        self.total = 0
        self.speech = 0
        self.silence = 0

    def feed(self, block):
        loud = float(np.sqrt(np.mean(np.square(block)))) >= self.silence_level
        if not self.chunks:
            if not loud:
                self.preroll.append(block)
                return None
            for earlier in self.preroll:
                self.chunks.append(earlier)
                self.total += len(earlier)
            self.preroll.clear()
        self.chunks.append(block)
        self.total += len(block)
        if loud:
            self.speech += len(block)
            self.silence = 0
        else:
            self.silence += len(block)
        if self.silence >= self.silence_limit or self.total >= self.max_segment:
            return self.flush()
        return None

    def flush(self):
        if not self.chunks:
            return None
        audio = np.concatenate(self.chunks)
        enough_speech = self.speech >= self.min_speech
        self._reset()
        return audio if enough_speech else None


class Transcriber:
    def __init__(self, emit):
        self.emit = emit
        self.model = None
        self.thread = None
        self.stop_event = threading.Event()
        self.blocks = queue.Queue()

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.blocks = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _on_audio(self, indata, frames, time_info, status):
        self.blocks.put(indata[:, 0].copy())

    def _load_model(self):
        if self.model is None:
            self.emit("status", "Loading speech model (first time can take a while)...")
            self.model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

    def _transcribe(self, audio):
        self.emit("status", "Transcribing...")
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if text:
            self.emit("text", text)
        if not self.stop_event.is_set():
            self.emit("status", "Listening...")

    def _run(self):
        segmenter = Segmenter()
        try:
            self._load_model()
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=int(SAMPLE_RATE * BLOCK_SECONDS),
                callback=self._on_audio,
            ):
                self.emit("status", "Listening...")
                while not self.stop_event.is_set():
                    try:
                        block = self.blocks.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    segment = segmenter.feed(block)
                    if segment is not None:
                        self._transcribe(segment)
            tail = segmenter.flush()
            if tail is not None:
                self._transcribe(tail)
            self.emit("status", "Stopped")
        except Exception as error:
            self.emit("error", f"Speech recognition failed: {error}")
        finally:
            self.emit("finished", None)
