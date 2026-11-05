"""Cross-platform mirror of run_tests.ps1 (same steps, same output wording).
Used for CI / Linux / macOS runs and for the recorded demo, where PowerShell
is not available. On Windows, run_tests.ps1 remains the primary runner."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:8080"
KEY = "EB-COMMAND-CENTER-SECURE-KEY"
PACE = float(os.getenv("ETB_DEMO_PACE", "0.4"))


def pause():
    time.sleep(PACE)


def post(body, headers=None):
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return None, {"error": str(e)}


def get_paypal_sandbox_order(amount="149.00", currency="USD"):
    """Create + re-fetch a real PayPal Sandbox order, if creds are set.

    Returns (order_id, amount) on success, or None if no Sandbox
    credentials are configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET).
    Raises SystemExit on a Sandbox API failure when creds ARE set, so a
    failed PayPal check is never silently replaced by a format-only
    payload and presented as a verified PayPal transaction.
    """
    if not os.getenv("PAYPAL_CLIENT_ID") or not os.getenv("PAYPAL_CLIENT_SECRET"):
        print("[!] PayPal Sandbox not configured (set PAYPAL_CLIENT_ID and")
        print("    PAYPAL_CLIENT_SECRET to use a real Sandbox order).")
        print("    Step B will use a PayPal-format payload only — this is")
        print("    NOT a PayPal API verification.")
        return None
    sys.path.insert(0, str(ROOT / "pipeline"))
    from paypal_sandbox import get_access_token, create_order, get_order
    print("[*] PayPal Sandbox: creating order via Orders API...")
    token = get_access_token()
    order = create_order(token, amount, currency)
    order_id = order.get("id")
    print(f"[+] PayPal Sandbox order created: {order_id} (status: {order.get('status')})")
    fetched = get_order(token, order_id)
    fetched_amount = fetched.get("purchase_units", [{}])[0].get("amount", {})
    print(f"[+] PayPal Sandbox order re-fetched: status={fetched.get('status')} "
          f"amount={fetched_amount.get('value')} {fetched_amount.get('currency_code')}")
    if fetched_amount.get("value") != amount:
        raise SystemExit(f"PayPal Sandbox amount mismatch: expected {amount}, "
                         f"got {fetched_amount.get('value')}")
    return order_id, amount


def wait_ready(proc, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=1) as r:
                if json.loads(r.read().decode()).get("status") == "ok":
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    print("====================================================")
    print("[*] Initializing Automated ETB PayShield Testing Loop...")
    print("====================================================")
    events = ROOT / "dashboard" / "gate_events.jsonl"
    if events.exists():
        events.unlink()
    env = {**os.environ, "GATE_HOST": "localhost", "GATE_PORT": "8080",
           "GATE_ENGINE_API_KEY": KEY,
           "N8N_PIPELINE_URL": "http://localhost:5678/webhook/etb-threats"}
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "gate" / "proxy_listener.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        print("[*] Launching ETB PayShield System Infrastructure...")
        print("[*] Waiting for gate to accept connections...")
        if not wait_ready(proc):
            print("[-] Gate did not become ready within 20 seconds.")
            return 1
        print("[+] Gate is ready.")
        pause()

        print("\n[*] Automation Step A: Launching unauthorized simulation string...")
        code, _ = post({"unauthorized_test": True})
        if code == 403:
            print("[?] Success: Gate actively blocked request with HTTP Status Code: 403")
        else:
            print(f"[-] Unexpected result for Step A: {code}")
        pause()

        print("\n[*] Automation Step A2: Authenticated injection payload (valid key, malicious body)...")
        code, body = post(
            {"transaction_id": "PAYPAL-TX-INJ-001", "amount": "149.00",
             "status": "AUTOMATION_STREAMED",
             "telemetry_class": "Zero-Click Ingestion Pipeline Active",
             "note": "'; DROP TABLE transactions; --"},
            {"X-ETB-Key": KEY})
        if code == 403:
            print("[?] Success: Gate blocked injection payload with HTTP Status Code: 403")
            print(f"    Violations: {body.get('violations')}")
        else:
            print(f"[-] Unexpected result for Step A2: {code} {body}")
        pause()

        print("\n[*] Automation Step B: PayPal Sandbox order -> gate...")
        sandbox = get_paypal_sandbox_order()
        if sandbox:
            tx_id, tx_amount = sandbox
            print(f"[*] Step B transaction is a real Sandbox order: {tx_id}")
        else:
            tx_id, tx_amount = "PAYPAL-TX-AUTO-777", "149.00"
        code, body = post(
            {"transaction_id": tx_id, "amount": tx_amount,
             "status": "AUTOMATION_STREAMED",
             "telemetry_class": "Zero-Click Ingestion Pipeline Active"},
            {"X-ETB-Key": KEY})
        if code == 200 and body.get("status") == "Verified":
            print("[?] Success: Gate successfully passed telemetry array. Response: Gateway Verified (HTTP 200).")
        else:
            print(f"[-] Unexpected result for Step B: {code} {body}")
        pause()

        print("\n[*] Automation Step C: Triggering out-of-band AI synthesis engine...")
        subprocess.run([sys.executable, str(ROOT / "pipeline" / "ai_analyzer.py")], check=False)
        pause()

        print("\n====================================================")
        print("[?] AUTOMATION PIPELINE RUN COMPLETE")
        print("====================================================")
        print("[*] Outputting final CISO compliance report matrix below:\n")
        report = ROOT / "dashboard" / "ai_compliance_report.json"
        print(report.read_text())
        stix = ROOT / "dashboard" / "stix_bundle.json"
        if stix.exists():
            print("[*] STIX 2.1 bundle for the blocked event (dashboard/stix_bundle.json):\n")
            print(stix.read_text())
        print("====================================================")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
