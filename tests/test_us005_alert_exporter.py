"""
AutoPulse US-005 — Adversarial Test Suite
Alerting Engine & JSON-LD Integration

Role: Lead Auditor
Target: autopulse.alert_exporter.serialize_alert()

This suite assumes the following contract from the Lead Developer (Codex):

    from autopulse.alert_exporter import PdMAlert, serialize_alert

    - PdMAlert is a dataclass or class with fields:
        vin_hashed: str
        failure_probability: float
        failure_type: str           # "HDF" or "OSF" only
        window_summary: dict | None

    - serialize_alert(alert) -> dict
        Returns a JSON-LD-compatible Python dict.
        Raises ValueError on any constraint violation.
        The returned dict must be json.dumps()-serializable (no NaN, no Infinity).

All tests in this file are adversarial: they probe the boundaries that the architect's
spec defines. Failures here are P0 defects, not suggestions.
"""

import json
import math
import re
import pytest

# ---------------------------------------------------------------------------
# Import guard — if the module doesn't exist, all tests will fail explicitly.
# ---------------------------------------------------------------------------
try:
    from autopulse.alert_exporter import PdMAlert, serialize_alert
except ImportError as exc:
    pytest.fail(
        f"FATAL: Cannot import autopulse.alert_exporter. "
        f"Lead Developer has not shipped the module. Error: {exc}"
    )

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

VALID_VIN_HASH = "a" * 64          # 64 lowercase hex chars — valid SHA-256 placeholder
VALID_PROB = 0.85
VALID_FAILURE_TYPE_HDF = "HDF"
VALID_FAILURE_TYPE_OSF = "OSF"

VALID_WINDOW_SUMMARY = {
    "primary_pid": "Vehicle.Powertrain.CombustionEngine.Speed",
    "current_value": 4500.0,
    "unit": "rpm",
    "z_score": 3.85,
    "iqr_bounds": {"lower": 650.0, "upper": 3200.0},
    "window_size_seconds": 60,
    "sample_count": 120,
}

REQUIRED_CONTEXT_NAMESPACES = {
    "autopulse": "https://autopulse.io/schema/",
    "sosa": "http://www.w3.org/ns/sosa/",
    "schema": "https://schema.org/",
    "vss": "https://vss.covesa.org/",
}

REQUIRED_FIELD_MAPPINGS = {
    "vin_hashed": "sosa:hasFeatureOfInterest",
    "failure_probability": "schema:probability",
    "failure_type": "autopulse:failureMode",
    "window_summary": "sosa:hasResult",
}


def make_valid_alert(**overrides) -> PdMAlert:
    """Convenience factory for a known-good PdMAlert."""
    kwargs = dict(
        vin_hashed=VALID_VIN_HASH,
        failure_probability=VALID_PROB,
        failure_type=VALID_FAILURE_TYPE_HDF,
        window_summary=VALID_WINDOW_SUMMARY.copy(),
    )
    kwargs.update(overrides)
    return PdMAlert(**kwargs)


# ===========================================================================
# Section 1: JSON-LD Structural Validity
# ===========================================================================

