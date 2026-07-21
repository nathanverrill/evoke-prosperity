# Field Kit QR pairing — handoff (2026-07-19)

Scope: the phone-pairing flow only — a student scans a QR code shown on the
web Hub to open `companion.html` ("Field Kit") on their own phone, with no
login on the phone itself. Written for whoever runs or continues work on
the upcoming playtest.

## How it works

1. A logged-in web session mints a one-time pairing token: `POST` handled
   by `_mint_pairing_token()` (`evoke/main.py:2811-2826`) — a `uuid.uuid4()`
   stored in the `pairing_tokens` table (`main.py:333-338`), scoped to that
   caller's own `user_id` via `Depends(get_current_user)`.
2. The QR encodes a URL built by `_companion_url()` (`main.py:2792-2808`):
   `PUBLIC_WEB_URL` env override > the host the browser used > a client
   hint. This is also the mechanism used for the "same Wi-Fi" note below.
3. The phone hits `POST /api/companion/pair` (`main.py:3380-3403`), which
   validates the token (exists, unused, <10 min old), marks it used, and —
   **as of today** — issues the real `evoke_session` cookie via
   `issue_session()`. Before today's fix it returned the user's identity as
   JSON only; the phone stored that raw `user_id` in `localStorage` and
   sent it back as a query param on every later call, which no longer
   works against any route (they all now use `require_self`/
   `get_current_user`, reading the cookie only — see `c4c5819`).

## What was fixed this pass

**`evoke/main.py:3380-3403`** — `companion_pair` now selects the user's
`role` and calls `issue_session(response, user_id, role)` after consuming
the token, the same call the OAuth callback and admin login use. The
token itself (server-minted, single-use, 10-minute expiry, tied to one
`user_id` at mint time) is treated as the verified-identity source, same
trust tier as an OAuth callback code — this is why it's allowed to call
`issue_session` directly per the contract documented in
`auth_session.py:42-45`.

Without this fix, Field Kit's pairing step "succeeded" but every
subsequent call (missions, reflections, awards, notifications, B1llbot
chat, Minecraft link-code mint/confirm, quest-evidence submit — everything
gated by `require_self`/`get_current_user`) would 401, because the phone
never held a real session cookie. This was an unverified regression from
the `c4c5819` auth-hardening pass, not a documented/intentional gap.

## Also required: HTTPS

`issue_session()` sets the cookie `secure=True` (`auth_session.py:51`), so
browsers refuse to store it over plain `http://`. The documented LAN
deployment pattern (`PUBLIC_WEB_URL=http://192.168.1.50:8000`,
`.env.example:117`) is plain HTTP — pairing will look broken again on that
path even with today's fix.

**For the playtest, use the ngrok tunnel that already exists in
`quick-start.sh:64-109`:**

```
ENABLE_NGROK=true
NGROK_STATIC_DOMAIN=your-reserved-domain.ngrok-free.app   # recommended, see below
```

in `.env`, then run `./quick-start.sh`. It starts `ngrok http 8000`, polls
the local ngrok API for the public URL, and writes it into
`PUBLIC_WEB_URL` automatically. Set `NGROK_STATIC_DOMAIN` (a free reserved
domain from your ngrok account) so the URL is stable across restarts —
without it you get a new random URL every restart, stranding any
already-generated QR codes/companion links mid-session.

ngrok also removes the "phone must be on the same Wi-Fi as the server"
constraint: the LAN-IP URL only resolves for devices on that private
network, so a phone on cellular data simply can't reach it. ngrok gives a
real public hostname reachable from anywhere with internet access.

## Verified NOT a blocker

- **Admin routes**: `quick-start.sh:65-66`'s comment warns ngrok would
  expose "unprotected `/api/admin/*` routes" — checked, this is **stale**.
  Every `/api/admin/*` route (`main.py:1223,1253,1284,3066,3178`) is
  already behind `Depends(get_current_admin)`, and `/api/admin/login`
  itself is disabled unless `EVOKE_ADMIN_PASSWORD_HASH` is set. Worth a
  one-line comment fix in `quick-start.sh`, not a live hole.
- **CORS wildcard + credentials** (`main.py:88-94`,
  `allow_origins=["*"], allow_credentials=True`): looked like a
  spec-violating combo, but Starlette's `CORSMiddleware` correctly echoes
  back the specific request `Origin` (plus `Vary: Origin`) whenever a
  cookie is present instead of literally sending `*`
  (`starlette/middleware/cors.py:161-164`) — verified by reading the
  installed middleware source. Not broken, though still a broad
  any-origin trust policy worth narrowing eventually.

## Known, accepted tradeoffs (not fixed, not blockers for a small trusted playtest)

- **No independent identity check on QR pairing** — possession of the
  token/QR is the only factor. `GAPS.md:45,121` documents this as a
  deliberate, deferred tradeoff (a "yes that's me" confirmation step was
  removed on request since it never actually verified identity, just
  added friction). Real risk: a shoulder-surfed QR gives full access to
  that student's data with no second factor.
- **4-digit Minecraft link code** (`main.py:3412`, `random.randint(1000,
  9999)`, ~13 bits) — no rate limiting beyond the bridge's 10-second poll
  cadence (`evoke-minecraft-bridge/bridge.py:1007-1064`), matched globally
  against all pending codes rather than scoped per-player. Mitigated by
  requiring the real student to confirm the matched Minecraft username
  before the link completes.
- **TOCTOU race on single-use pairing tokens** (`main.py:3390-3397`) —
  read-then-update instead of an atomic `UPDATE ... WHERE used_at IS
  NULL`; a raced replay of a captured token could theoretically redeem it
  twice. Low practical risk at playtest scale.

## Operational notes for running the playtest

- The ngrok tunnel exposes the instance to the **public internet**, not
  just the school network, for as long as it's up — fine for a short
  supervised window, tear it down afterward.
- Free-tier ngrok has connection-rate limits; if the whole class scans
  the QR within the same minute or two, worth a quick sanity check against
  your plan's limits.
- Do one real dry run yourself (scan the QR, confirm the click-through
  path) before the class does, in case ngrok's free-tier interstitial
  behavior has changed since this was written.

## Suggested follow-ups after the playtest

1. Fix the TOCTOU race on pairing-token consumption.
2. Decide, as a product call (not just engineering), whether the "no
   identity confirmation" tradeoff is acceptable for a real (non-playtest)
   rollout — `GAPS.md` flags it as deliberate but open.
3. Narrow the CORS policy from `allow_origins=["*"]` to an explicit list.
4. Update the stale "unprotected /api/admin/*" comment in
   `quick-start.sh:65-66`.
