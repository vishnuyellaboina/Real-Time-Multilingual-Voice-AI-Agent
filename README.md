# 2care Real-Time Multilingual Voice AI Agent

This repository contains a runnable submission scaffold for the clinical appointment booking assignment. It now includes a browser voice demo using microphone input and spoken output on top of a Python backend that handles multilingual appointment orchestration, memory, conflict logic, outbound reminder flows, and visible reasoning traces.

## Stack

- Backend: Python, FastAPI, SQLite
- Frontend: TypeScript, React, Vite
- Persistence: SQLite by default, with clean seams for Redis or external stores

## What is implemented

- Real-time session endpoint over WebSocket: `/ws/session/{patient_id}`
- Simple HTTP turn endpoint for browser voice demoing: `/api/turn`
- Browser voice interface:
  - microphone input via Web Speech API
  - spoken agent reply via browser speech synthesis
  - inbound and outbound demo modes
- Appointment lifecycle support:
  - booking
  - rescheduling
  - cancellation
  - conflict detection with alternative slots
- Multilingual continuity:
  - English, Hindi, Tamil detection
  - preferred language persisted across sessions
- Memory design:
  - short-term session state in TTL cache
  - long-term patient and interaction history in SQLite
- Outbound campaign mode:
  - reminder interaction path
  - campaign outcome logging
- Reasoning traces:
  - each turn emits language, intent, memory, and tool trace steps
- Latency instrumentation:
  - dispatch
  - reasoning
  - tool execution
  - render
  - total turn latency

## Repository structure

```text
backend/
  app/
  tests/
frontend/
docs/
```

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://127.0.0.1:5173` and posts turns to the backend on `http://127.0.0.1:8000`.

For the voice demo, use Chrome or Edge so the browser speech APIs are available.

For deployed frontend builds, set:

```bash
VITE_API_BASE_URL=https://your-backend-project.vercel.app
```

Without this, the deployed UI will still try to call localhost and voice turns will fail after transcription.

## Architecture summary

The architecture is intentionally split into thin, testable layers:

1. Voice IO layer
   The runnable demo uses browser microphone capture plus Web Speech API recognition for inbound voice and browser speech synthesis for outbound voice. The backend remains transport-agnostic, so this same orchestrator can later sit behind WebRTC, SIP, Twilio, Exotel, or a streaming provider SDK.

2. Realtime orchestrator
   Owns session state, latency budgets, language continuity, and trace generation. This is where barge-in handling should live in a production deployment.

3. Agent brain
   Plans tool usage, extracts doctor and slot hints, resolves intent, and produces multilingual responses. The demo keeps the planning layer deterministic so the repo is runnable without keys, but the tool orchestration is still real: appointment operations, patient lookup, and campaign logging happen through concrete services rather than mocked UI responses.

4. Tool layer
   Encapsulates patient lookup, appointment operations, campaign logging, and conflict resolution. No hardcoded user responses bypass the tool layer.

5. Memory layer
   Split between:
   - session memory: active intent, pending confirmation, last requested slot, recent trace
   - cross-session memory: preferred language, doctor preference, last reason, appointment and interaction history

See [architecture.png](/F:/NEXTWAVE/2care.ai_Assessment/docs/architecture.png) or [architecture.svg](/F:/NEXTWAVE/2care.ai_Assessment/docs/architecture.svg).

## Memory design

### Session memory

- Backed by an in-process TTL cache
- Stores:
  - language for current conversation
  - active intent
  - pending confirmation payload
  - last doctor and slot hints
  - last reason
  - recent reasoning trace

This exists to keep the active turn loop fast and avoid repeated storage reads during the same call.

### Cross-session memory

- Backed by SQLite in the demo
- Stores:
  - patient profile
  - preferred language
  - preferred doctor
  - last known clinical reason
  - appointment history
  - recent interactions

In production, this layer can move to Postgres plus Redis:

- Redis:
  - hot session cache
  - TTL-ed call state
  - pub/sub for horizontally scaled workers
- Postgres:
  - source of truth for appointments
  - durable patient memory
  - campaign audit trail

## Tool orchestration

Tool calls are explicitly surfaced in the response payload. A typical booking turn:

1. `lookup_patient`
2. `book_appointment`
3. return either a booked slot or viable alternatives

The scheduling tool enforces:

- no past bookings
- no double-booking a doctor slot
- graceful fallback for invalid doctors
- alternative slot search in 30-minute increments

## Multilingual strategy

The demo detects English, Hindi, and Tamil from script and keyword markers, then persists the language back to the patient profile. On a return interaction, preferred language is used as the tie-breaker if the current utterance is ambiguous.

In production I would separate multilingual handling into:

- streaming ASR with language ID
- normalized semantic representation for agent reasoning
- language-locked TTS voice per patient preference

## Real-time latency target

The assignment target is under `450 ms` from speech end to first audio response.

This repository logs on every backend turn:

- speech end to dispatch
- reasoning time
- tool time
- response render time
- total turn time

In the current browser demo, backend orchestration should complete well under the target because:

- reasoning is deterministic
- storage is local SQLite
- browser STT and TTS stay local to the device

### Production latency budget I would target

- VAD finalization: 40-80 ms
- ASR final partial stabilization: 90-140 ms
- reasoning + tool loop: 80-140 ms
- TTS first chunk: 90-120 ms

Total: roughly `300-480 ms`, with aggressive caching and prefetching required to consistently stay below `450 ms`.

## Outbound campaigns

Outbound mode is represented by the `channel="outbound"` turn path and campaign logging service. In production this would be driven by a scheduler or queue:

- reminder campaign generator
- campaign worker queue
- retry policy
- polite rejection logging
- rebooking follow-up path

## Barge-in / interruption design

The current code leaves a clear seam for it but does not fully implement streaming audio interruption. The production design would:

- stream TTS in chunks
- cancel TTS immediately when inbound speech energy crosses threshold
- preserve partial state in session memory
- resume with a concise repair turn

## Known limitations

- Voice transport uses browser speech APIs rather than telephony or WebRTC media streams
- The deterministic planner is a local demo substitute for a function-calling LLM
- Slot extraction is intentionally simple
- Timezones are not yet patient-specific
- SQLite is not enough for real concurrent booking traffic

## Verification

Run backend tests:

```bash
cd backend
python -m unittest discover -s tests
```

## Vercel deployment

Deploy as two Vercel projects:

- Backend project with root directory `backend`
- Frontend project with root directory `frontend`

In the frontend Vercel project, add:

```bash
VITE_API_BASE_URL=https://your-backend-project.vercel.app
```

Voice input in production requires:

- `https://` deployment or `localhost`
- Chrome or Edge for the best Web Speech API support
- microphone permission enabled in the browser

For the backend Vercel project:

- set root directory to `backend`
- Vercel should serve [index.py](/F:/NEXTWAVE/2care.ai_Assessment/backend/index.py:1) as the FastAPI entrypoint
- on Vercel, SQLite now defaults to `/tmp/agent.db` because the deployed filesystem is not writable like local disk

## Suggested next production upgrades

- Replace deterministic planner with streaming LLM function calling
- Add Redis-backed session memory with TTL
- Add Postgres-backed transactional scheduler
- Add provider adapters for telephony, ASR, and TTS
- Add queue-backed campaign scheduler
- Add true interrupt handling and partial audio streaming
