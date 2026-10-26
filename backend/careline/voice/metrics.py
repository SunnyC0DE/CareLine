from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from statistics import mean

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSAudioRawFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

logger = logging.getLogger("careline.metrics")


@dataclass
class TurnTiming:
    started_at: float
    transcript_at: float | None = None
    stt_ms: float | None = None
    llm_started_at: float | None = None
    llm_ms: float | None = None
    tts_started_at: float | None = None
    tts_ms: float | None = None
    first_audio_ms: float | None = None
    interrupted: bool = False


class LatencyRecorder:
    """Measure stages without recording audio, transcript text, names, or tool arguments."""

    def __init__(self) -> None:
        self.turn: TurnTiming | None = None
        self.completed: list[dict[str, float | bool | None]] = []
        self.turn_number = 0

    def start_turn(self) -> None:
        self.flush_unfinished()
        self.turn_number += 1
        self.turn = TurnTiming(started_at=time.perf_counter())

    def on_transcript(self) -> None:
        if self.turn is None:
            self.start_turn()
        assert self.turn is not None
        now = time.perf_counter()
        self.turn.transcript_at = now
        self.turn.stt_ms = round((now - self.turn.started_at) * 1000, 1)

    def llm_start(self) -> None:
        if self.turn is None:
            self.start_turn()
        assert self.turn is not None
        self.turn.llm_started_at = time.perf_counter()

    def llm_end(self) -> None:
        if self.turn is None or self.turn.llm_started_at is None:
            return
        elapsed_ms = (time.perf_counter() - self.turn.llm_started_at) * 1000
        self.turn.llm_ms = round((self.turn.llm_ms or 0.0) + elapsed_ms, 1)
        self.turn.llm_started_at = None

    def tts_start(self) -> None:
        if self.turn is None:
            self.start_turn()
        assert self.turn is not None
        self.turn.tts_started_at = time.perf_counter()

    def first_audio(self) -> None:
        if self.turn is None or self.turn.first_audio_ms is not None:
            return
        now = time.perf_counter()
        baseline = self.turn.transcript_at or self.turn.started_at
        self.turn.first_audio_ms = round((now - baseline) * 1000, 1)

    def tts_end(self) -> None:
        if self.turn is None:
            return
        if self.turn.tts_started_at is not None:
            self.turn.tts_ms = round((time.perf_counter() - self.turn.tts_started_at) * 1000, 1)
        self.flush()

    def interrupt(self) -> None:
        if self.turn is not None:
            self.turn.interrupted = True

    def _row(self) -> dict[str, float | bool | None] | None:
        if self.turn is None:
            return None
        return {
            "turn": float(self.turn_number),
            "stt_ms_from_first_voice": self.turn.stt_ms,
            "llm_ms": self.turn.llm_ms,
            "tts_ms": self.turn.tts_ms,
            "time_to_first_audio_ms_after_transcript": self.turn.first_audio_ms,
            "total_ms_from_first_voice_to_first_audio": (
                round((self.turn.first_audio_ms or 0) + (self.turn.stt_ms or 0), 1)
                if self.turn.first_audio_ms is not None or self.turn.stt_ms is not None
                else None
            ),
            "interrupted": self.turn.interrupted,
        }

    def flush(self) -> None:
        row = self._row()
        if row is not None:
            self.completed.append(row)
            logger.info("turn_latency %s", row)
        self.turn = None

    def flush_unfinished(self) -> None:
        if self.turn is not None:
            self.flush()

    def summary(self) -> None:
        if not self.completed:
            logger.info("latency_summary turns=0")
            return
        names = (
            "stt_ms_from_first_voice",
            "llm_ms",
            "tts_ms",
            "time_to_first_audio_ms_after_transcript",
            "total_ms_from_first_voice_to_first_audio",
        )
        fields = []
        for name in names:
            values: list[float] = []
            for row in self.completed:
                value = row[name]
                if isinstance(value, float):
                    values.append(value)
            fields.append(f"{name}_avg={mean(values):.1f}" if values else f"{name}_avg=n/a")
        logger.info("latency_summary turns=%d %s", len(self.completed), " ".join(fields))


class LatencyFrameProcessor(FrameProcessor):
    def __init__(self, recorder: LatencyRecorder) -> None:
        super().__init__(name="careline_latency")
        self.recorder = recorder

    async def process_frame(
        self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM
    ) -> None:
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, UserStartedSpeakingFrame):
                self.recorder.start_turn()
            elif isinstance(frame, TranscriptionFrame):
                self.recorder.on_transcript()
            elif isinstance(frame, LLMFullResponseStartFrame):
                self.recorder.llm_start()
            elif isinstance(frame, LLMFullResponseEndFrame):
                self.recorder.llm_end()
            elif isinstance(frame, TTSStartedFrame):
                self.recorder.tts_start()
            elif isinstance(frame, TTSAudioRawFrame):
                self.recorder.first_audio()
            elif isinstance(frame, TTSStoppedFrame):
                self.recorder.tts_end()
            elif isinstance(frame, InterruptionFrame):
                self.recorder.interrupt()
        await self.push_frame(frame, direction)
