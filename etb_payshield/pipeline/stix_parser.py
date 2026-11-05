"""
ETB PayShield - Threat Serialization Engine (fixed version)

Changes from the original: the observed-data hash is now the real SHA-256
of the intercepted payload (supplied by the gate), not a random UUID hex
placeholder, and the classification is read from telemetry_class as well
as class. Output follows the STIX 2.1 bundle structure; it has not been
run through an external STIX validator.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone


def generate_stix_bundle(anomaly_data, raw_sha256=None):
    bundle_id = f"bundle--{uuid.uuid4()}"
    indicator_id = f"indicator--{uuid.uuid4()}"
    observed_id = f"observed-data--{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    classification = (anomaly_data.get("telemetry_class")
                      or anomaly_data.get("class")
                      or "Unknown Threat Classification")
    if raw_sha256 is None:
        raw_sha256 = hashlib.sha256(
            json.dumps(anomaly_data, sort_keys=True).encode()).hexdigest()

    indicator = {
        "type": "indicator",
        "spec_version": "2.1",
        "id": indicator_id,
        "created": timestamp,
        "modified": timestamp,
        "name": f"ETB LayerZero Intercept: {classification}",
        "description": "Anomalous transactional telemetry structure neutralized at the system boundary gate.",
        "indicator_types": ["malicious-activity"],
        "pattern": f"[network-traffic:dst_port = {os.getenv('GATE_PORT', '8080')}]",
        "pattern_type": "stix",
        "valid_from": timestamp,
    }
    observed = {
        "type": "observed-data",
        "spec_version": "2.1",
        "id": observed_id,
        "created": timestamp,
        "modified": timestamp,
        "first_observed": timestamp,
        "last_observed": timestamp,
        "number_observed": 1,
        "objects": {
            "0": {
                "type": "file",
                "name": "raw_transaction_payload.json",
                "hashes": {"SHA-256": raw_sha256},
            }
        },
    }
    return {"type": "bundle", "id": bundle_id, "objects": [indicator, observed]}


if __name__ == "__main__":
    sample_anomaly = {"status": "Anomaly Neutralized", "class": "Malformed JSON Input Pattern"}
    print(json.dumps(generate_stix_bundle(sample_anomaly), indent=4))
