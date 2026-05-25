"""US-006 EV adapter read-only security tests."""

from __future__ import annotations

import pytest

from autopulse.data.validator import CommandBlockedException, UDSCommandGuard
from tests.simulation.virtual_replay import EVMockAdapter, JSONLProvider, SecurityViolationError


def ev_row(**overrides):
    row = {
        "timestamp": "2026-05-24T12:00:00.000Z",
        "vin_hashed": "e" * 64,
        "protocol": "SAE_J1979-3",
        "battery_soh": 95.0,
        "battery_soce": 80.0,
        "battery_temp_avg": 35.0,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "case_id,service_id,sub_function,expected_code",
    [
        ("SEC-001", "0x2E", None, "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-002", "0x31", "0x01", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-003", "0x31", "0x02", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-004", "0x2F", None, "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-005", "0x10", "0x02", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-006", "0x10", "0x03", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-008", "0x14", None, "SECURITY_VIOLATION_HIGH"),
        ("SEC-009", "0x27", "0x01", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-010", "0x27", "0x02", "SECURITY_VIOLATION_RED_LINE"),
    ],
    ids=lambda item: item if isinstance(item, str) and item.startswith("SEC-") else None,
)
def test_forbidden_services_blocked(case_id, service_id, sub_function, expected_code):
    guard = UDSCommandGuard()
    with pytest.raises(CommandBlockedException) as exc:
        guard.validate(service_id, sub_function)
    assert exc.value.code == expected_code


def test_sec_007_default_session_permitted():
    UDSCommandGuard().validate("0x10", "0x01")


def test_sec_011_tester_present_rate_limited():
    guard = UDSCommandGuard()
    guard.validate("0x3E", now=10.0)
    with pytest.raises(CommandBlockedException) as exc:
        guard.validate("0x3E", now=12.0)
    assert exc.value.code == "TESTER_PRESENT_RATE_LIMIT"


def test_sec_012_tester_present_blocked_outside_default_session():
    guard = UDSCommandGuard()
    guard.current_session = 0x03
    with pytest.raises(CommandBlockedException) as exc:
        guard.validate("0x3E", now=10.0)
    assert exc.value.code == "SECURITY_VIOLATION_RED_LINE"


def test_sec_013_read_data_by_identifier_permitted():
    UDSCommandGuard().validate("0x22")


def test_sec_014_read_dtc_status_mask_permitted():
    UDSCommandGuard().validate("0x19", "0x02")


def test_sec_015_unapproved_dtc_subfunction_rejected():
    with pytest.raises(CommandBlockedException) as exc:
        UDSCommandGuard().validate("0x19", "0x04")
    assert exc.value.code == "SECURITY_VIOLATION_HIGH"


def test_sec_016_spoofed_ice_identity_with_ev_service_rejected():
    adapter = EVMockAdapter(
        JSONLProvider([ev_row(powertrain_type="ICE", __service_id__="0x22")])
    )
    adapter.connect()
    with pytest.raises(Exception):
        adapter.fetch_frame()
    adapter.disconnect()


def test_sec_017_docan_to_doip_transition_aborts():
    adapter = EVMockAdapter(
        JSONLProvider(
            [
                ev_row(protocol="ISO_15765_4_DoCAN"),
                ev_row(protocol="ISO_13400_DoIP"),
            ]
        )
    )
    adapter.connect()
    adapter.fetch_frame()
    with pytest.raises(SecurityViolationError, match="PROTOCOL_TRANSITION_BLOCKED"):
        adapter.fetch_frame()
    adapter.disconnect()


def test_sec_018_negative_motor_speed_without_sign_convention_rejected():
    adapter = EVMockAdapter(
        JSONLProvider([ev_row(traction_motor_speed=-5000)]),
        sign_convention_documented=False,
    )
    adapter.connect()
    with pytest.raises(SecurityViolationError, match="SIGN_CONVENTION_UNDOCUMENTED"):
        adapter.fetch_frame()
    adapter.disconnect()


def test_sec_019_speculative_dtc_extended_data_probe_rejected():
    guard = UDSCommandGuard()
    with pytest.raises(CommandBlockedException) as exc:
        guard.validate("0x19", "0x06", dtc="P0A80")
    assert exc.value.code == "SPECULATIVE_DTC_PROBE"
    assert "SPECULATIVE_DTC_PROBE" in guard.events


def test_sec_019_observed_dtc_extended_data_permitted():
    guard = UDSCommandGuard()
    guard.observe_dtcs(["P0A80"])
    guard.validate("0x19", "0x06", dtc="P0A80")
