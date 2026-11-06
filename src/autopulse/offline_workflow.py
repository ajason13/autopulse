"""Small offline ICE workflow over strictly validated canonical JSONL rows."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from jsonschema import ValidationError

from autopulse.alert_exporter import serialize_alert
from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.data.validator import validate_frame
from autopulse.debugging import get_logger, log_event
from autopulse.virtual_replay import JSONLProvider, MockAdapter


LOGGER = get_logger(__name__)


def analyze_ice_jsonl(lines: Iterable[str]) -> dict[str, Any]:
    """Replay local canonical ICE rows, partition analysis, and export observations.

    Blank lines are ignored. Every other line is accepted once or rejected once.
    Rejections expose only the physical line number and a fixed stage code.
    Observations retain input order within each vehicle's first-seen partition.
    This in-memory workflow is intended for small supplied offline fixtures.
    """
    processors: dict[str, PdMProcessor] = {}
    vehicles: dict[str, dict[str, Any]] = {}
    rejections: list[dict[str, Any]] = []
    total_rows = 0
    accepted_frames = 0

    for row_index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        total_rows += 1
        stage = "input"
        try:
            row = json.loads(line)
            # Validate before defaults, coercion, property stripping, or state.
            validate_frame(row)
            stage = "replay"
            adapter = MockAdapter(JSONLProvider([row]))
            adapter.connect()
            try:
                frame = adapter.fetch_frame().to_schema_dict()
            finally:
                adapter.disconnect()
            validate_frame(frame)
            identity = frame["vin_hashed"]
            stage = "analysis"
            if identity not in processors:
                processors[identity] = PdMProcessor(vin_hashed=identity)
            alert = processors[identity].process_frame(frame)
            if alert.failure_type == "SENSOR_ERROR":
                raise ValueError("sensor rejection")
        except (ValidationError, ValueError, TypeError, OverflowError, RecursionError):
            rejections.append({"row_index": row_index, "stage": stage})
            log_event(LOGGER, logging.WARNING, "offline_row_rejected",
                      row_index=row_index, stage=stage)
            continue

        # Export failures are fatal, rather than counted as input rejections.
        observation = serialize_alert(alert)
        if identity not in vehicles:
            vehicles[identity] = {"vin_hashed": identity, "observations": []}
        vehicles[identity]["observations"].append(observation)
        accepted_frames += 1

    report = {
        "ok": True,
        "powertrain_type": "ICE",
        "total_rows": total_rows,
        "accepted_frames": accepted_frames,
        "rejected_frames": len(rejections),
        "rejections": rejections,
        "vehicles": list(vehicles.values()),
    }
    log_event(LOGGER, logging.DEBUG, "offline_analysis_completed",
              total_rows=total_rows, accepted_frames=accepted_frames,
              rejected_frames=len(rejections), vehicles=len(vehicles))
    return report
