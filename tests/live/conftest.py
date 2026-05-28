"""Hardware-free fixtures for live smoke harness tests."""

from __future__ import annotations

import logging

import pytest

from tests.live.fakes import FAKE_VIN_HASHED


@pytest.fixture(autouse=True)
def restore_autopulse_logger():
    logger = logging.getLogger("autopulse")
    original_level = logger.level
    original_propagate = logger.propagate
    original_handlers = list(logger.handlers)
    try:
        yield
    finally:
        for handler in logger.handlers:
            if handler not in original_handlers:
                handler.close()
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate


@pytest.fixture
def fake_vin_hashed():
    return FAKE_VIN_HASHED
