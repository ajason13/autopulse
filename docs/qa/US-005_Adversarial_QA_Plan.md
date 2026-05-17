# AutoPulse US-005 — Adversarial QA Plan
**Role:** Lead Auditor
**Targets:** Alerting Engine & JSON-LD Integration (US-005)
**Spec Author:** Gemini (Lead Architect)
**Date:** 2025-10 (Phase 2 QA Planning)

---

## 1. Audit Mandate & Threat Model

The JSON-LD serializer is the **trust boundary** between raw sensor telemetry and downstream
consumers (fleet dashboards, insurance APIs, semantic knowledge graphs). A defect here is not
a rendering bug — it is a data-integrity or privacy breach. The audit posture is therefore
**adversarial by default**: we assume the serializer is broken until proven otherwise.

Threat surface:
| Vector | Risk |
|---|---|
| Raw VIN exposure | PII/regulatory breach (GDPR, CCPA) |
| Invalid ontology IRIs | Silent semantic mismatch — downstream reasoners draw wrong conclusions |
| NaN / Inf in numeric fields | ML pipeline corruption, silent schema pass |
| Unsupported failure_type values | Downstream type-checking failures, alert suppression |
| Missing required JSON-LD keys | Frames break; React components silently skip alerts |
| Writable fields leaking | Violates read-only contract from US-001 |

---

## 2. Validation Strategy

### 2.1 JSON-LD Syntax Verification
- Every output **must be valid JSON** (parseable by `json.loads`).
- The `@context` block must be present, contain all four required namespace prefixes
  (`autopulse`, `sosa`, `schema`, `vss`), and every mapped field must resolve to a valid IRI
  (string starting with `http://` or `https://`).
- The `@type` field must be present and equal `"sosa:Observation"`.

### 2.2 Semantic Mapping Verification
Four field mappings defined in the spec are contractual and must be tested exhaustively:

| Python Field | Expected JSON-LD Key | Expected Mapped IRI |
|---|---|---|
| `vin_hashed` | `"vin_hashed"` | `"sosa:hasFeatureOfInterest"` |
| `failure_probability` | `"failure_probability"` | `"schema:probability"` |
| `failure_type` | `"failure_type"` | `"autopulse:failureMode"` |
| `window_summary` | `"window_summary"` | `"sosa:hasResult"` |

Any drift between the field name and its `@context` mapping is a **semantic contract breach**.

### 2.3 Schema Coherence (US-003 Failure Modes)
- `failure_type` MUST be one of `{"HDF", "OSF"}` — these are the only two modes defined in US-003.
- `"SENSOR_ERROR"`, `"UNKNOWN"`, numeric codes, or `None` are **not valid failure types** and
  must be rejected at serialization time, not silently coerced.

---

## 3. Red Lines (Non-Negotiable Constraints for Codex)

These are absolute prohibitions. Any violation is a **P0 defect** that blocks release.

### RED LINE 1 — No Raw VINs
- The serialized payload **must never contain a raw VIN** (17-character alphanumeric string
  matching `[A-HJ-NPR-Z0-9]{17}`).
- The `vin_hashed` field must contain **exactly a 64-character lowercase hexadecimal string**
  matching `^[a-f0-9]{64}$`.
- If a raw VIN is passed as input, the serializer must raise an exception or sanitize — it must
  **never silently pass it through**.

### RED LINE 2 — No Writable/Control Fields
- The output payload must not contain any key that corresponds to a restricted OBD-II service
  (Mode 0x08, Service 0x31, Service 0x2E, Service 0x14, Service 0x10). These must be blocked
  even if they appear in `window_summary` or `additional_properties`.
- `additionalProperties` behavior: any field not in the defined schema must either be **dropped
  silently** or cause a **validation error** — never passed through.

### RED LINE 3 — NaN/Infinity Prohibition
- `failure_probability`, `z_score`, and any numeric field in `window_summary` must **never
  serialize to JSON `NaN` or `Infinity`** (which are not valid JSON values per RFC 8259).
