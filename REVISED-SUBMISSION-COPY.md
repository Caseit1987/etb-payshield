# ETB PayShield — revised Devpost copy (paste-ready)

This replaces the copy currently on Devpost. It keeps only what was
verified on 2026-10-23 (main run A 403 / A2 403 / B 200, 2 blocked /
1 verified; extended suite 12/12) and discloses the PayPal / AI
status honestly. See SUBMISSION-FIX.md for the repo + deadline steps.

## What was wrong in the pasted copy

- "zero-overhead" / "zero network latency" — never measured. The gate
  does checks inline, so it costs something. Latency was not benchmarked.
- "validates ... completely out-of-band" / "out-of-band asynchronous
  processing loop" — validation is inline, before the response. Only
  the n8n forward is off the response path.
- "before internal memory stacks are exposed" / "before any unparsed
  data strings can touch internal memory" — Python's http.server reads
  the body into memory before validation.
- "Zero Packet Drops" / "internet-facing telemetry" — tests were
  localhost loopback, 3 requests in the main run + 12 in the extended
  suite. Not internet-facing, not a packet-drop test.
- "hallucination-free" — unproven, and the demo run used the labelled
  deterministic fallback, not a live LLM result.
- "feeds the structured STIX bundles into an analytical AI language
  model" — ai_analyzer.py reads the gate event log
  (dashboard/gate_events.jsonl), not the STIX bundle.
- "custom, high-speed" / "low-level, memory-safe" — it is Python
  stdlib ThreadingHTTPServer. No speed or memory-safety measurement.
- "Try it out: GitHub Repo — www.linkedin.com" — a LinkedIn URL is
  not a code repository. Replace with the public GitHub repo URL.
- Built With has no PayPal tag, and the text never says how PayPal
  is used. See the PayPal note in the revised copy below.

## Paste this into "About the project"

### Inspiration

In high-throughput e-commerce and agentic commerce, transaction
processing backends are exposed to webhook manipulation and semantic
data injection — payloads that look like valid transactions but
carry injection patterns or out-of-range amounts. Most application
security checks run after a payload has already been accepted for
processing. I built ETB PayShield, from Eternal Boundaries, as a
small HTTP gate that checks a transaction payload at the boundary
first — API key, payload size, JSON shape, required fields, amount
range, and an injection-pattern scan — and returns 403 for anything
that fails, before it reaches internal transaction handling.

### How we built it

The gate is Python 3, standard library only, using
ThreadingHTTPServer (`gate/proxy_listener.py`). It runs on localhost
(port 8080 by default) and is started by `run_tests.py` (cross-platform)
or `run_tests.ps1` (Windows PowerShell). The runners poll
`GET /health` until the gate is accepting connections, then run the
same three steps every time: an unauthorized request, an authenticated
injection payload, and a legitimate PayPal-format transaction.

Every decision is logged to `dashboard/gate_events.jsonl` with the
real SHA-256 of the raw body. Blocked events also produce a STIX 2.1
bundle (`dashboard/stix_bundle.json`) built from that payload.
`pipeline/ai_analyzer.py` builds `dashboard/ai_compliance_report.json`
from the gate event log: it first tries a local Ollama model
(`llama3`), and if Ollama is not reachable it uses a deterministic
fallback computed from the events, labelled in the report as
`analysis_source: deterministic_fallback_offline`.

PayPal — central to the project, not a label: the transaction the
gate protects is a PayPal transaction. Step B of `run_tests.py`
creates a real Sandbox order via the PayPal Orders API
(`pipeline/paypal_sandbox.py`, OAuth client-credentials at
api-m.sandbox.paypal.com, credentials via `PAYPAL_CLIENT_ID` /
`PAYPAL_CLIENT_SECRET` environment variables only), re-fetches it,
checks its amount ($149.00), then feeds that real Sandbox order ID
to the gate as the verified transaction. If Sandbox credentials are
not set, Step B says so on screen and falls back to a PayPal-format
payload only (`PAYPAL-TX-AUTO-777`) — that run verifies the gate,
but is not a PayPal API verification. Sandbox order creation and
fetch were verified against live Sandbox on 2026-11-05: order
42V51277WU110645W, status CREATED, $149.00 USD; see
`sandbox_run_log_2026-11-05.txt` in the repo.

### Challenges we ran into

The original gate failed its own first demo step: a fixed 2-second
sleep raced PowerShell job startup, so Step A failed with "Gate did
not initialize properly" while Step B passed seconds later. The fix
was a `GET /health` readiness poll (up to ~20s) in both runners.

The original gate also only checked the API key — any valid JSON
with the key passed, including injection payloads. The fix was real
validation (size cap, required fields, amount range, injection scan)
plus a new Step A2: a valid-key injection payload, proving the gate
is a validation gate and not only an auth gate. The original STIX
"SHA-256" was a random UUID hex, and the original AI report was a
hardcoded fallback analysing the verified $149 payload; both are now
derived from the actual event log.

### What we learned

Deterministic boundary checks and AI analysis do different jobs
well together: the gate makes a yes/no decision on the payload
itself, and the AI layer summarises the gate's actual decision log
for a compliance report. Keeping the report grounded in the event
log — and labelling the fallback when no LLM is reachable — is what
keeps the report honest about what was actually blocked and verified.

### What's next for ETB PayShield

Expand the dashboard view of blocked vs. verified events for SOC
review, and re-record the demo video so it shows the live Sandbox
path (the current video is the format-only run). STIX output follows
the STIX 2.1 bundle structure but has not been run through an
external STIX validator; the n8n blueprint is carried over
unexecuted.

### Verified results (for the submission description)

Main run: Step A 403 (no key), Step A2 403 (injection_pattern in
field 'note'), Step B 200 Verified, report 2 blocked / 1 verified.
Extended suite: 12/12 PASS — no key 403, wrong key 403, malformed
JSON 400, missing fields 403, negative amount 403, over-limit amount
403, XSS payload 403, legit payload 200, oversize body 403, unknown
GET 404, STIX hash equals the SHA-256 of the blocked body, event log
holds all 9 decisions (8 BLOCKED / 1 VERIFIED).

## Built With (replace the current tags)

python, powershell, json, stix, api, automation, ai, paypal

## Try it out (fix this — do not leave as LinkedIn)

Replace the current `www.linkedin.com` link with:
`https://github.com/Caseit1987/etb-payshield`

The repo must be public, with `LICENSE` (MIT) at the root and
`README.md` with the run instructions (`python
etb_payshield/run_tests.py`). The publish-ready folder is in this
bundle; see SUBMISSION-FIX.md for the `gh repo create` steps.

## Video

Keep the current Video URL (https://youtu.be/1rHbbGdxOfo) only if
that upload is the 68-second recorded run of `run_tests.py`.
