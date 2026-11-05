# ETB PayShield — Layer-Zero HTTP Transaction Gate

A lightweight HTTP boundary gate for transaction telemetry. Requests are
checked at the boundary, before any internal processing: API key, payload
size, JSON shape, required transaction fields, amount range, and an
injection-pattern scan over every string value.

- Blocked: HTTP 403 (missing/invalid key, oversize payload, failed
  validation including injection patterns). Malformed JSON: HTTP 400.
- Verified: HTTP 200 `{"status": "Verified", "gateway": "ETB LayerZero Gate Passed"}`
- Health/readiness: `GET /health` → 200 `{"status": "ok", ...}`

Every decision is appended to `etb_payshield/dashboard/gate_events.jsonl`
with the SHA-256 of the raw body. Blocked events generate a STIX 2.1 bundle
at `etb_payshield/dashboard/stix_bundle.json` containing the real payload
hash.

## Run it (judges — no dependencies beyond Python 3 stdlib)

```bash
python etb_payshield/run_tests.py
```

Expected output:

- Step A: unauthorized request → **403**
- Step A2: authenticated injection payload → **403**
  (`injection_pattern in field 'note'`)
- Step B: legitimate PayPal-format transaction → **200 Verified**
- Step C: compliance report generated — **2 blocked / 1 verified**

Windows (PowerShell):

```powershell
.\etb_payshield\run_tests.ps1
```

The runners poll `GET /health` until the gate is actually accepting
connections (no fixed sleep). The demo gate key is
`EB-COMMAND-CENTER-SECURE-KEY` — set `GATE_ENGINE_API_KEY` to override it.
No PayPal or AI credentials are needed to run the gate demo.

See `VERIFICATION.md` for the full wire verification (main pipeline plus
the extended 12/12 suite) and `demo_run_log.txt` for the recorded run.

## AI layer — what it actually is

`etb_payshield/pipeline/ai_analyzer.py` builds
`dashboard/ai_compliance_report.json` from the gate's actual decision log.

- It first tries a local Ollama model (`OLLAMA_MODEL`, default `llama3`,
  at `OLLAMA_URL`, default `http://localhost:11434/api/generate`).
- If Ollama is not reachable, it uses a deterministic fallback computed
  from the gate events, and labels it in the report as
  `analysis_source: deterministic_fallback_offline`.
- The fallback is not presented as an LLM result.

To see the LLM path, run Ollama locally with `llama3` before running
`run_tests.py`. Without Ollama, the gate, the 403/200 decisions, and the
report still run and verify exactly as logged.

## PayPal — how it is central, and honest status

PayPal is the transaction being gated. Step B of `run_tests.py` is
the PayPal step:

1. If `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` are set,
   `run_tests.py` calls `pipeline/paypal_sandbox.py` to create a
   real Sandbox order via the Orders API
   (`https://api-m.sandbox.paypal.com`, OAuth client-credentials),
   re-fetches that order, checks its amount ($149.00), then feeds
   the real Sandbox order ID and amount to the gate as the verified
   transaction. If the Sandbox call fails with credentials set, the
   run fails loudly instead of silently substituting a fake payload.
2. If no Sandbox credentials are set, Step B prints that clearly
   and uses a PayPal-format payload only (`PAYPAL-TX-AUTO-777`,
   $149.00). That run still verifies the gate, but it is **not** a
   PayPal API verification.

No PayPal credentials are in this repo. The Sandbox integration was
**verified live on Windows on 2026-11-05**: Sandbox order
`42V51277WU110645W` (status CREATED, $149.00 USD) was created and
re-fetched via the Orders API, then fed to the gate as the verified
transaction — Step B 200 Verified. See
`sandbox_run_log_2026-11-05.txt` for that run.

To run the full PayPal path:

```bash
export PAYPAL_CLIENT_ID='...'
export PAYPAL_CLIENT_SECRET='...'
python etb_payshield/run_tests.py
```

Create the Sandbox app at developer.paypal.com first (free).

## Files

- `etb_payshield/gate/proxy_listener.py` — the gate (stdlib `http.server`, threaded)
- `etb_payshield/pipeline/stix_parser.py` — STIX 2.1 bundle builder
- `etb_payshield/pipeline/ai_analyzer.py` — compliance report from the gate event log
- `etb_payshield/pipeline/paypal_sandbox.py` — optional PayPal Sandbox client (see above)
- `etb_payshield/pipeline/n8n_workflow_blueprint.json` — optional n8n forwarding layout
  (the gate posts verified payloads to n8n off the response path; the
  pipeline runs fine without n8n, and the blueprint has not been executed)
- `etb_payshield/dashboard/` — generated outputs; regenerated on every run

## License

MIT — see `LICENSE`. Copyright (c) 2026 Justin Schomer / Eternal Boundaries.
