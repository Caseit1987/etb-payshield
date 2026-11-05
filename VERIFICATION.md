# ETB PayShield — grade of the original, fixes applied, verification results

Date: 2026-10-23. Source graded: the 9 files Justin supplied from
`C:\Users\casei\Desktop\etb_payshield\` (7,791-byte zip).

## What the original actually did

- `gate/proxy_listener.py` — a real HTTP server, but the only 403 check was
  an API-key header. Any valid JSON with the key passed, including malicious
  payloads: no shape, field, amount, length or injection validation, despite
  the project story claiming all of those. Verified payloads were written to
  a hardcoded Windows path, and the n8n forward ran synchronously after the
  response on a single-threaded server.
- `run_tests.ps1` Step A failure ("Gate did not initialize properly") was a
  startup race: a fixed `Start-Sleep 2` against slow PowerShell
  `Start-Job` + Python startup. Step B ran seconds later, by which time the
  gate was up — which is why B passed and A did not.
- `pipeline/stix_parser.py` — STIX-shaped bundle builder, but nothing in the
  test pipeline ever called it (only an n8n blueprint node, with no input),
  and the observed-data "SHA-256" was a random UUID hex placeholder.
- `pipeline/ai_analyzer.py` — tries Ollama (llama3, localhost:11434); on any
  failure it silently returned a hardcoded summary — HIGH severity,
  "Anomalous input format successfully isolated…" — written before the run.
  The report Justin pasted on 2026-10-23 is that fallback verbatim, and it
  analysed the *verified* $149 payload, not a blocked threat.
- `README.md` — one slogan line, duplicated.

## Fixes in this package (`etb_payshield/`)

1. Portable paths everywhere (`$PSScriptRoot` / project root); job receives
   its environment explicitly.
2. Startup race fixed with a `GET /health` readiness poll (up to ~20s) in
   both runners.
3. Real boundary validation: size cap, required fields, transaction-ID
   format, amount range (0, 100000], injection-pattern scan of all string
   values. Failures → 403; malformed JSON → 400.
4. Threaded gate; n8n forward off the response path.
5. Every decision logged to `dashboard/gate_events.jsonl` with the real
   SHA-256 of the raw body; blocked events generate
   `dashboard/stix_bundle.json` with that hash via the STIX builder.
6. Report derived from the event log (blocked/verified counts, reasons,
   last verified transaction). Ollama is still tried first; the fallback is
   deterministic, computed from the events, and labelled
   `analysis_source: deterministic_fallback_offline` in the report.
7. New Step A2 in both runners: a valid-key injection payload, proving the
   gate is a validation gate and not only an auth gate.
8. `run_tests.py` cross-platform mirror of `run_tests.ps1` (same steps and
   wording) for Linux/macOS and for the recorded demo.

## Verification (on the wire, this machine, 2026-10-23)

Main pipeline (`run_tests.py`, the run recorded in the demo video):
Step A 403 blocked · Step A2 403 blocked (injection_pattern in 'note') ·
Step B 200 Verified · Step C report generated: 2 blocked / 1 verified,
severity HIGH (injection present), source labelled as fallback.

Extended suite (12 checks, separate run): **12/12 PASS** — no key 403,
wrong key 403, malformed JSON 400, missing fields 403, negative amount 403,
over-limit amount 403, XSS payload 403, legit payload 200 Verified,
oversize body 403, unknown GET 404, STIX hash equals the SHA-256 of the
blocked body, event log contains all 9 decisions (8 BLOCKED / 1 VERIFIED).

Not claimed: the STIX output follows the STIX 2.1 bundle structure but has
not been run through an external STIX validator; the n8n blueprint is
carried over from the original and was not executed; on Windows the
PowerShell runners were updated to the same logic as the verified Python
runner but were not executed on a Windows machine in this pass.
