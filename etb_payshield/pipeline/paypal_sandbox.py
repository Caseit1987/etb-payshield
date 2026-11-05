"""
PayPal Sandbox client for ETB PayShield — NEW, NOT YET VERIFIED LIVE.

Purpose: close the eligibility gap flagged 2026-11-05 — the gate as
submitted validates PayPal-*format* payloads but does not call the
PayPal Developer Platform. This module is the real Sandbox integration:
OAuth 2.0 client-credentials token + Orders API against
https://api-m.sandbox.paypal.com (default; override with PAYPAL_BASE_URL).

Credentials come ONLY from the environment:
  PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET
No credentials are stored in this repo. Never commit a .env with them.

Usage (after creating a Sandbox app at developer.paypal.com):
  export PAYPAL_CLIENT_ID='...'
  export PAYPAL_CLIENT_SECRET='...'
  python etb_payshield/pipeline/paypal_sandbox.py --create-order 149.00 USD
  # prints the Sandbox order id + amount; feed those to the gate as
  # transaction_id / amount in a Step-B-style verified request.

Status: written 2026-11-05, wired into run_tests.py Step B, and
VERIFIED against live Sandbox on Windows on 2026-11-05: order
42V51277WU110645W, status CREATED, $149.00 USD, created + re-fetched
via the Orders API, then fed to the gate as the verified transaction
(Step B 200). See sandbox_run_log_2026-11-05.txt in the repo root.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").rstrip("/")


def _auth_header(client_id, client_secret):
    token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"}


def get_access_token(client_id=None, client_secret=None):
    client_id = client_id or os.getenv("PAYPAL_CLIENT_ID")
    client_secret = client_secret or os.getenv("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (Sandbox app credentials).")
    req = urllib.request.Request(
        f"{BASE_URL}/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        headers=_auth_header(client_id, client_secret),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())["access_token"]


def _api(method, path, access_token, body=None):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"PayPal Sandbox {method} {path} failed: {e.code} {e.read().decode()[:500]}")


def create_order(access_token, amount="149.00", currency="USD"):
    return _api("POST", "/v2/checkout/orders", access_token, {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": currency, "value": str(amount)}}],
    })


def get_order(access_token, order_id):
    return _api("GET", f"/v2/checkout/orders/{order_id}", access_token)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="PayPal Sandbox helper for ETB PayShield")
    p.add_argument("--create-order", metavar="AMOUNT", help="Create a Sandbox order for this amount")
    p.add_argument("--currency", default="USD")
    p.add_argument("--get-order", metavar="ORDER_ID", help="Fetch a Sandbox order by id")
    a = p.parse_args()
    token = get_access_token()
    if a.create_order:
        order = create_order(token, a.create_order, a.currency)
        print(json.dumps(order, indent=2))
        print(f"\nGate payload: transaction_id={order.get('id')} amount={a.create_order}")
    elif a.get_order:
        print(json.dumps(get_order(token, a.get_order), indent=2))
    else:
        p.print_help()
        sys.exit(2)
