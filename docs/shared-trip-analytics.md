# Shared-Trip Growth Instrumentation

Roadmap: Phase 18, Weeks 19–20. Goal: measure how users discover, share, and
convert on shared trips — without changing any existing UX.

**Status: implemented.** Storage is MongoDB (already provisioned as
"secondary storage" per `CLAUDE.md`, this is its first real use). Nothing in
this document changes business logic — every event is observation bolted
onto an action that already existed.

## Scope: what "trip" means here

The event payload field is `trip_id`, but it refers to the **existing
`Video`/`Plan` entity** — the only thing in the product with a working
public share page (`web/share/[id]`, copy-link, QR code) — not the newer
`Trip`/`TripStop` Trip Builder entity from Weeks 6–7. As of this writing the
Trip Builder has no sharing capability of any kind (no `is_public`, no share
endpoint, no share page). `trip_id` uses "trip" because that's the
user-facing word for a completed video result (e.g. `"İstanbul Gezisi"`),
not because it's the Trip Builder's `Trip` table. If/when Trip Builder gains
its own sharing, it should get its own `trip_id` namespace or a `kind` field
distinguishing the two — don't assume every `trip_id` in this collection is
a `Video.id`.

Also worth noting: `Plan.is_public` is a dead column — never set, never
read anywhere in the codebase. Today, "public" effectively means "the video
finished processing" (`Video.status == COMPLETED`); there's no explicit
publish action to observe. `shared_trip_created` reflects that reality (see
below) rather than pretending a publish toggle exists.

## Event taxonomy

Single source of truth: `services/core-api/app/core/analytics_events.py`.

| Event | Status | Platform(s) | Fired from |
|---|---|---|---|
| `shared_trip_created` | ✅ wired | server | `video_tasks.py` (`_track_trip_created`), on `COMPLETED` |
| `shared_trip_link_copied` | ✅ wired | web | `share/[id]/page.tsx` (3 copy actions) |
| `shared_trip_share_sheet_opened` | ✅ wired | iOS | `ResultsView.swift` (PDF/Story Card export) |
| `shared_trip_opened` | ✅ wired | web | `share/[id]/page.tsx`, on successful mount |
| `shared_trip_joined` | ✅ wired | web | `api.ts` `register()`, via referral marker |
| `shared_trip_deleted` | ✅ wired | server | `VideoService.delete_video` |
| `shared_trip_invite_sent` | ⛔ not wired | — | no invite mechanism exists |
| `shared_trip_declined` | ⛔ not wired | — | no accept/decline flow exists |
| `shared_trip_expired` | ⛔ not wired | — | no share-link expiry exists |

### `shared_trip_created`

Fires the moment a video reaches `COMPLETED` — i.e. the moment its
`/share/[id]` page becomes reachable. This is **not** a user-initiated
"publish" action (none exists); it's the closest real analog to "a
shareable trip now exists."

- **Where:** `services/core-api/app/tasks/video_tasks.py`, helper
  `_track_trip_created`, called from both `process_video_task` and
  `process_url_task` right after `repo.save_results(...)` succeeds.
- **Platform:** always `"server"`.
- **source:** always `"pipeline_completed"`.
- **user_id:** the video's owner.

### `shared_trip_link_copied`

Fires whenever the share page's link is copied to the clipboard. There are
three distinct copy affordances on the page today, distinguished by `source`:

- **Where:** `web/src/app/share/[id]/page.tsx`, function `handleShare`, and
  `web/src/components/QRShareCard.tsx`'s own copy button (via an `onCopy`
  callback prop — `QRShareCard` itself stays analytics-agnostic).
- **Platform:** `"web"` only. iOS has no link-copy UI (see
  `shared_trip_share_sheet_opened` below for why).
- **source:** `"hero_button"` | `"sidebar_card"` | `"qr_card"`.

### `shared_trip_share_sheet_opened`

iOS has no link-based sharing UI — `ResultsView`'s "..." menu exports a PDF
or a rendered "Story Card" image via the OS share sheet
(`UIActivityViewController`), not the `/share/[id]` URL. That existing sheet
is the closest real analog to "share sheet opened" today, so it's tracked
there. Web has no native share-sheet call (`navigator.share()` is not used
anywhere) — its equivalent action is `shared_trip_link_copied`.

