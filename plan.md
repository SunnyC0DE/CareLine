# Careline implementation plan

**Status: approved by the user; implementation and verification in progress.**

## Product and implementation approach

Build a small, open-source clinic receptionist with a Python Pipecat voice pipeline, a browser microphone UI, and a SQLite-backed tool layer. The deployed app will be an educational/demo-ready prototype; it will not be represented as production-ready for real patient data.

The live agent will rely on Pipecat's LLM context and native function calling. The model will decide whether it needs to ask a question, retrieve FAQ text, check availability, book, reschedule, cancel, or escalate. There will be no intent classifier, keyword/regex router, or deterministic action-selection layer. Deterministic code is limited to validating tool arguments, enforcing database constraints, and formatting errors/results.

### Architecture

```text
Browser mic + transcript UI
        │ HTTPS page; WSS audio + RTVI messages
        ▼
Pipecat browser client SDK ── Pipecat Python / FastAPI WebSocket endpoint
                                  │
                                  ├─ VAD + turn detection + interruption handling
                                  ├─ Deepgram streaming STT (default; Groq Whisper option)
                                  ├─ Groq streaming LLM + Pipecat function calling (Gemini option)
                                  ├─ Piper local TTS (default; Groq TTS option)
                                  ├─ SQLite tool layer: appointments, FAQ FTS5, escalation queue
                                  └─ privacy-minimized per-stage latency metrics
```

The default browser transport will be Pipecat's WebSocket client/server transport. It keeps the single-process deployment compatible with a free host that proxies HTTPS/WSS without requiring a separately exposed UDP port. Pipecat's own documentation recommends WebRTC for stronger browser-media behavior, so the README will describe WebSocket's TCP/head-of-line and reconnection trade-offs. No phone or telephony support will be included. The provider and transport boundaries will be isolated so switching to SmallWebRTC for local/self-hosted runs can be a later configuration choice, not a rewrite.

The UI will be a light Vite/TypeScript client served as static assets by the Python app. It will have one prominent microphone connect/disconnect button, connection and listening/speaking states, a compact transcript, and an obvious stop control. Audio and transcript content will not be persisted by default.

### LLM, tools, state, and safety

- Default providers: Pipecat `DeepgramSTTService` for streaming interim recognition, `GroqLLMService` for streaming tool-capable responses, and local `PiperTTSService` for open-source speech output. Provider selection will be through `.env` configuration. Swaps will include Groq Whisper STT, Gemini's OpenAI-compatible chat API, and Groq TTS. Piper requires no API key.
- Conversation context is per active Pipecat session and survives turns through Pipecat's context aggregators. Clinic data is persisted in SQLite; conversational audio/transcripts are not.
- Register exactly these business tools for LLM function calling: `check_available_slots`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `lookup_clinic_info`, and `escalate_to_human`.
- Use typed/validated arguments, ISO clinic-local dates/times, SQLite transactions, and a uniqueness constraint on active appointment slots. Conflicts, unknown references, invalid dates, and invalid names return structured recoverable errors for the model to explain and ask follow-up questions about. Booking requires the LLM tool arguments to indicate the caller has confirmed the proposed date, time, and name. Reschedule/cancel require a generated booking reference plus the caller's name; tools never search or disclose another patient's appointment.
- The clinic FAQ will be stored in SQLite and retrieved through FTS5. The LLM will be instructed to use only text returned by `lookup_clinic_info`; a no-match result directs it to say “I don't know from the clinic information I have.” Sample hours, services, fees, and policies will be fictitious and clearly marked for replacement.
- The receptionist will not diagnose, recommend treatment, or provide medical advice. The system prompt directs emergency callers to local emergency services/emergency care immediately and calls `escalate_to_human`; out-of-scope requests also use that tool. Escalation will be stored as a pending follow-up record, not represented as a live staff connection or emergency dispatch. No general patient lookup tool will be exposed.
- The sample app will log stage names, elapsed times, provider errors, and tool names, not raw audio, full transcripts, patient names, or tool payloads. This is data minimization, not a complete privacy/security program.