class TestJsonLdSyntax:
    """Verify that every output is a syntactically valid JSON-LD document."""

    def test_output_is_dict(self):
        """serialize_alert must return a Python dict, not a string."""
        result = serialize_alert(make_valid_alert())
        assert isinstance(result, dict), (
            "serialize_alert must return a dict, not a raw JSON string."
        )

    def test_output_is_json_serializable(self):
        """The returned dict must survive json.dumps without errors."""
        result = serialize_alert(make_valid_alert())
        try:
            json.dumps(result)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Output is not JSON-serializable: {exc}")

    def test_context_key_present(self):
        """@context must be present at the root level."""
        result = serialize_alert(make_valid_alert())
        assert "@context" in result, "Missing mandatory '@context' key in JSON-LD output."

    def test_type_key_present(self):
        """@type must be present at the root level."""
        result = serialize_alert(make_valid_alert())
        assert "@type" in result, "Missing mandatory '@type' key in JSON-LD output."

    def test_type_is_sosa_observation(self):
        """@type must equal 'sosa:Observation' per US-005 spec."""
        result = serialize_alert(make_valid_alert())
        assert result["@type"] == "sosa:Observation", (
            f"Expected @type 'sosa:Observation', got '{result.get('@type')}'. "
            "Semantic type breach — downstream reasoners will misclassify this alert."
        )

    def test_id_key_present(self):
        """@id (UUID) should be present for graph addressability."""
        result = serialize_alert(make_valid_alert())
        assert "@id" in result, (
            "Missing '@id' key. JSON-LD nodes without an @id cannot be addressed "
            "in a knowledge graph."
        )

    def test_no_nan_values_in_output(self):
        """The serialized JSON string must contain no NaN tokens (invalid per RFC 8259)."""
        result = serialize_alert(make_valid_alert())
        serialized = json.dumps(result)
        assert "NaN" not in serialized and "nan" not in serialized, (
            "Output JSON contains 'NaN', which is illegal per RFC 8259 and will break "
            "any JSON parser."
        )

    def test_no_infinity_values_in_output(self):
        """The serialized JSON string must contain no Infinity tokens."""
        result = serialize_alert(make_valid_alert())
        serialized = json.dumps(result)
        assert "Infinity" not in serialized and "infinity" not in serialized, (
            "Output JSON contains 'Infinity', which is illegal per RFC 8259."
        )


# ===========================================================================
# Section 2: @context Ontology Mapping Verification
# ===========================================================================

class TestOntologyMapping:
    """Verify that @context maps every field to the correct IRI per spec."""

    def test_all_required_namespaces_present(self):
        """The @context must declare all four required namespace prefixes."""
        result = serialize_alert(make_valid_alert())
        ctx = result["@context"]
        for prefix, expected_iri in REQUIRED_CONTEXT_NAMESPACES.items():
            assert prefix in ctx, (
                f"Namespace prefix '{prefix}' missing from @context. "
                f"Expected IRI: {expected_iri}"
            )

    @pytest.mark.parametrize("prefix,expected_iri", REQUIRED_CONTEXT_NAMESPACES.items())
    def test_namespace_iri_correctness(self, prefix, expected_iri):
        """Each namespace IRI must exactly match the spec."""
        result = serialize_alert(make_valid_alert())
        ctx = result["@context"]
        actual_iri = ctx.get(prefix)
        assert actual_iri == expected_iri, (
            f"Namespace '{prefix}' IRI mismatch.\n"
            f"  Expected: {expected_iri}\n"
            f"  Got:      {actual_iri}\n"
            "IRI drift silently breaks semantic interoperability."
        )

    @pytest.mark.parametrize("field,expected_mapping", REQUIRED_FIELD_MAPPINGS.items())
    def test_field_semantic_mapping(self, field, expected_mapping):
        """Every field must map to its specified ontology IRI alias in @context."""
        result = serialize_alert(make_valid_alert())
        ctx = result["@context"]
        actual_mapping = ctx.get(field)
        assert actual_mapping == expected_mapping, (
            f"Field '{field}' has wrong @context mapping.\n"
            f"  Expected: {expected_mapping}\n"
            f"  Got:      {actual_mapping}\n"
            "This is a semantic contract breach — the field will not be understood "
            "by SOSA/Schema.org reasoners."
        )

    def test_all_iri_values_are_strings(self):
        """All @context values must be strings (IRIs or compact IRI aliases)."""
        result = serialize_alert(make_valid_alert())
        ctx = result["@context"]
        for key, value in ctx.items():
            assert isinstance(value, str), (
                f"@context key '{key}' has a non-string value: {type(value).__name__}. "
                "JSON-LD @context values must be strings or objects."
            )

    def test_iri_values_are_valid_uris(self):
        """Namespace IRIs must start with http:// or https://."""
        result = serialize_alert(make_valid_alert())
        ctx = result["@context"]
        for prefix, iri in REQUIRED_CONTEXT_NAMESPACES.items():
            actual = ctx.get(prefix, "")
            assert actual.startswith("http://") or actual.startswith("https://"), (
                f"Namespace '{prefix}' IRI is not a valid absolute URI: '{actual}'"
            )