- **Where:** `ios/TripClipApp/Features/Results/ResultsView.swift`, function
  `share(_:source:)`, called only after export succeeds (a failed export
  never opens a sheet, so it must never fire this event).
- **Platform:** `"ios"` only.
- **source:** `"pdf_export"` | `"story_card"`.

### `shared_trip_opened`

Fires when someone successfully loads a shared trip's page — i.e. the page
actually rendered content, not a 404/error state.

- **Where:** `web/src/app/share/[id]/page.tsx`, inside the `getPlan(id)`
  success handler, guarded by a `useRef` so React StrictMode's dev-mode
  double-invoke doesn't double-fire it.
- **Platform:** `"web"` only. iOS has no deep-link-into-a-shared-trip flow.
- **source:** `"direct_link"`.
- **user_id:** present if the viewer happens to be logged in (their own
  browser session), otherwise `null` — most viewers of a shared link are
  anonymous.

### `shared_trip_joined`

The actual "did a viewer become a user" growth-loop signal. Implemented as
a small referral-attribution mechanism, not a new event trigger point:

1. On share-page mount, `markShareReferral(tripId)` writes
   `{ tripId, ts }` to `localStorage` under `tripclip_referral` (7-day TTL).
2. On successful `register()`, `trackReferralJoinIfPresent()` checks for
   that marker; if present and not expired, fires `shared_trip_joined` with
   the stored `trip_id`, then clears the marker regardless of outcome.

- **Where:** `web/src/lib/api.ts` (`markShareReferral`,
  `trackReferralJoinIfPresent`, called from `register()`).
- **Platform:** `"web"` only.
- **source:** `"share_page_referral"`.
- **Caveat:** this is same-browser attribution only (no cross-device
  linking, no server-side cookie). A user who visits on their phone and
  signs up on desktop won't be attributed. That's an accepted limitation
  for a first cut — a real attribution system (server-side referral tokens
  in the URL) is future work if this signal proves noisy.

### `shared_trip_deleted`

- **Where:** `services/core-api/app/application/services/video_service.py`,
  `VideoService.delete_video`, after the delete already succeeded.
- **Platform:** `"server"`.
- **source:** `"user_delete"`.

### Not wired: `shared_trip_invite_sent`, `shared_trip_declined`, `shared_trip_expired`

These three are defined in `AnalyticsEvent` for schema forward-compatibility
and are explicitly rejected by the beacon endpoint
(`InvalidAnalyticsEventException`) if a client attempts to send them. They
don't correspond to anything a user can currently do:

- **No invite mechanism.** There's no email/SMS/in-app way to invite a
  specific person to a trip — the only distribution channel is "copy a link
  and send it yourself outside the app."
- **No accept/decline flow.** Opening a share link just... shows the trip.
  There's no request-to-join or accept/reject step.
- **No expiry.** A share link works as long as the video exists; there's no
  TTL or revocation on the link itself.

All three become meaningful once collaborative trip building (goal.md
Phase 6, "should have," scoped to v2) exists — a real invite/accept/decline
UI for the `Trip` entity. Wiring fake triggers for them now would mean
recording events for actions that can't happen, which is worse than not
recording them at all. When that feature ships, wire these three the same
way the other six are wired here — the taxonomy and beacon already support
it, only `CLIENT_FIREABLE_EVENTS`/new server hooks need updating.

## Payload schema

Every event is a MongoDB document in the `analytics_events` collection
(database `tripclip`, same `MONGODB_URL` already used elsewhere):

```json
{
  "event":     "shared_trip_link_copied",
  "trip_id":   42,
  "user_id":   17,
  "platform":  "web",
  "source":    "hero_button",
  "timestamp": "2026-08-07T10:15:00.000Z",
  "metadata":  {}
}
```

| Field | Type | Notes |
|---|---|---|
| `event` | string | One of the 9 taxonomy values (`AnalyticsEvent`) |
| `trip_id` | int | See "Scope" above — a `Video`/`Plan` id today |
| `user_id` | int \| null | Absent for anonymous share-page viewers |
| `platform` | string | `"ios"` \| `"web"` \| `"server"` — set by the BFF/server, never trusted from the client body |
| `source` | string \| null | Free-form, per-event (see tables above) |
| `timestamp` | datetime (UTC) | Set server-side in `AnalyticsService.track`, not client-supplied |
| `metadata` | object | Reserved for event-specific extra fields; empty today |

