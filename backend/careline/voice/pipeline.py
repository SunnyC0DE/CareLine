from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import WebSocket
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from backend.careline.config import Settings
from backend.careline.db import ClinicStore
from backend.careline.providers import SYSTEM_PROMPT, build_llm, build_stt, build_tts
from backend.careline.tools.appointment_handlers import make_appointment_tools
from backend.careline.tools.appointments import AppointmentTools
from backend.careline.tools.clinic_info import make_lookup_clinic_info
from backend.careline.tools.escalation import make_escalate_to_human
from backend.careline.voice.metrics import LatencyFrameProcessor, LatencyRecorder

logger = logging.getLogger("careline.voice")


def build_tools(store: ClinicStore, settings: Settings):
    appointment_tools = AppointmentTools(store, settings)
    return [
        *make_appointment_tools(appointment_tools),
        make_lookup_clinic_info(store),
        make_escalate_to_human(store),
    ]


async def run_voice_session(websocket: WebSocket, settings: Settings, store: ClinicStore) -> None:
    await websocket.accept()
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=ProtobufFrameSerializer(),
        ),
    )

    llm = build_llm(settings)
    stt = build_stt(settings)
    tts = build_tts(settings)
    metrics = LatencyRecorder()
    clinic_date = datetime.now(ZoneInfo(settings.clinic_timezone)).strftime("%A, %Y-%m-%d")
    context = LLMContext(
        messages=[
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT.format(clinic_name=settings.clinic_name)
                    + f"\n\nToday's date in the clinic timezone ({settings.clinic_timezone}) is {clinic_date}. "
                    "Use it to resolve relative dates, then confirm the exact date with the caller."
                ),
            },
            {
                "role": "user",
                "content": "A new caller has just connected. Greet them briefly and ask how you can help.",
            },
        ],
        tools=build_tools(store, settings),
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            LatencyFrameProcessor(metrics),
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=False,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
        ),
        idle_timeout_secs=900,
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client) -> None:
        logger.info("voice_session_connected")
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client) -> None:
        logger.info("voice_session_disconnected")
        metrics.flush_unfinished()
        metrics.summary()
        await runner.cancel()

    await runner.run()
    metrics.flush_unfinished()
    metrics.summary()