# ===========================================================================
# Section 3: Security Red Lines
# ===========================================================================

class TestSecurityRedLines:
    """
    CRITICAL — Zero Tolerance.
    Any failure here is an automatic P0 release blocker.
    """

    # --- RED LINE 1: No Raw VINs ---

    RAW_VIN_PATTERN = re.compile(r"[A-HJ-NPR-Z0-9]{17}")
    VALID_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")

    def test_valid_hash_accepted(self):
        """A valid 64-char lowercase hex hash must be accepted without error."""
        alert = make_valid_alert(vin_hashed="b" * 64)
        result = serialize_alert(alert)
        assert result.get("vin_hashed") == "b" * 64

    def test_raw_vin_17_chars_rejected(self):
        """A raw 17-character VIN must never appear in the serialized output."""
        raw_vin = "1HGCM82633A004352"   # Valid real-format VIN
        with pytest.raises((ValueError, TypeError), match=re.compile(r"vin|hash|invalid", re.I)):
            serialize_alert(make_valid_alert(vin_hashed=raw_vin))

    def test_raw_vin_does_not_leak_to_output(self):
        """Even if the serializer doesn't raise, the raw VIN must not appear in output."""
        raw_vin = "1HGCM82633A004352"
        try:
            result = serialize_alert(make_valid_alert(vin_hashed=raw_vin))
            serialized = json.dumps(result)
            assert raw_vin not in serialized, (
                "CRITICAL: Raw VIN found in serialized output. "
                "This is a PII/regulatory breach (GDPR, CCPA)."
            )
        except (ValueError, TypeError):
            pass  # Raising is the correct behavior

    def test_63_char_hash_rejected(self):
        """A hash that is 1 char too short must be rejected."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(vin_hashed="a" * 63))

    def test_65_char_hash_rejected(self):
        """A hash that is 1 char too long must be rejected."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(vin_hashed="a" * 65))

    def test_uppercase_hex_hash_rejected(self):
        """SHA-256 convention requires lowercase hex; uppercase must be rejected."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(vin_hashed="A" * 64))

    def test_non_hex_characters_in_hash_rejected(self):
        """Hash containing non-hex characters (g-z) must be rejected."""
        bad_hash = "g" + "a" * 63   # 'g' is not valid hex
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(vin_hashed=bad_hash))

    def test_empty_vin_hash_rejected(self):
        """An empty vin_hashed string must be rejected."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(vin_hashed=""))

    # --- RED LINE 2: No Restricted OBD-II Fields ---

    @pytest.mark.parametrize("restricted_key", [
        "mode_0x08", "service_0x31", "service_0x2E", "service_0x14", "service_0x10",
        "routine_control", "write_data_by_identifier", "clear_dtc",
    ])
    def test_restricted_obd_fields_not_in_output(self, restricted_key):
        """Restricted OBD-II service keys must never appear in the serialized output."""
        alert = make_valid_alert(
            window_summary={**VALID_WINDOW_SUMMARY, restricted_key: "injected_value"}
        )
        result = serialize_alert(alert)
        serialized = json.dumps(result)
        assert restricted_key not in serialized, (
            f"CRITICAL: Restricted field '{restricted_key}' found in output. "
            "This violates the Read-Only Red Line from US-001."
        )

    # --- RED LINE 5: @context Injection Prevention ---

    def test_context_injection_via_window_summary_ignored(self):
        """
        A crafted @context key inside window_summary must not override the root @context.
        This simulates a context hijacking attack.
        """
        malicious_summary = {
            **VALID_WINDOW_SUMMARY,
            "@context": {
                "vin_hashed": "http://evil.io/steal#vin"
            }
        }
        alert = make_valid_alert(window_summary=malicious_summary)
        result = serialize_alert(alert)
        # The root @context mapping must remain unaffected
        ctx = result.get("@context", {})
        actual_mapping = ctx.get("vin_hashed")
        assert actual_mapping == "sosa:hasFeatureOfInterest", (
            "CRITICAL: @context injection succeeded. An attacker passed a crafted @context "
            "in window_summary and overrode the root ontology mapping. "
            "The serializer must enforce a static, immutable @context."
        )


