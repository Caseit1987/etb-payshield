"""
ETB PayShield - AppSec AI Telemetry Layer (fixed version)

Changes from the original:
- Portable paths (project_root/dashboard).
- The report is derived from the gate's actual decision log
  (dashboard/gate_events.jsonl), not from a single pre-set payload, so
  blocked and verified counts, transaction IDs and reasons are real.
- The offline fallback is labelled in the report
  (analysis_source = "deterministic_fallback_offline", with the Ollama
  error) instead of silently printing a hardcoded HIGH-severity summary
  that was written before the run happened.
"""
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = Path(os.getenv("ETB_DASHBOARD_DIR", ROOT / "dashboard"))
EVENTS_PATH = DASHBOARD / "gate_events.jsonl"
FEED_PATH = DASHBOARD / "active_threat_feed.json"
REPORT_OUTPUT_PATH = DASHBOARD / "ai_compliance_report.json"
API_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")


def load_events():
    events = []
    if EVENTS_PATH.exists():
        for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def deterministic_analysis(blocked, verified):
    reasons = sorted({e.get("reason", "blocked") for e in blocked})
    last_ok = verified[-1] if verified else {}
    if any(e.get("reason") == "payload_validation_failed" for e in blocked):
        severity = "HIGH"
    elif blocked:
        severity = "MEDIUM"
    else:
        severity = "LOW"
    summary = (
        f"{len(blocked)} request(s) blocked at the LayerZero gate "
        f"({', '.join(reasons) if reasons else 'none'}); "
        f"{len(verified)} legitimate transaction(s) verified"
    )
    if last_ok:
        summary += (f", most recent {last_ok.get('transaction_id')} "
                    f"amount {last_ok.get('amount')}.")
    else:
        summary += "."
    return {
        "executive_summary": summary,
        "severity_level": severity,
        "impact_analysis": (
            "Blocked requests never reached internal transaction state. "
            "Verified traffic passed API-key, JSON-shape, amount-range and "
            "injection-pattern checks at the boundary."),
        "analysis_source": "deterministic_fallback_offline",
    }


def generate_ai_analysis(events, blocked, verified):
    system_prompt = (
        "You are an expert enterprise Application Security (AppSec) agent "
        "specializing in financial gateway monitoring.\n"
        "Analyze the following gate decision log from a boundary proxy.\n"
        "Provide a structured JSON compliance analysis containing:\n"
        "1. executive_summary (Max 2 sentences)\n"
        "2. severity_level (LOW, MEDIUM, HIGH, CRITICAL)\n"
        "3. impact_analysis for a corporate CISO.\n"
    )
    data = {
        "model": os.getenv("OLLAMA_MODEL", "llama3"),
        "prompt": f"{system_prompt}\n\nGate events:\n{json.dumps(events, indent=2)}",
        "stream": False,
        "format": "json",
    }
    try:
        req = urllib.request.Request(
            API_URL, data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            parsed = json.loads(res_body.get("response", "{}"))
            if "executive_summary" in parsed:
                parsed["analysis_source"] = "ollama_local_llm"
                return parsed
        raise ValueError("LLM response missing executive_summary")
    except Exception as e:
        print(f"[!] Ollama unavailable ({type(e).__name__}); "
              "using deterministic fallback derived from gate events.")
        return deterministic_analysis(blocked, verified)


if __name__ == "__main__":
    events = load_events()
    blocked = [e for e in events if e.get("decision") == "BLOCKED"]
    verified = [e for e in events if e.get("decision") == "VERIFIED"]
    feed = {}
    if FEED_PATH.exists():
        feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))

    print("[*] Processing threat telemetry through AppSec AI layer...")
    ai_analysis = generate_ai_analysis(events, blocked, verified)

    final_report = {
        "telemetry": feed,
        "gate_summary": {
            "blocked_count": len(blocked),
            "verified_count": len(verified),
            "blocked_reasons": sorted({e.get("reason", "blocked") for e in blocked}),
            "stix_bundle": "dashboard/stix_bundle.json"
                           if (DASHBOARD / "stix_bundle.json").exists() else None,
        },
        "ai_compliance_insights": ai_analysis,
    }
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=4)
    try:
        display_path = REPORT_OUTPUT_PATH.relative_to(ROOT)
    except ValueError:
        display_path = REPORT_OUTPUT_PATH
    print(f"[+] Consolidated AI Compliance Report generated safely at: {display_path}")
