# ETB PayShield — Layer-Zero Verification Gate

A lightweight HTTP boundary gate for transaction telemetry. Requests are
checked at the boundary, before any internal processing: API key, payload
size, JSON shape, required transaction fields, amount range, and an
injection-pattern scan over every string value.

- Blocked: HTTP 403 (missing/invalid key, oversize payload, failed
  validation including injection patterns). Malformed JSON: HTTP 400.
- Verified: HTTP 200 `{"status": "Verified", "gateway": "ETB LayerZero Gate Passed"}`
- Health/readiness: `GET /health` → 200 `{"status": "ok", ...}`

Every decision is appended to `dashboard/gate_events.jsonl` with the
SHA-256 of the raw body. Blocked events generate a STIX 2.1 bundle at
`dashboard/stix_bundle.json` containing the real payload hash.
`pipeline/ai_analyzer.py` builds `dashboard/ai_compliance_report.json`
from that event log: it uses a local Ollama model when one is reachable,
and otherwise a deterministic fallback that is labelled as such in the
report (`analysis_source`).

## Run it

Windows (PowerShell):
```powershell
.\etb_payshield\run_tests.ps1
```

Windows / Linux / macOS (Python 3, no dependencies beyond the stdlib):
```bash
python etb_payshield/run_tests.py
```

`run_tests` recycles any previous gate, starts
`gate/proxy_listener.py`, polls `/health` until the gate is actually
accepting connections (no fixed sleep), then runs: unauthorized request
(403), authenticated injection payload (403), legitimate PayPal-format
transaction (200), and the compliance-report step.

## Files

- `gate/proxy_listener.py` — the gate (stdlib `http.server`, threaded)
- `pipeline/stix_parser.py` — STIX 2.1 bundle builder
- `pipeline/ai_analyzer.py` — compliance report from the gate event log
- `pipeline/n8n_workflow_blueprint.json` — optional n8n forwarding layout
  (the gate posts verified payloads to n8n off the response path; the
  pipeline runs fine without n8n)
- `dashboard/` — generated outputs: `active_threat_feed.json` (last
  verified payload), `gate_events.jsonl`, `stix_bundle.json`,
  `ai_compliance_report.json`
