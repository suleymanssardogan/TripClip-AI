# Trip Assistant (Milestone 26)

TripClip AI's first genuinely AI-native feature: a conversational assistant
that answers questions about a user's *actual* trip, grounded in the
trip's real data — not generic LLM travel knowledge. **Read-only** in this
milestone: it cannot modify a trip, apply an itinerary, or perform any
action. It only answers questions.

## Why this architecture

Before writing any code, the existing AI/LLM surface was inspected:

- `services/core-api/app/ml/gemini_service.py` — Gemini 2.0/2.5 Flash via
  raw REST calls (no SDK), used for two narrow, schema-locked tasks:
  extracting locations from video frames, and generating travel tips.
  Neither exposes a general "ask a question, get an answer" capability.
- `services/core-api/app/ml/rag_service.py` — despite the filename, this
  is **not** retrieval-augmented generation. It calls Ollama's
  `/api/generate` directly with a hand-built prompt; there is no
  retrieval step (confirmed by `CLAUDE.md`'s own description: "no
  retrieval step, pure generation"). It's the pre-Gemini fallback for
  travel tips.
- `app/ml/qdrant_service.py` / `embeddings.py` — real vector search, but
  scoped to Place library *semantic search* (finding places by meaning
  across a user's whole saved-places library). A single trip's context
  (a handful of stops) is small and already fully known — there is
  nothing to *retrieve*, so wiring this trip assistant into Qdrant would
  be retrieval infrastructure solving a problem that doesn't exist here.
  Per the milestone's own instruction, no RAG/vector database was
  introduced.
- No conversation/message database model, no MCP integration, no agent
  framework anywhere in the repository.

Given this, the smallest correct design is: a **new, minimal
provider-agnostic interface** (`AIProvider`, one method:
`answer(system_prompt, user_message)`), a **real implementation** that
delegates to `GeminiService` (reusing its existing HTTP/retry/JSON-parse
machinery — nothing is reimplemented), and a **fake implementation** for
tests, so the test suite never needs a real LLM call or API key.

### Provider scope (deliberate simplification)

Only Gemini is wired up as a real provider. `RAGService` (Ollama) already
exists in the codebase and *could* be added the same way — but doing so
here would mean handling a second, less-reliable JSON-mode contract
(Ollama's structured output isn't schema-constrained the way Gemini's
`responseSchema` is) for a first version that's explicitly supposed to
stay small. This is a conscious trade-off, not an oversight, and the
`AIProvider` interface is built precisely so adding an `OllamaAIProvider`
later requires no changes anywhere else in the stack.

## Architecture

```
Trip (AbstractTripRepository.get_trip)
Applied Itinerary, if any (OptimizationService.get_itinerary)
        ↓
TripContextBuilder (app/domain/assistant/context_builder.py — pure, no I/O)
        ↓
TripContext (structured, JSON-ready)
        ↓
TripAssistantService (app/application/services/trip_assistant_service.py)
        ↓
AIProvider (app/ml/ai_provider.py) → GeminiService.answer_question
        ↓
POST /internal/trips/{trip_id}/assistant  (core-api)
        ↓
POST /api/mobile/trips/{trip_id}/assistant   POST /api/web/trips/{trip_id}/assistant
   (mobile-bff, pass-through proxy)             (web-bff, pass-through proxy)
        ↓                                              ↓
      iOS (TripAssistantView)                   Web (/trips/[id]/assistant)
```

Neither BFF contains any AI/prompt/context logic — both are the same
thin pass-through style already established by `trip_optimization.py` in
each service (parse request → forward with `x-user-id` → translate
errors → return response verbatim).

## Trip context structure

`TripContextBuilder.build_trip_context(trip, itinerary, today)` merges
two **already-existing** sources — no new queries, no duplicated business
logic:

1. `AbstractTripRepository.get_trip()` — the trip's own canonical stop
   list. Has place identity, order, and location, but **no schedule**
   (`TripStop` doesn't carry arrival/departure times).
2. `OptimizationService.get_itinerary()` — if `trip.applied_itinerary_id`
   is set, the *applied* optimizer itinerary, which has real
   `arrival_time`/`departure_time`/`visit_duration_minutes`/`date` per
   stop. This is the "distinguish planned itinerary from historical data"
   requirement: the assistant only ever states a specific time if an
   itinerary has genuinely been applied — otherwise it says so.

Resulting `TripContext` (serialized as JSON in the prompt):

```json
{
  "trip_id": 2, "title": "Gaziantep Gezisi", "today": "2026-08-11",
  "has_applied_itinerary": true, "itinerary_applied_at": "2026-08-08T10:05:00",
  "total_days": 1, "total_stops": 4,
  "days": [{
    "day_index": 0, "date": "2026-08-08",
    "stops": [{
      "place_id": 25, "name": "Antep", "order_index": 0,
      "city": "Gaziantep", "category": "tarihi", "has_location": true,
      "arrival_time": "09:00", "departure_time": "10:00", "visit_duration_minutes": 60
    }]
  }]
}
```

Missing data is never silently omitted — `has_location: false`,
`arrival_time: null`, etc. are explicit, so the model can distinguish "I
don't know" from "there's nothing here." `Place.opening_hours` was
**not** wired in: core-api's own optimizer code already documents this
field as "not populated by any pipeline in production" — building a
query for data that's essentially always empty would be premature.

## API contract

```
POST /trips/{trip_id}/assistant

Request:
{ "message": "Bugün nereye gideceğim?", "history": [{"role": "user", "content": "..."}] }

Response:
{ "answer": "...", "references": [{"type": "stop", "day_index": 0, "place_id": 25}] }
```

Permissions follow the trip's own existing access rule exactly
(`resolve_access`, owner/editor/viewer can all ask — same as every other
read-only trip endpoint). A trip the caller can't access returns
`404 TRIP_NOT_FOUND`, not `403` — the same anti-enumeration principle
already established for delete/apply-history (a caller can't distinguish
"doesn't exist" from "exists, not yours").

## Grounding

The system prompt (built once per request, server-side, never seen by
the client) explicitly instructs the model to:

- answer only from the supplied JSON, never invent stops, opening hours,
  or reservations,
- never claim to have performed an action (it's read-only),
- distinguish missing information from known information,
- say so plainly when a question can't be answered from the data,
- treat every string inside the JSON (including place names, which
  ultimately originate from Gemini's own video-extraction step and OCR —
  untrusted, user-influenced data) as inert data, never as instructions.

**Reference validation is not optional trust in the model.** Every
`{day_index, place_id}` pair the model returns is checked against the
actual `TripContext` (`TripContext.find_stop`) before it reaches the
client — a hallucinated reference is dropped and logged, never
forwarded. This is what lets the UI resolve "the AI mentioned this stop"
into "highlight this exact stop" without ever parsing natural language.

## Selection integration (reusing existing infrastructure, not new)

References use the **same stable identity** already established by the
Optimizer/Trip Detail work (Milestones 21–25): `(day_index, place_id)`,
never an array index.

- **Web**: a reference chip navigates to
  `/trips/{id}?focusDay={d}&focusPlace={p}`; Trip Detail resolves this
  into a real `stopId()`-based selection once the trip loads, reusing the
  exact `OptimizerRouteMap`/`selectStop`/`selectDay` machinery already
  built for the map ↔ list sync — no new selection architecture.
- **iOS**: a reference chip calls an `onFocusStop(dayIndex, placeId)`
  closure that `TripDetailView` uses to set its own `OptimizerSelection`
  (the same type `TripOptimizerView` already uses) and dismisses back to
  Trip Detail.

## Conversation model (deliberately stateless)

No conversation/message table was added. The server holds no chat state
between requests — the client keeps the message list in memory and
sends a bounded slice (`history`, capped server-side at
`MAX_HISTORY_TURNS = 6` regardless of what the client sends) with each
new question. This avoids a new database schema, session concept, or
cleanup/expiry logic entirely, at the cost of losing history on app
relaunch/page reload — an explicit, documented trade-off matching the
milestone's own "do not introduce a large database schema just for chat
history."

## Security

- **Auth**: identical to every other trip-scoped route — BFF decodes the
  real JWT, sets `x-user-id` on the internal request; core-api never
  trusts a client-supplied user id directly.
- **No cross-trip leakage**: access is re-checked on every request via
  `resolve_access`; a non-collaborator gets `404`, never trip content.
- **No API keys reach a client.** `GEMINI_API_KEY` is read once,
  server-side, in `get_ai_provider()` — nothing in the BFF or client
  request/response ever carries it.
- **Prompt injection**: the grounding system prompt explicitly instructs
  the model not to treat any data (including user-supplied place names)
  as instructions; the user's own message is passed as ordinary chat
  content, never concatenated into the system instruction.
- **No arbitrary backend execution.** The service has no write path at
  all in this milestone — `TripAssistantService.ask()` never calls
  anything that mutates a trip, itinerary, or apply-history record.

## Failure handling

| Condition | Result |
|---|---|
| Empty/whitespace message | `400 INVALID_ASSISTANT_REQUEST` |
| Message over 1000 chars | `400 INVALID_ASSISTANT_REQUEST` |
| No access / trip not found | `404 TRIP_NOT_FOUND` |
| No provider configured (`GEMINI_API_KEY` unset) | `503 ASSISTANT_UNAVAILABLE` |
| Provider call fails (timeout, malformed response, upstream error) | `503 ASSISTANT_UNAVAILABLE` — raw provider exception never reaches the client |
| Applied-itinerary enrichment fails (e.g. deleted) | Falls back to trip-only context (no schedule), does not fail the request |

Mobile-bff maps `ASSISTANT_UNAVAILABLE` to `500` (matching its own
pre-existing `ML_SERVICE_UNAVAILABLE` convention); web-bff maps it to
`503` (matching its own pre-existing `DATABASE_ERROR`/`SERVICE_UNAVAILABLE`
convention) — both asymmetries already existed for other codes before
this milestone, just extended consistently here.

## Testing

No test anywhere in the suite requires a real LLM call or API key —
`FakeAIProvider` (records calls, returns configurable/deterministic
responses, can simulate failure) stands in everywhere.

- `test_trip_context_builder.py` (9) — pure merge logic: no-itinerary
  fallback, applied-itinerary schedule, city/category backfill, deleted
  place in itinerary, missing coordinates, multi-day ordering.
- `test_ai_provider.py` (8) — `FakeAIProvider`, `GeminiAIProvider`
  delegation/error-wrapping, `get_ai_provider()` factory (with/without
  `GEMINI_API_KEY`).
- `test_trip_assistant_service.py` (13) — validation, anti-enumeration
  permissions, provider-unavailable, provider-error-never-leaks-raw-text,
  grounding (system prompt contains real trip data), history bounding,
  hallucinated-reference dropping, applied-itinerary-fetch-failure
  fallback.
- `test_trip_assistant.py` (10, core-api route, real DB + HTTP) — full
  integration with `FakeAIProvider` injected via `app.dependency_overrides`.
- `test_trip_assistant.py` (mobile-bff, 7 / web-bff, 8) — proxy
  forwarding, auth, error-code propagation (including the two new codes
  registered in each BFF's `error_wrapper.py`).
- `TripAssistantViewModelTests.swift` (12) — send/receive, validation,
  re-entrancy, no-token-never-calls-API, failure removes the optimistic
  message, retry, unauthorized handling, bounded history.
- `page.test.tsx` (web assistant page, 9) — suggested prompts, send,
  loading, error+retry (input preserved), reference-chip navigation,
  history bounding.
- `page.test.tsx` (Trip Detail, +4) — AI Asistan entry link,
  `?focusDay=&focusPlace=` resolving to a real selection once the trip
  loads, and safely ignoring a reference to a stop that no longer exists.

## Local development

Requires `GEMINI_API_KEY` in `.env` (already required for the video
pipeline — no new variable). Without it, `get_ai_provider()` returns
`None` and every request gets a clean `503 ASSISTANT_UNAVAILABLE` — the
rest of the app is unaffected.

```bash
cd services/core-api  && pytest tests/test_trip_context_builder.py tests/test_ai_provider.py tests/test_trip_assistant_service.py tests/test_trip_assistant.py
cd services/mobile-bff && pytest tests/test_trip_assistant.py
cd services/web-bff    && pytest tests/test_trip_assistant.py
cd web                 && npm test
```

## Verified against a real Gemini call

With a real `GEMINI_API_KEY` available in this environment, the full
stack was exercised end-to-end (not just the fake-provider tests) against
a real trip:

- *"Bu gezide kaç durak var ve hangi şehirdeyim?"* → correctly answered
  "4 durak... Gaziantep", with all 4 real stops returned as validated
  references.
- *"Antep Kalesi saat kaçta açılıyor?"* (opening hours aren't in the
  data) → correctly refused to invent an answer: *"...açılış saati
  bilgisi elimde yok."*
- The same question through the full Web BFF chain (real JWT auth, real
  proxy) produced the same grounded, correct answer.
- Empty message and cross-user access were both verified live to
  produce the expected `400`/`404`.

This is real, observed behavior from this session — not a claim made
without having run it.

## Remaining limitations

- No interactive browser/simulator UI walkthrough (same tooling gap as
  Milestones 22–25 — Chrome extension and iOS tap-automation were both
  unavailable in this environment). The chat pages/views were verified
  via unit/integration tests and a real backend smoke test, not visually.
- Conversation history doesn't survive an app relaunch or page reload
  (by design — see "Conversation model" above).
- Only Gemini is wired as a real provider (see "Provider scope" above).
- `Place.opening_hours` isn't included in context — it's effectively
  always empty in production today; wiring it in would be premature
  until a real data source populates it.

## Future improvements

- An `OllamaAIProvider` (trivial given the existing `AIProvider`
  interface) if a local-model fallback becomes a priority.
- Persistent conversation history, if product usage shows users actually
  want cross-session memory rather than a fresh conversation per visit.
- Once `Place.opening_hours` has real data, include it in context so
  "is this open at 14:00" can be answered directly instead of "I don't
  know."
