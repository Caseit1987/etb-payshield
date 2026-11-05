# ETB PayShield — fix for Kenneth Milburn's message (2026-11-05)

Deadline: **Thursday, November 12, 2026 at 12:00pm PT / 2:00pm CT.**
Edits go in the Devpost submission form — not in the message thread.

## What Kenneth flagged — and what's actually true

1. **No public repo / license / runnable demo on the submission.**
   True. The verified code lived only in the workspace, the MIT LICENSE
   was a draft in a side folder, and the form's "Try it out" link was a
   placeholder. Fixed in this folder — see below.

2. **"Does not seem to be built with the PayPal developer platform
   (Sandbox) and an AI tool/model/platform."**
   Half true, and the PayPal half is the real risk:
   - **AI: present in code.** `pipeline/ai_analyzer.py` tries local
     Ollama `llama3` first; if Ollama isn't running it uses a labelled
     deterministic fallback. That needs to be stated clearly in the
     submission so a judge running without Ollama isn't misled.
   - **PayPal: NOT present as an API call.** The gate validates
     PayPal-*format* payloads (`PAYPAL-TX-AUTO-777`, $149.00) — the
     words "sandbox payload" in the test script are just a label.
     There is no call to `api-m.sandbox.paypal.com`, no OAuth, no
     Orders API in the submitted code. Do not claim otherwise.
     `pipeline/paypal_sandbox.py` in this bundle is the real Sandbox
     client (OAuth + Orders API, env-var credentials only). It is
     **written but not yet run against live Sandbox**.

## Step 1 — publish this folder to GitHub (Justin, on your machine)

GitHub CLI here is not logged in, so this step needs you. From this
folder (`etb-payshield-public-repo/`):

```bash
git init
git add .
git commit -m "ETB PayShield: public Devpost submission (MIT)"
gh repo create etb-payshield --public --source=. --push
```

Then check on github.com that:
- `LICENSE` is at the repo root and GitHub shows "MIT" in the About section,
- `README.md` renders at the top,
- the repo is Public.

## Step 2 — paste this into the Devpost form

**"Try it out" / repository URL:** `<your new public GitHub repo URL>`

**Add to the submission description (paste as-is):**

> ETB PayShield is a Layer-Zero HTTP transaction gate. Run it with
> `python etb_payshield/run_tests.py` (Python 3, stdlib only, no
> credentials needed). Step A: unauthorized request → 403. Step A2:
> authenticated injection payload → 403. Step B: legitimate
> PayPal-format transaction → 200 Verified. Step C: compliance report
> generated, 2 blocked / 1 verified. Full wire verification is in
> VERIFICATION.md (extended suite 12/12).
>
> AI: the compliance report tries a local Ollama llama3 model first;
> if Ollama is not running it uses a deterministic fallback computed
> from the gate event log, labelled `analysis_source:
> deterministic_fallback_offline` in the report.
>
> PayPal status: this version validates PayPal-format transaction
> payloads at the gate. The repo includes
> `pipeline/paypal_sandbox.py`, a PayPal Sandbox client (OAuth +
> Orders API at api-m.sandbox.paypal.com, credentials via
> PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET env vars only). [Delete
> one of the next two sentences before submitting:]
> — If Sandbox has been run and logged: "Sandbox order creation and
> fetch were verified against live Sandbox on <date>; see the log."
> — If not yet run: "The Sandbox client is included but has not yet
> been run against live Sandbox."

## Step 3 — the PayPal decision (pick one before Nov 12)

**Option A — Publish as-is + disclose (fastest).**
Publish the repo, paste the text above with the "not yet run"
sentence. Fixes gap 1 completely. Gap 2 stays open: a judge may
still rule it ineligible for not using the PayPal platform. No new
code to test.

**Option B — Run the Sandbox integration first, then submit (real fix).**
1. In developer.paypal.com, create a Sandbox app, copy its Client ID
   and Secret (do not paste them in chat — env vars only).
2. Run with them set:
   `PAYPAL_CLIENT_ID='...' PAYPAL_CLIENT_SECRET='...' python etb_payshield/run_tests.py`
   Step B will now create a real Sandbox order, re-fetch it, check
   the $149.00 amount, and feed that real order ID to the gate.
   Save that run's log — it is the PayPal evidence.
3. Then paste the "verified against live Sandbox" sentence, and
   re-record the demo video if the video is meant to show the
   Sandbox path — done 2026-11-05: the demo video now shows the live
   Sandbox run (order 39Q34089QY7990S36; see
   sandbox_run_log_2026-11-05_rerecord.txt).
This is the only option that actually answers Kenneth's second
point — and the hackathon's own rule: PayPal must be used
meaningfully and centrally, not just as a payload format.

## What NOT to do

- Do not paste a PayPal Client ID / Secret anywhere in Devpost, GitHub, or chat.
- Do not claim the current Step B is a PayPal API call, or that the
  n8n blueprint is live automation, or that STIX output is externally
  validated — none of those are verified.
- Do not reply only in the Devpost message thread. Kenneth's note
  says to add it to the submission form.
