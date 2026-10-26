import logging
import time

from backend.careline.voice.metrics import LatencyRecorder


def test_latency_recorder_aggregates_tool_round_trips_and_logs_summary(caplog):
    recorder = LatencyRecorder()
    recorder.start_turn()
    time.sleep(0.002)
    recorder.on_transcript()

    recorder.llm_start()
    time.sleep(0.002)
    recorder.llm_end()
    first_llm_segment = recorder.turn.llm_ms

    recorder.llm_start()
    time.sleep(0.002)
    recorder.llm_end()
    assert recorder.turn.llm_ms > first_llm_segment

    recorder.tts_start()
    time.sleep(0.002)
    recorder.first_audio()
    time.sleep(0.002)
    recorder.tts_end()

    assert len(recorder.completed) == 1
    row = recorder.completed[0]
    assert row["stt_ms_from_first_voice"] is not None
    assert row["llm_ms"] is not None
    assert row["tts_ms"] is not None
    assert row["time_to_first_audio_ms_after_transcript"] is not None
    assert row["total_ms_from_first_voice_to_first_audio"] is not None

    with caplog.at_level(logging.INFO, logger="careline.metrics"):
        recorder.summary()
    assert "latency_summary turns=1" in caplog.text
