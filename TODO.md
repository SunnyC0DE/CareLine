# Careline delivery outcomes

## 1. LLM-led receptionist and session context
- [x] Build a real voice receptionist that answers clinic questions and can book, reschedule, and cancel appointments.
- [x] Do not build an intent-classifier or rule-based bot. Do not use if/else, regex, or keyword routing to decide what to do. The LLM must decide the next action through function/tool calling, and keep conversation state across turns.
- [ ] Live LLM decisions and voice conversations were not exercised because no API credentials or real microphone/browser audio test were available; see README's test/evaluation limits.

## 2. Open-source, free-tier, browser voice architecture
- [x] Use only free tiers and open-source tools. Do not use paid services or no-code voice platforms (including Vapi, Retell, or ElevenLabs Agents). Default app providers are Groq, Deepgram free credit, and local Piper; no paid credentials or billing are configured.
- [x] Use Pipecat (Python) for real-time orchestration. The client is browser-based WebSocket with a microphone control; no phone/telephony is included.
- [x] Use Groq or Gemini free tier for the LLM with tool calling; use Groq Whisper or Deepgram free credit for STT; use a free-tier or open-source TTS. Make every provider swappable through configuration. Provider adapters construct successfully; real external provider requests remain untested.

## 3. Validated appointment, clinic-information, and escalation tools
- [x] Provide LLM-callable tools named `check_available_slots`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `lookup_clinic_info`, and `escalate_to_human`.
- [x] Store appointment and clinic tool data in SQLite. Validate tool arguments and handle errors such as a slot being taken or an invalid date so the agent can recover by asking the caller.
- [x] Confirm the date, time, and name before booking. Prevent booking conflicts and support rescheduling and cancellation without exposing another patient's data.
- [x] Document that confirmation is prompt/model-dependent: the tool rejects a false confirmation flag but does not independently verify spoken caller agreement.

## 4. FAQ retrieval and grounded answers
- [x] Build a RAG tool over a sample clinic FAQ covering hours, services, fees, and policies.
- [x] Answer only from retrieved text and say “I don't know” otherwise.

## 5. Voice interaction, safety, and future languages
- [x] Support streaming responses, interruption handling (barge-in), natural turn-taking with VAD, and short spoken-style replies. Implemented with Pipecat's streaming services, VAD and interruption-capable pipeline; live acoustic barge-in was not tested.
- [x] Provide no medical advice. Escalate emergencies and out-of-scope requests. Never reveal or invent patient data. Escalation only records a pending follow-up; it is not live staff contact or emergency dispatch.
- [x] Design so Hindi/Punjabi can be added later, but ship English first.

## 6. Observability and evaluation artifacts
- [x] Log per-turn latency for STT, LLM, TTS, and total time to first audio, and print a summary. Latency recorder is unit-tested; no live voice latency values are reported because no end-to-end audio session ran.
- [x] Create an evaluation set of at least 30 scripted test conversations (text-driven is fine) covering booking, rescheduling, cancellation, conflicts, unknown questions, interruptions, and emergencies. The delivered set has 38 fixtures.
- [x] Score task success and tool-call correctness, and save a results table. Distinguish offline fixture/tool evaluation from actual LLM decision-quality evaluation and report anything not live-tested honestly.

## 7. Automated tests and clean project
- [x] Write pytest tests for the tools and database logic.
- [x] Provide a clean repository structure, `.env.example` (never commit secrets), and dependency requirements.
- [x] Keep the implementation lightweight for a 4 GB RAM Acer laptop without a graphics card; avoid Docker and MLOps. CPU/RAM performance on that specific laptop is not measured.

## 8. Browser app, documentation, and free-host guidance
- [x] Provide a simple web page with a mic button to talk to the agent. The UI production build passed; live microphone connection was not exercised.
- [x] Display clinic identity and schedule from backend configuration so the page does not show stale hard-coded hours when settings change.
- [x] Provide a README with an architecture diagram, setup steps, a latency table, evaluation results, limitations, and a section explaining each design decision.
- [x] Include deployment instructions for a free host and a list of exactly which API keys the user needs to create and where. The Render Blueprint YAML was parsed; the service was not deployed.
- [x] Warn that the public WebSocket demo currently has no authentication/rate limit and must not be exposed with provider keys without access and usage controls.
- [x] Work step by step, run the tests, and report honest results. Do not claim anything that was not actually tested.