### Repository structure

```text
backend/careline/
  app.py                 FastAPI HTTP/WSS app and static UI serving
  voice/pipeline.py      Pipecat transport, services, context, tools, lifecycle
  voice/metrics.py       STT/LLM/TTS/first-audio measurements and summaries
  providers.py           Config-driven STT/LLM/TTS factories
  tools/appointments.py  Slot, booking, reschedule and cancellation tool logic
  tools/clinic_info.py   FAQ retrieval tool
  tools/escalation.py    Human-follow-up queue tool
  db.py                  SQLite schema, transactions, sample seed data
  schemas.py             Validated tool argument models
  config.py              Environment configuration
web/                     Small Vite TypeScript/HTML microphone client
clinic_faq.json          Fictional editable FAQ seed content
tests/                   Pytest coverage for validation, tools, and SQLite logic
eval/scenarios.json      At least 30 scripted conversation/tool-trace fixtures
eval/run_eval.py         Offline replay scorer; no provider credentials needed
eval/results.csv         Saved scenario-level scores and tool correctness
requirements.txt         Python dependencies
.env.example             Variable names and safe sample defaults only
.gitignore               Excludes .env, SQLite data, caches, build outputs
render.yaml              Optional Docker-free Render free-host service recipe
README.md                Setup, architecture, keys, measured results, caveats
plan.md                  This approved implementation plan
TODO.md                  Outcome-based progress after plan approval
```

## Design direction

Three uncommon alternatives considered: **clinical field-notes console** (0.07), **warm modern reception ledger** (0.04), and **monochrome waveform instrument** (0.02). Choose **warm modern reception ledger**: quietly reassuring, highly legible, and focused on one human interaction rather than a busy dashboard.

- **Design movement:** contemporary editorial service design with restrained Swiss typography and a soft, tactile paper-like canvas.
- **Core principles:** one clear action at a time; readable at arm's length; calm rather than clinical-cold; status is explicit without exposing patient information.
- **Color philosophy:** warm ivory and deep ink support long reading; muted eucalyptus communicates a ready state; a restrained rust accent is reserved for urgent notices and the microphone affordance.
- **Layout paradigm:** an asymmetric two-part composition, with conversation and microphone as the primary column and a narrow clinic-information rail on wide screens; the rail collapses below the conversation on mobile.
- **Signature elements:** a thin “open door” line motif around the mic control; small appointment-slot pills; a subtle pulse ring only while listening.
- **Interaction philosophy:** click once to start, click again to stop; explain microphone permission before the browser prompt; display live transcript text and a clear interruption state; no auto-book action before spoken confirmation.
- **Animation:** gentle 180–240 ms opacity/scale transitions; listening pulse follows the active speech state and stops immediately on barge-in; respect `prefers-reduced-motion`.
- **Typography system:** system UI sans for controls/body; a restrained editorial serif for the Careline wordmark and key heading; tabular numerals for appointment times. Avoid loading large font assets.
- **Brand essence:** “A small clinic's front desk, made easier to reach”; personality: calm, clear, respectful.
- **Brand voice:** short, warm, plainspoken, never clinical or overconfident. Examples: “Tell me what would work for you.” “I can check that, or ask the clinic team to follow up.”
- **Wordmark & logo:** a compact line-art doorway with a small speech mark as a custom CSS/SVG monogram beside “careline,” not a default-font logo.
- **Signature brand color:** muted eucalyptus, used consistently for the active/ready state.

## Dependencies and resource decisions

Use Python 3.12 and Node 22.12+ (the verified workspace has Python 3.12.3 and Node 22.13). No Docker, GPU, local LLM, vector database, external database, MLOps stack, or paid orchestration service. SQLite FTS5 avoids embedding downloads and keeps retrieval CPU/memory-light. VAD will use Pipecat's local Silero analyzer; Piper will run on CPU. External LLM/STT services keep the clinic's small laptop from needing to host a large model, but provider quotas, network latency, and provider data handling still apply.

## Evaluation and observability

