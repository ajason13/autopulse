"""Production processor/export boundary, including privacy and invalid metadata."""
from copy import deepcopy
import json
from typing import get_args
from uuid import UUID

import pytest

from autopulse.alert_exporter import serialize_alert
from autopulse.analysis.pdm_processor import FailureType, PdMProcessor

VIN_HASH = "a" * 64


def frame(timestamp=0, **changes):
    return dict(timestamp=timestamp, engine_rpm=900.0, engine_load=5.0,
                coolant_temp=40.0, ambient_temp=25.0, **changes)


def production_alerts():
    processor = PdMProcessor(VIN_HASH, window_size=1)
    healthy = processor.process_frame(frame())
    hdf = processor.process_frame(dict(frame(60000), coolant_temp=30.0))
    sensor = processor.process_frame({"timestamp": 61000})

    processor = PdMProcessor(VIN_HASH)
    for second in range(59):
        processor.process_frame(dict(frame(second * 1000), coolant_temp=90.0))
    statistical = processor.process_frame(dict(frame(70000), coolant_temp=140.0))

    processor = PdMProcessor(VIN_HASH)
    for second in range(61):
        alert = processor.process_frame(dict(frame(second * 1000), engine_load=90.0))
        if second == 31:
            osf_anomaly = alert
    return [healthy, hdf, sensor, statistical, osf_anomaly, alert]


@pytest.mark.parametrize("alert", production_alerts(), ids=lambda a: a.failure_type)
def test_every_production_outcome_exports(alert):
    before = deepcopy(alert)
    payload = serialize_alert(alert)
    assert payload["failure_type"] == alert.failure_type
    assert payload["failure_probability"] == alert.failure_probability
    assert payload["timestamp"] == alert.timestamp
    assert payload["is_anomaly"] is alert.is_anomaly
    assert payload["primary_pid"] == alert.primary_pid
    assert payload["window_summary"] == alert.window_summary
    assert payload["vin_hashed"] == VIN_HASH
    assert payload["@type"] == "sosa:Observation"
    assert UUID(payload["@id"].removeprefix("urn:uuid:")).version == 4
    assert "obd_frame" not in payload
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    assert alert == before


def test_all_declared_processor_outcomes_exercised():
    assert {a.failure_type for a in production_alerts()} == set(get_args(FailureType))


@pytest.mark.parametrize("field,value", [
    ("timestamp", True), ("timestamp", 1.5), ("timestamp", float("nan")),
    ("timestamp", -62135596800001), ("timestamp", 253402300800000),
    ("timestamp", "1HGCM82633A004352"),
    ("is_anomaly", 1), ("is_anomaly", "1HGCM82633A004352"),
    ("primary_pid", True), ("primary_pid", -1), ("primary_pid", 256),
    ("primary_pid", float("inf")), ("primary_pid", "1HGCM82633A004352"),
    ("failure_type", "UNKNOWN"), ("failure_type", []),
    ("failure_type", "1HGCM82633A004352"),
    ("failure_probability", float("nan")), ("failure_probability", float("inf")),
    ("failure_probability", True), ("failure_probability", -0.1),
    ("failure_probability", 1.1), ("vin_hashed", "1HGCM82633A004352"),
    ("window_summary", {"nested": {"value": float("nan")}}),
    ("window_summary", {"nested": {"value": "1HGCM82633A004352"}}),
    ("window_summary", {"raw_vin": "sensitive"}),
])
def test_malformed_processor_fields_reject_without_sensitive_errors(field, value):
    alert = production_alerts()[0]
    # Mutability must not bypass export validation (including identity).
    setattr(alert, field, value)
    with pytest.raises((TypeError, ValueError)) as error:
        serialize_alert(alert)
    assert "1HGCM82633A004352" not in str(error.value)
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("index", range(6))
def test_raw_frame_never_traversed_and_summary_sanitization_retained(index):
    alert = production_alerts()[index]
    alert.obd_frame = {"vin": "1HGCM82633A004352", "payload_bytes": object(),
                       "engine_rpm": float("nan")}
    alert.window_summary = {"nested": {"@context": "https://example.invalid",
                            "payload_bytes": [1, 2], "service_0x2E": "secret",
                            "avg": 900.0}}
    payload = serialize_alert(alert)
    assert payload["window_summary"] == {"nested": {"avg": 900.0}}
    serialized = json.dumps(payload, allow_nan=False)
    assert "1HGCM82633A004352" not in serialized
    assert "secret" not in serialized
    assert "example.invalid" not in serialized
    payload["window_summary"]["nested"]["avg"] = 0
    payload["@context"]["timestamp"] = "changed"
    assert alert.window_summary["nested"]["avg"] == 900.0
    assert serialize_alert(alert)["@context"]["timestamp"] == "autopulse:unixTimeMilliseconds"


def test_duck_typed_objects_reject():
    with pytest.raises(TypeError):
        serialize_alert({"failure_type": "HDF"})