# ===========================================================================
# Section 4: Failure Mode Coherence (US-003 Schema Coherence)
# ===========================================================================

class TestFailureModeCoherence:
    """Verify that failure_type is correctly typed and constrained per US-003."""

    def test_hdf_accepted(self):
        """'HDF' is a valid US-003 failure type and must serialize without error."""
        result = serialize_alert(make_valid_alert(failure_type="HDF"))
        assert result["failure_type"] == "HDF"

    def test_osf_accepted(self):
        """'OSF' is a valid US-003 failure type and must serialize without error."""
        result = serialize_alert(make_valid_alert(failure_type="OSF"))
        assert result["failure_type"] == "OSF"

    @pytest.mark.parametrize("invalid_type", [
        "SENSOR_ERROR",      # Operationally different — must not be aliased to OSF
        "UNKNOWN",
        "ERROR",
        "hdf",               # Case sensitivity check
        "osf",
        "HDF ",              # Trailing whitespace
        " OSF",              # Leading whitespace
        "1",
        "",
        None,
    ])
    def test_invalid_failure_type_rejected(self, invalid_type):
        """
        Any failure_type that is not exactly 'HDF' or 'OSF' must be rejected.
        SENSOR_ERROR is explicitly NOT an alias for OSF — treating it as one
        corrupts the semantic type graph and the ML training labels.
        """
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(failure_type=invalid_type))

    def test_failure_type_appears_in_output(self):
        """failure_type must be present in the serialized output."""
        result = serialize_alert(make_valid_alert(failure_type="OSF"))
        assert "failure_type" in result, "failure_type missing from serialized output."

    def test_sensor_error_not_coerced_to_osf(self):
        """
        'SENSOR_ERROR' must never be silently coerced to 'OSF'.
        This conflation would corrupt downstream ML training data.
        """
        try:
            result = serialize_alert(make_valid_alert(failure_type="SENSOR_ERROR"))
            # If no exception raised, the value must NOT be silently coerced
            assert result.get("failure_type") != "OSF", (
                "CRITICAL: 'SENSOR_ERROR' was silently coerced to 'OSF'. "
                "This corrupts the semantic meaning defined in US-003."
            )
            assert result.get("failure_type") != "HDF", (
                "CRITICAL: 'SENSOR_ERROR' was silently coerced to 'HDF'."
            )
        except (ValueError, TypeError):
            pass  # Raising is the correct behavior


# ===========================================================================
# Section 5: Numeric Edge Cases (NaN / Infinity / Bounds)
# ===========================================================================