The evaluation suite will contain at least 30 scripted, text-driven scenarios covering completed/incomplete bookings, confirmation, rescheduling, cancellations, slot conflicts, malformed/invalid dates, unknown FAQ requests, barge-in recovery, emergencies, and escalation. An offline replay harness will execute fixture-specified tool calls against a fresh temporary SQLite database, score task success and expected-vs-actual tool-call correctness, and save every row plus totals to `eval/results.csv`.

This is a reproducible test of tool/database outcomes and recovery contracts, not a test of the LLM's ability to choose the right function. A true LLM decision-quality evaluation needs provider credentials and model calls; it will be reported separately and not fabricated. Pytest will use isolated temporary databases, never a development or hosted clinic database.

Latency instrumentation will print per-turn STT, LLM, TTS, and speech-end-to-first-audio values. The README will include a table with observed results only. Since no Groq or Deepgram API keys have been supplied, provider-backed latency will remain “not measured” unless a real end-to-end run is completed with credentials; unit tests can validate that metric events are recorded, but not substitute synthetic values for service latency.

## Deployment, secrets, and material limitations

The Docker-free deployment example will target a Render Free Web Service using its native Python runtime and one HTTPS/WSS listener. The default local development path will run the Python service and Vite UI without containers. Current Render Free documentation says free web services use an ephemeral filesystem; local SQLite changes can be lost on spin-down, restart, or redeploy. Therefore the Render deployment is only for synthetic-data demonstration and testing, not actual clinic appointment records. The same is true of the unprotected demo and unverified escalation queue. A real clinic must choose a host with durable storage, authentication/authorization, backups, appropriate privacy/security controls, and qualified review before using real patient data. Do not use a personal 4 GB laptop as an internet-facing production host.

Default configuration requires exactly two API keys: `GROQ_API_KEY` for the Groq LLM and `DEEPGRAM_API_KEY` for streaming STT. Piper TTS is local and needs no key. The README will give the official account/key URLs. Optional provider swaps add `GEMINI_API_KEY` when `LLM_PROVIDER=gemini`, or reuse `GROQ_API_KEY` for Groq STT/TTS. The app will not request billing credentials. Deepgram's current public pricing page describes a free $200 credit with no credit card required; credits are finite, so the app will use no paid service and the operator should not add a payment method for this demo. Provider limits can change and must be checked in the provider dashboard.

## Sources consulted for the design

- Pipecat WebSocket client, server transport and runtime runner: <https://docs.pipecat.ai/api-reference/client/js/transports/websocket>, <https://docs.pipecat.ai/api-reference/server/services/transport/fastapi-websocket>, <https://docs.pipecat.ai/api-reference/server/utilities/runner/guide>
- Pipecat function calling, context, VAD and interruption behavior: <https://docs.pipecat.ai/pipecat/learn/function-calling>, <https://docs.pipecat.ai/pipecat/learn/context-management>, <https://docs.pipecat.ai/pipecat/learn/speech-input>, <https://docs.pipecat.ai/pipecat/fundamentals/interruptions>
- Pipecat Groq LLM, Deepgram STT, Groq Whisper, and Piper services: <https://docs.pipecat.ai/api-reference/server/services/llm/groq>, <https://docs.pipecat.ai/api-reference/server/services/stt/deepgram>, <https://docs.pipecat.ai/api-reference/server/services/stt/groq>, <https://docs.pipecat.ai/api-reference/server/services/tts/piper>
- Official Groq model use, speech endpoints and rate limits: <https://console.groq.com/docs/tool-use>, <https://console.groq.com/docs/speech-to-text>, <https://console.groq.com/docs/rate-limits>
- Gemini OpenAI compatibility and tool calling: <https://ai.google.dev/gemini-api/docs/openai>
- Deepgram no-cost account credit: <https://deepgram.com/pricing>
- Render native web services and free tier limitations: <https://render.com/docs/web-services>, <https://render.com/docs/free>

The user approved this plan as written before implementation. The README and evaluation results will distinguish tested offline tool behavior from provider-backed voice behavior that cannot be verified without credentials.
