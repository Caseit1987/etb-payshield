"""
ETB PayShield - LayerZero Verification Gate (fixed version)

Changes from the original Justin supplied 2026-10-23:
- Portable paths (no hardcoded C:\\Users\\casei\\...), dashboard dir is
  <project_root>/dashboard unless ETB_DASHBOARD_DIR is set.
- ThreadingHTTPServer + n8n forward moved off the response path, so a slow
  or absent n8n cannot stall the gate.
- Real payload validation, not just an API-key check: required transaction
  fields, amount range, payload size cap, and an injection-pattern scan
  over every string value. Validation failures return 403.
- Every decision is logged to dashboard/gate_events.jsonl with the SHA-256
  of the raw body. Blocked events also produce a STIX 2.1 bundle
  (dashboard/stix_bundle.json) built from the actual payload.
- GET /health readiness endpoint, used by run_tests to poll instead of
  sleeping a fixed 2 seconds (the original Step A startup race).
"""
import hashlib
import json
import os
import re
import sys
import threading
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = Path(os.getenv("ETB_DASHBOARD_DIR", ROOT / "dashboard"))
HOST = os.getenv("GATE_HOST", "localhost")
PORT = int(os.getenv("GATE_PORT", "8080"))
N8N_URL = os.getenv("N8N_PIPELINE_URL", "http://localhost:5678/webhook/etb-threats")
API_KEY = os.getenv("GATE_ENGINE_API_KEY", "EB-COMMAND-CENTER-SECURE-KEY")
MAX_BODY = 16384

sys.path.insert(0, str(ROOT / "pipeline"))
try:
    from stix_parser import generate_stix_bundle
except Exception:  # STIX is a reporting extra; never break the gate for it
    generate_stix_bundle = None

INJECTION_PATTERNS = [
    r"<\s*script", r"javascript\s*:", r"'\s*or\s+", r'"\s*or\s+',
    r";\s*(drop|delete|insert|update)\s", r"\bunion\s+select\b",
    r"\.\./", r"\.\.\\", r"\$\{", r"\{\{", r"--\s*$", r"\bdrop\s+table\b",
]
INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
TX_ID_RE = re.compile(r"^[A-Za-z0-9\-_]{3,64}$")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scan_strings(value, path=""):
    hits = []
    if isinstance(value, str):
        for rx in INJECTION_RE:
            if rx.search(value):
                hits.append(f"injection_pattern in field '{path or 'body'}'")
                break
    elif isinstance(value, dict):
        for k, v in value.items():
            hits += scan_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            hits += scan_strings(v, f"{path}[{i}]")
    return hits


def validate_payload(payload):
    """Return a list of violations; empty list means the payload is clean."""
    if not isinstance(payload, dict):
        return ["payload is not a JSON object"]
    violations = []
    tx = payload.get("transaction_id")
    if not isinstance(tx, str) or not TX_ID_RE.match(tx):
        violations.append("transaction_id missing or not [A-Za-z0-9-_]{3,64}")
    amount = payload.get("amount")
    try:
        amt = Decimal(str(amount))
        if amt <= 0 or amt > Decimal("100000"):
            violations.append("amount out of allowed range (0, 100000]")
    except (InvalidOperation, ValueError, TypeError):
        violations.append("amount missing or not a valid number")
    status = payload.get("status")
    if not isinstance(status, str) or not (1 <= len(status) <= 40):
        violations.append("status missing or invalid length")
    violations += scan_strings(payload)
    return violations


def log_event(event):
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD / "gate_events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    if event["decision"] == "BLOCKED" and generate_stix_bundle is not None:
        try:
            bundle = generate_stix_bundle(
                {"class": event.get("reason", "blocked"),
                 "telemetry_class": event.get("telemetry_class")},
                raw_sha256=event["raw_sha256"])
            with open(DASHBOARD / "stix_bundle.json", "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=4)
        except Exception as e:
            print(f"[-] STIX generation error: {e}")


class ETBValidationGate(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            body = b'{"status": "ok", "gate": "ETB PayShield LayerZero Gate"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        raw_sha = hashlib.sha256(raw).hexdigest()
        base = {"timestamp": utc_now(), "raw_sha256": raw_sha,
                "client": self.client_address[0]}

        if length > MAX_BODY:
            log_event({**base, "decision": "BLOCKED",
                       "reason": "payload_too_large"})
            return self._reply(403, {"error": "LayerZero Gate: Payload exceeds size limit"})

        if self.headers.get("X-ETB-Key") != API_KEY:
            log_event({**base, "decision": "BLOCKED",
                       "reason": "missing_or_invalid_api_key"})
            return self._reply(403, {"error": "LayerZero Gate: Unauthorized Access Defended"})

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            log_event({**base, "decision": "BLOCKED", "reason": "malformed_json"})
            return self._reply(400, {"error": "LayerZero Gate: Malformed JSON"})

        violations = validate_payload(payload)
        if violations:
            log_event({**base, "decision": "BLOCKED",
                       "reason": "payload_validation_failed",
                       "violations": violations,
                       "transaction_id": payload.get("transaction_id"),
                       "telemetry_class": payload.get("telemetry_class")})
            return self._reply(403, {"error": "LayerZero Gate: Payload validation failed",
                                     "violations": violations})

        DASHBOARD.mkdir(parents=True, exist_ok=True)
        with open(DASHBOARD / "active_threat_feed.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        log_event({**base, "decision": "VERIFIED", "reason": "passed_all_checks",
                   "transaction_id": payload.get("transaction_id"),
                   "amount": payload.get("amount"),
                   "telemetry_class": payload.get("telemetry_class")})
        self._reply(200, {"status": "Verified", "gateway": "ETB LayerZero Gate Passed"})

        def forward():
            try:
                req = urllib.request.Request(
                    N8N_URL, data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=2):
                    pass
            except Exception:
                pass
        threading.Thread(target=forward, daemon=True).start()


if __name__ == "__main__":
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    print(f"[*] ETB PayShield LayerZero Gate running on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), ETBValidationGate).serve_forever()