class TestNumericEdgeCases:
    """
    Numeric guard tests. NaN and Infinity are illegal JSON values per RFC 8259
    and will corrupt every downstream system that consumes this data.
    """

    # --- failure_probability ---

    @pytest.mark.parametrize("prob", [0.0, 0.001, 0.5, 0.999, 1.0])
    def test_valid_probability_accepted(self, prob):
        """Probabilities in [0.0, 1.0] must be accepted."""
        result = serialize_alert(make_valid_alert(failure_probability=prob))
        assert result["failure_probability"] == prob

    @pytest.mark.parametrize("prob", [-0.001, -1.0, 1.001, 1.5, 100.0, -100.0])
    def test_out_of_range_probability_rejected(self, prob):
        """Probabilities outside [0.0, 1.0] must be rejected."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(failure_probability=prob))

    def test_nan_probability_rejected(self):
        """NaN failure_probability must raise — cannot be serialized to JSON."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(failure_probability=math.nan))

    def test_positive_inf_probability_rejected(self):
        """Positive infinity failure_probability must raise."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(failure_probability=math.inf))

    def test_negative_inf_probability_rejected(self):
        """Negative infinity failure_probability must raise."""
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(failure_probability=-math.inf))

    # --- z_score in window_summary ---

    def test_nan_z_score_in_window_summary_rejected(self):
        """
        NaN z_score inside window_summary must cause serialization to fail.
        Silently passing NaN to downstream ML models corrupts anomaly detection.
        """
        bad_summary = {**VALID_WINDOW_SUMMARY, "z_score": math.nan}
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(window_summary=bad_summary))

    def test_positive_inf_z_score_rejected(self):
        """Positive infinity z_score must raise."""
        bad_summary = {**VALID_WINDOW_SUMMARY, "z_score": math.inf}
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(window_summary=bad_summary))

    def test_negative_inf_z_score_rejected(self):
        """Negative infinity z_score must raise."""
        bad_summary = {**VALID_WINDOW_SUMMARY, "z_score": -math.inf}
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(window_summary=bad_summary))

    def test_valid_negative_z_score_accepted(self):
        """A valid negative z_score (e.g., -3.85) represents a low-side anomaly and is legal."""
        summary = {**VALID_WINDOW_SUMMARY, "z_score": -3.85}
        result = serialize_alert(make_valid_alert(window_summary=summary))
        assert result is not None

    def test_z_score_zero_accepted(self):
        """z_score of 0 is valid (value exactly at mean) and must be accepted."""
        summary = {**VALID_WINDOW_SUMMARY, "z_score": 0.0}
        result = serialize_alert(make_valid_alert(window_summary=summary))
        assert result is not None

    # --- NaN check survives JSON round-trip ---

    def test_no_nan_survives_json_roundtrip(self):
        """After json.dumps + json.loads, no numeric field should be NaN or Infinity."""
        result = serialize_alert(make_valid_alert())
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        # Recursively check all numeric values
        def find_non_finite(obj, path=""):
            if isinstance(obj, float):
                assert math.isfinite(obj), (
                    f"Non-finite float found at '{path}': {obj}"
                )
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    find_non_finite(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    find_non_finite(v, f"{path}[{i}]")
        find_non_finite(parsed)


# ===========================================================================
# Section 6: window_summary Edge Cases
# ===========================================================================

class TestWindowSummaryEdgeCases:
    """Test robustness of window_summary handling — missing PIDs, zero samples, etc."""

    def test_none_window_summary_behavior_is_defined(self):
        """
        window_summary=None must have defined behavior: either raise or produce
        a null value in the output. Undefined behavior (no key at all) is a defect.
        """
        alert = make_valid_alert(window_summary=None)
        try:
            result = serialize_alert(alert)
            # If no exception, the key must be explicitly present (even if null)
            assert "window_summary" in result, (
                "window_summary=None caused the field to be silently omitted. "
                "JSON-LD consumers cannot distinguish 'no data' from 'not serialized'."
            )
        except (ValueError, TypeError):
            pass  # Explicit rejection is also acceptable

    def test_zero_sample_count_does_not_crash(self):
        """
        sample_count=0 should not cause a division-by-zero crash.
        The behavior (accept or reject) must be explicit and not a runtime exception.
        """
        summary = {**VALID_WINDOW_SUMMARY, "sample_count": 0}
        try:
            serialize_alert(make_valid_alert(window_summary=summary))
        except (ValueError, TypeError):
            pass  # Intentional rejection is fine
        except ZeroDivisionError:
            pytest.fail(
                "serialize_alert crashed with ZeroDivisionError on sample_count=0. "
                "All division operations must guard against zero denominators."
            )

    def test_inverted_iqr_bounds_rejected(self):
        """
        iqr_bounds where lower > upper is a physically impossible statistical result.
        This indicates data corruption and must be rejected.
        """
        summary = {**VALID_WINDOW_SUMMARY, "iqr_bounds": {"lower": 3200.0, "upper": 650.0}}
        with pytest.raises((ValueError, TypeError)):
            serialize_alert(make_valid_alert(window_summary=summary))

    def test_equal_iqr_bounds_behavior_is_defined(self):
        """
        iqr_bounds where lower == upper (zero IQR) implies a degenerate distribution.
        This is statistically suspicious but not impossible (constant signal).
        The serializer must handle it without crashing.
        """
        summary = {**VALID_WINDOW_SUMMARY, "iqr_bounds": {"lower": 1000.0, "upper": 1000.0}}
        try:
            serialize_alert(make_valid_alert(window_summary=summary))
        except (ValueError, TypeError):
            pass  # Rejection is acceptable
        except Exception as exc:
            pytest.fail(f"Unexpected exception on equal IQR bounds: {type(exc).__name__}: {exc}")

    def test_missing_primary_pid_behavior_is_defined(self):
        """
        A window_summary without primary_pid cannot be linked to a VSS signal path.
        The behavior must be explicitly defined (raise or fill with null).
        """
        summary = {k: v for k, v in VALID_WINDOW_SUMMARY.items() if k != "primary_pid"}
        alert = make_valid_alert(window_summary=summary)
        try:
            result = serialize_alert(alert)
            # If accepted, primary_pid should be absent or null — not fabricated
            ws = result.get("window_summary", {})
            assert ws.get("primary_pid") is None or "primary_pid" not in ws, (
                "A missing primary_pid was fabricated in the output. "
                "The serializer must not invent data that was not provided."
            )
        except (ValueError, TypeError):
            pass  # Explicit rejection is also correct

    def test_negative_current_value_for_rpm_is_flagged(self):
        """
        A negative current_value for an RPM signal is physically impossible.
        If the serializer is aware of units, it must reject this.
        If not unit-aware, this is a known gap that must be documented.
        """
        summary = {**VALID_WINDOW_SUMMARY, "current_value": -500.0, "unit": "rpm"}
        # This test documents the gap — the serializer may or may not enforce physics
        # but it must not crash
        try:
            serialize_alert(make_valid_alert(window_summary=summary))
        except (ValueError, TypeError):
            pass  # Enforcement is ideal
        except Exception as exc:
            pytest.fail(
                f"Unexpected crash on negative RPM: {type(exc).__name__}: {exc}. "
                "If the serializer is not physics-aware, document this as a known gap."
            )

    def test_window_summary_present_in_output(self):
        """When a valid window_summary is provided, it must appear in the output."""
        result = serialize_alert(make_valid_alert())
        assert "window_summary" in result, (
            "window_summary was provided but is missing from the serialized output."
        )

    def test_window_summary_is_dict_in_output(self):
        """window_summary in the output must be a dict, not a string or list."""
        result = serialize_alert(make_valid_alert())
        ws = result.get("window_summary")
        assert isinstance(ws, dict), (
            f"window_summary in output is {type(ws).__name__}, expected dict."
        )


# ===========================================================================
# Section 7: Integration Smoke Test
# ===========================================================================

class TestIntegrationSmoke:
    """End-to-end validation of a known-good payload against all invariants at once."""

    def test_full_hdf_alert_is_valid_jsonld(self):
        """A complete, valid HDF alert must produce a schema-compliant JSON-LD document."""
        alert = make_valid_alert(
            failure_type="HDF",
            failure_probability=0.91,
            window_summary={**VALID_WINDOW_SUMMARY, "z_score": 4.2},
        )
        result = serialize_alert(alert)
        serialized = json.dumps(result)          # Must not raise
        parsed = json.loads(serialized)          # Must not raise

        assert parsed.get("@type") == "sosa:Observation"
        assert "@context" in parsed
        assert parsed["@context"].get("vin_hashed") == "sosa:hasFeatureOfInterest"
        assert parsed["failure_type"] == "HDF"
        assert parsed["failure_probability"] == 0.91
        assert re.match(r"^[a-f0-9]{64}$", parsed["vin_hashed"])

    def test_full_osf_alert_is_valid_jsonld(self):
        """A complete, valid OSF alert must produce a schema-compliant JSON-LD document."""
        alert = make_valid_alert(
            failure_type="OSF",
            failure_probability=0.92,
        )
        result = serialize_alert(alert)
        serialized = json.dumps(result)
        parsed = json.loads(serialized)

        assert parsed.get("@type") == "sosa:Observation"
        assert parsed["failure_type"] == "OSF"

    def test_serializer_is_deterministic(self):
        """
        Two calls with identical inputs must produce identical @context mappings.
        Non-determinism in @context would break semantic interoperability.
        """
        alert = make_valid_alert()
        result_a = serialize_alert(alert)
        result_b = serialize_alert(alert)
        assert result_a["@context"] == result_b["@context"], (
            "serialize_alert is non-deterministic: two identical inputs produced "
            "different @context blocks. This will break downstream semantic reasoners."
        )
