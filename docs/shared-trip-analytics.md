# Shared-Trip Growth Instrumentation

Roadmap: Phase 18, Weeks 19–20. Goal: measure how users discover, share, and
convert on shared trips — without changing any existing UX.

**Status: implemented.** Storage is MongoDB (already provisioned as
"secondary storage" per `CLAUDE.md`, this is its first real use). Nothing in
this document changes business logic — every event is observation bolted
onto an action that already existed.

## Scope: what "trip" means here

The event payload field is `trip_id`, and it now spans **two different
entities**, disambiguated by a `kind` field:

- `kind: "video"` (default, omitted on older documents predating this
  field) — the existing `Video`/`Plan` entity, the original public share
  page (`web/share/[id]`, copy-link, QR code). `trip_id` uses "trip"
  because that's the user-facing word for a completed video result (e.g.
  `"İstanbul Gezisi"`), not because it's the Trip Builder's `Trip` table.
- `kind: "trip"` — the Trip Builder's `Trip`/`TripStop` entity
  (`app/models/trip.py`), which gained its own sharing capability (invite
  links, accept/decline, collaborators) in the trip-sharing feature. Here
  `trip_id` really is a `Trip.id`.

**Don't assume every `trip_id` in this collection is a `Video.id`** — always
filter/group by `kind` as well when querying, or the two id spaces will
collide (a `Video.id` and a `Trip.id` can be numerically equal but refer to
completely different rows).

`Plan.is_public` is a dead column — never set, never read anywhere in the
codebase. Today, "public" effectively means "the video finished processing"
(`Video.status == COMPLETED`); there's no explicit publish action to
observe. `shared_trip_created` reflects that reality (see below) rather
than pretending a publish toggle exists.

## Event taxonomy

Single source of truth: `services/core-api/app/core/analytics_events.py`.

| Event | Status | `kind` | Platform(s) | Fired from |
|---|---|---|---|---|
| `shared_trip_created` | ✅ wired | video | server | `video_tasks.py` (`_track_trip_created`), on `COMPLETED` |
| `shared_trip_link_copied` | ✅ wired | video | web | `share/[id]/page.tsx` (3 copy actions) |
| `shared_trip_share_sheet_opened` | ✅ wired | video | iOS | `ResultsView.swift` (PDF/Story Card export) |
| `shared_trip_opened` | ✅ wired | video | web | `share/[id]/page.tsx`, on successful mount |
| `shared_trip_joined` | ✅ wired | video | web | `api.ts` `register()`, via referral marker |
| `shared_trip_deleted` | ✅ wired | video | server | `VideoService.delete_video` |
| `shared_trip_invite_sent` | ✅ wired | trip | server | `SqlSharingRepository.create_share`, on invite-link creation |
| `shared_trip_declined` | ✅ wired | trip | server | `SqlSharingRepository.decline_by_token`, on decline |
| `shared_trip_expired` | ✅ wired | trip | server | `SqlSharingRepository._maybe_expire`, lazy check on next token use |
| *(invite accepted)* | ⛔ not wired | — | — | no event exists — `accept_by_token` doesn't call `AnalyticsService.track()` at all |

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

### `shared_trip_invite_sent`

Fires the moment a trip owner creates an invite link (`POST
/internal/trips/{trip_id}/shares`) — the server-side analog of "an invite
now exists," same pattern as `shared_trip_created`.

- **Where:** `services/core-api/app/infrastructure/repositories/sql_sharing_repository.py`,
  `SqlSharingRepository.create_share`, right after the `TripShare`/`ShareToken`
  rows commit. Best-effort — a failed analytics write never fails invite
  creation (the token is already committed by the time `track()` runs).
- **Platform:** always `"server"`. **kind:** always `"trip"`.
- **source:** always `"share_link_created"`.
- **user_id:** the trip owner (`created_by`), i.e. the person creating the
  invite — not the (not-yet-known) recipient.
- Not client-fireable: this is derived from a server-controlled state
  change (share creation), same reasoning as `shared_trip_created`/`deleted`.

### `shared_trip_declined`

Fires when the invite recipient explicitly declines (`POST
/internal/shares/decline`).

- **Where:** same file, `SqlSharingRepository.decline_by_token`, after the
  share's status flips to `DECLINED`.
- **Platform:** always `"server"`. **kind:** always `"trip"`.
- **source:** always `"invite_response"`.
- **user_id:** the recipient who declined.
- Not client-fireable: the BFF/web page never calls the beacon endpoint for
  this — the decline itself (`POST /shares/decline`) is what triggers it,
  server-side, same as `created`/`deleted`/`invite_sent`.

### `shared_trip_expired`

There's no background cron sweeping for expired invites — expiry is
observed lazily, the first time anyone touches an expired token again
(preview, accept, or decline all funnel through the same `_is_usable` →
`_maybe_expire` check).

- **Where:** same file, `SqlSharingRepository._maybe_expire`, called from
  `_is_usable` (shared by `preview_by_token`/`accept_by_token`/
  `decline_by_token`). Only fires on the transition itself (`PENDING` →
  `EXPIRED`) — a token that's already `EXPIRED` from a prior check doesn't
  re-fire on every subsequent touch.
- **Platform:** always `"server"`. **kind:** always `"trip"`.
- **source:** always `"lazy_expiry_check"`.
- **user_id:** the trip owner (`created_by`) — whoever is touching the
  expired link at the moment of the lazy check isn't necessarily who should
  be attributed to the expiry.

### Not wired: invite acceptance

There is currently **no event for a successful accept**
(`POST /internal/shares/accept`) — `SqlSharingRepository.accept_by_token`
never calls `AnalyticsService.track()`. This is the actual "did the
invite convert" growth-loop signal for trip sharing (the `kind: "trip"`
analog of `shared_trip_joined` for video shares) and it's currently a real
gap in the funnel, not an intentional no-op like the three above used to
be. `AnalyticsEvent` has no dedicated member for it either — wiring it
would need a new enum value (e.g. `shared_trip_accepted`) added to both
`CLIENT_FIREABLE_EVENTS`-adjacent server-only wiring and a `track()` call
in `accept_by_token`, mirroring how `declined`/`expired` are wired above.

## Payload schema

Every event is a MongoDB document in the `analytics_events` collection
(database `tripclip`, same `MONGODB_URL` already used elsewhere):

```json
{
  "event":     "shared_trip_link_copied",
  "trip_id":   42,
  "kind":      "video",
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
| `trip_id` | int | See "Scope" above — a `Video`/`Plan` id when `kind="video"`, a `Trip` id when `kind="trip"` |
| `kind` | string | `"video"` (default) \| `"trip"` — disambiguates the `trip_id` namespace, see "Scope" |
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
(`link_copied`, `share_sheet_opened`, `opened`, `joined`). Every other
event — `created`, `deleted`, and the trip-sharing trio
(`invite_sent`/`declined`/`expired`) — is rejected if sent by a client:
all six are derived from state the server already controls (video
lifecycle or `SqlSharingRepository` mutations), and accepting them from
outside would let anyone fabricate fake trip activity.

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

For the four steps that are real, query `analytics_events` directly. This
funnel is `kind: "video"` only — `created`/`link_copied`/`opened`/`joined`
are never fired with `kind: "trip"` today (see the trip-sharing events
above for that funnel's equivalents: `invite_sent` → `declined`/`expired`,
with acceptance still unobserved). Example aggregation — trips created in
the last 30 days, with counts at each funnel stage:

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
