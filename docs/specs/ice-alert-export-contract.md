# ICE processor observations at the export boundary

`autopulse.alert_exporter.serialize_alert()` accepts the production
`autopulse.analysis.pdm_processor.PdMAlert` directly. The boundary explicitly
selects export fields; it never traverses or serializes `obd_frame`.
The existing exporter `PdMAlert` constructor and HDF/OSF validation remain
supported. Callers do not need to rebuild processor alerts as that legacy type.

```python
from autopulse.alert_exporter import serialize_alert
from autopulse.analysis.pdm_processor import PdMProcessor

processor = PdMProcessor(vin_hashed="a" * 64)  # synthetic identity
observation = serialize_alert(processor.process_frame({
    "timestamp": 0, "engine_rpm": 900, "engine_load": 5,
    "coolant_temp": 40, "ambient_temp": 25,
}))
```

All six processor outcomes export as `sosa:Observation`, without filtering or
relabeling. Consumers must inspect `failure_type` and `is_anomaly`; observation
presence alone does not indicate an anomaly or a vehicle fault.

| Processor outcome | Exported failure_type | Meaning |
| --- | --- | --- |
| HDF | HDF | Eligible synthetic thermal score |
| OSF | OSF | Full recent-condition exposure |
| OSF_ANOMALY | OSF_ANOMALY | Partial recent-condition exposure above threshold |
| STATISTICAL_ANOMALY | STATISTICAL_ANOMALY | Rolling-window statistical outlier |
| SENSOR_ERROR | SENSOR_ERROR | Rejected sensor sample; not HDF/OSF |
| NONE | NONE | No selected anomaly; not HDF/OSF |

Processor exports additionally preserve `timestamp` (integer Unix milliseconds,
including zero, with the [processor time contract](processor-time-contract.md)
range), `is_anomaly` (boolean), and `primary_pid` (integer byte or null).
Their fixed inline context aliases are `autopulse:unixTimeMilliseconds`,
`autopulse:isAnomaly`, and `autopulse:primaryPID`. The legacy exporter type has
no such metadata; its exports omit these three fields. Each export gets a fresh
UUID observation identifier; it is not a stable event deduplication key.

The boundary validates the hash, finite score in [0, 1], supported outcome and
metadata types before returning a payload. Unknown outcomes reject. The existing
recursive summary sanitization and inline JSON-LD context remain in force:
restricted service/payload/context keys are removed, raw VIN fields/values and
non-finite or unsupported values reject, and summaries are copied. No context
URL is fetched. Exceptions use field descriptions without echoing field values.
No raw frame, sensor-error detail, or arbitrary alert attributes are exported.

These are offline experimental scores, not calibrated failure probabilities or
confirmed diagnoses; the legacy `failure_probability` name and ontology alias
remain for compatibility. See the [ICE scoring policy](ice-scoring-policy.md).
The serializer is not a physical-units validator or a replacement for telemetry
schema validation. ICE telemetry schemas and EV export behavior are unchanged.