- The serializer must detect `math.nan`, `math.inf`, and `-math.inf` and raise a
  `ValueError` before producing output.

### RED LINE 4 — failure_probability Bounds
- Must be in the closed interval `[0.0, 1.0]`. Values like `1.5`, `-0.1`, or `101` must be
  rejected.

### RED LINE 5 — @context Immutability
- The `@context` block must be **read-only at runtime**. No consumer input should be able to
  override, inject, or extend it. A context injection attack (passing a crafted `@context` in
  input data) must have no effect on the serialized output.

---

## 4. Edge Cases Under Test

### 4.1 Statistical Anomalies
- `z_score = NaN` → must raise, not silently serialize
- `z_score = Inf` → must raise
- `iqr_bounds` with `lower > upper` → must raise (inverted bounds are impossible)
- `iqr_bounds` missing entirely → behavior must be defined: either required or optional with
  documented default; ambiguity is a defect

### 4.2 Missing & Partial window_summary
- `window_summary` present but `sample_count = 0` → division-by-zero guard needed
- `window_summary` missing `primary_pid` → must raise if PID is required per spec
- `window_summary = None` → behavior must be explicit (null is not the same as absent)

### 4.3 SENSOR_ERROR Handling
- `failure_type = "SENSOR_ERROR"` → must be rejected as an invalid enum value; this is **not**
  an alias for OSF — conflating them corrupts the semantic type graph
- `failure_probability = 0.0` with `failure_type = "HDF"` — contradictory but valid? Must be
  explicitly decided and enforced

### 4.4 Boundary & Encoding
- `vin_hashed` with 63 chars → reject
- `vin_hashed` with 65 chars → reject
- `vin_hashed` with uppercase hex → reject (must be lowercase per SHA-256 convention)
- `failure_probability = 0.0` → must be accepted (low-confidence alert is valid)
- `failure_probability = 1.0` → must be accepted

### 4.5 @context Injection
- Pass a crafted input with a `@context` key attempting to remap `vin_hashed` to a
  non-privacy-preserving IRI → serializer must ignore and enforce its own static context

---

## 5. Test Suite Structure

```
tests/
└── test_us005_alert_exporter.py
    ├── TestJsonLdSyntax          — Structural validity of the output
    ├── TestOntologyMapping       — @context IRI correctness
    ├── TestSecurityRedLines      — VIN exposure, field injection, context hijack
    ├── TestFailureModeCoherence  — HDF/OSF typing, SENSOR_ERROR rejection
    ├── TestNumericEdgeCases      — NaN, Inf, bounds violations
    └── TestWindowSummaryEdgeCases — Missing PIDs, zero samples, inverted IQR
```

---

## 6. Assumed Module Contract (for Codex)

The test suite assumes the Lead Developer ships a module at:
```
autopulse/alert_exporter.py
```
exposing:
```python
class PdMAlert:
    vin_hashed: str
    failure_probability: float
    failure_type: str          # Must be "HDF" or "OSF"
    window_summary: dict | None

def serialize_alert(alert: PdMAlert) -> dict:
    """Returns a JSON-LD compatible Python dict. Raises ValueError on constraint violations."""
```

The tests import from this module. If the module does not exist or deviates from this interface,
**all tests will fail by design** — that is the correct adversarial outcome.

---

## 7. Pass/Fail Criteria

| Category | Required Pass Rate |
|---|---|
| JSON-LD Syntax | 100% — zero tolerance |
| Ontology Mapping | 100% — zero tolerance |
| Security Red Lines | 100% — zero tolerance |
| Failure Mode Coherence | 100% — zero tolerance |
| Numeric Edge Cases | 100% — zero tolerance |
| Window Summary Edge Cases | ≥ 90% (some behaviors TBD by spec) |

**Any failure in Security Red Lines or Ontology Mapping is an automatic release blocker.**
