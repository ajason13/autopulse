"""Fake live-adapter helpers for smoke harness tests."""

from __future__ import annotations


FAKE_VIN_HASHED = "a" * 64
RAW_VIN = "1HGCM82633A004352"


def frame_values(**overrides):
    values = {
        "engine_load": 22.0,
        "coolant_temp": 88.0,
        "stft_bank1": 0.5,
        "ltft_bank1": -0.5,
        "engine_rpm": 1200.0,
        "vehicle_speed": 0,
    }
    values.update(overrides)
    return values


class FakeICEAdapter:
    def __init__(
        self,
        frames,
        *,
        protocol="SAE_J1979",
        connect_error=None,
        fetch_error=None,
        disconnect_error=None,
    ):
        self.frames = list(frames)
        self.protocol = protocol
        self.connect_error = connect_error
        self.fetch_error = fetch_error
        self.disconnect_error = disconnect_error
        self.connected = False
        self.disconnected = False
        self.query_count = 0
        self.queries = []

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    def disconnect(self):
        self.disconnected = True
        self.connected = False
        if self.disconnect_error is not None:
            raise self.disconnect_error

    def get_protocol_name(self):
        return self.protocol

    def query_pid(self, pid):
        self.queries.append(pid)
        if self.fetch_error is not None:
            raise self.fetch_error
        frame_index = self.query_count // 6
        self.query_count += 1
        frame = self.frames[frame_index]
        return {
            0x04: frame["engine_load"],
            0x05: frame["coolant_temp"],
            0x06: frame["stft_bank1"],
            0x07: frame["ltft_bank1"],
            0x0C: frame["engine_rpm"],
            0x0D: frame["vehicle_speed"],
        }[pid]