## API

`POST /internal/analytics/events` (core-api, behind `verify_internal_secret`
like every other internal route), proxied by both BFFs as
`POST /api/mobile/analytics/events` and `POST /api/web/analytics/events`.

Request body (client-facing, via a BFF):
```json
{ "event": "shared_trip_link_copied", "trip_id": 42, "source": "hero_button", "metadata": {} }
```

`platform` and `user_id` are **not** part of the client request body — each
BFF hardcodes its own `platform`, and `user_id` comes from the BFF's own
auth resolution (JWT for mobile, optional JWT for web), forwarded as the
`x-user-id` internal header. This prevents a client from spoofing another
user's activity or claiming to be a different platform.

Only `CLIENT_FIREABLE_EVENTS` are accepted from this endpoint
(`link_copied`, `share_sheet_opened`, `opened`, `joined`). `created` and
`deleted` are rejected if sent by a client — they're derived from state the
server already controls, and accepting them from outside would let anyone
fabricate fake trip activity.

The endpoint returns `202` immediately; the actual Mongo write happens via
FastAPI `BackgroundTasks` after the response is sent. A slow or unreachable
Mongo can never add latency to the request, and `AnalyticsService.track()`
additionally never raises on its own — both layers independently guarantee
"failures must never affect user requests."

## Computing the funnel

`Create → Share → Open → Join → First edit → Return visit`

Two of these six steps don't have a real backing action today:

- **First edit:** N/A. The existing stop-order edit
  (`PATCH /videos/{id}/order`) only applies to the trip's *owner*, not a
  viewer who opened it via a share link — there's no collaborative editing
  yet. Meaningful once Trip Builder gets collaborative editing (v2).
- **Return visit:** not a discrete event in the requested taxonomy — it's
  derived by querying repeat `shared_trip_opened` events for the same
  `trip_id` (or repeat sessions for the same `user_id`) over time, rather
  than firing a dedicated event per visit.

For the four steps that are real, query `analytics_events` directly. Example
aggregation — trips created in the last 30 days, with counts at each funnel
stage:

```javascript
db.analytics_events.aggregate([
  { $match: { timestamp: { $gte: ISODate("2026-07-08T00:00:00Z") } } },
  { $group: {
      _id: "$trip_id",
      created:      { $sum: { $cond: [{ $eq: ["$event", "shared_trip_created"] }, 1, 0] } },
      shared:       { $sum: { $cond: [{ $in: ["$event", ["shared_trip_link_copied", "shared_trip_share_sheet_opened"]] }, 1, 0] } },
      opened:       { $sum: { $cond: [{ $eq: ["$event", "shared_trip_opened"] }, 1, 0] } },
      joined:       { $sum: { $cond: [{ $eq: ["$event", "shared_trip_joined"] }, 1, 0] } },
  }},
  { $group: {
      _id: null,
      trips_created:      { $sum: { $cond: [{ $gt: ["$created", 0] }, 1, 0] } },
      trips_shared:       { $sum: { $cond: [{ $gt: ["$shared", 0] }, 1, 0] } },
      trips_opened:       { $sum: { $cond: [{ $gt: ["$opened", 0] }, 1, 0] } },
      trips_led_to_join:  { $sum: { $cond: [{ $gt: ["$joined", 0] }, 1, 0] } },
  }},
]);
```

Conversion rate between any two adjacent stages is just
`stage_N_count / stage_N-1_count`. K-factor (goal.md's Phase 17 growth
metric) is `count(shared_trip_joined) / count(distinct user_id who fired
shared_trip_created or shared_trip_link_copied)` over the same window.

## Operational notes

- **Kill switch:** `ANALYTICS_ENABLED` env var (default `true`), read by
  `MongoAnalyticsClient`. Set to `false` to stop all writes without a
  deploy — same "opt-in via config" pattern as `SENTRY_DSN`/`APNS_*`.
- **Failure mode:** if MongoDB is unreachable, every `track()` call logs a
  warning and returns — no exception ever reaches a caller, no user-facing
  request is ever slowed or failed by this system.
- **No PII beyond `user_id`.** No IP addresses, device identifiers, or
  free-text fields are captured.
