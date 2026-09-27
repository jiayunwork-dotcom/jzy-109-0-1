"""Tests for pre-computation input validation: illegal input is blocked with
an explicit reason before any solver can hit a division by zero."""
from __future__ import annotations

import math

import pytest

from app import validation
from app.validation import BridgeValidationError


@pytest.mark.parametrize("bad", [0.0, -1.0, -1e-9])
def test_non_positive_resistance_rejected_with_reason(bad):
    with pytest.raises(BridgeValidationError) as exc:
        validation.validate_resistance("r1", bad)
    assert "strictly positive" in str(exc.value)
    assert "r1" in str(exc.value)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_resistance_rejected(bad):
    with pytest.raises(BridgeValidationError):
        validation.validate_resistance("r2", bad)


@pytest.mark.parametrize("bad", ["100", None, [100.0], True])
def test_non_numeric_resistance_rejected(bad):
    with pytest.raises(BridgeValidationError):
        validation.validate_resistance("r3", bad)


def test_missing_arm_named_explicitly():
    with pytest.raises(BridgeValidationError) as exc:
        validation.validate_arms({"r1": 1.0, "r2": 1.0, "r3": 1.0})
    message = str(exc.value)
    assert "missing" in message
    assert "r4" in message


def test_unknown_arm_name_rejected():
    payload = {"r1": 1.0, "r2": 1.0, "r3": 1.0, "r4": 1.0, "rx": 2.0}
    with pytest.raises(BridgeValidationError) as exc:
        validation.validate_arms(payload)
    assert "rx" in str(exc.value)


def test_zero_source_voltage_is_valid():
    # Zero Vs must NOT raise: the caller returns a flagged zero output.
    assert validation.validate_source_voltage(0.0) == 0.0


def test_non_finite_source_voltage_rejected():
    with pytest.raises(BridgeValidationError):
        validation.validate_source_voltage(float("inf"))


def test_solve_rejects_four_known_arms_as_self_inconsistent():
    with pytest.raises(BridgeValidationError) as exc:
        validation.validate_known_arms(
            {"r1": 1.0, "r2": 1.0, "r3": 1.0, "r4": 1.0}
        )
    assert "self-inconsistent" in str(exc.value)


def test_solve_rejects_fewer_than_three_known_arms():
    with pytest.raises(BridgeValidationError) as exc:
        validation.validate_known_arms({"r1": 1.0, "r2": 1.0})
    assert "exactly three" in str(exc.value)


def test_solve_rejects_unknown_name():
    with pytest.raises(BridgeValidationError):
        validation.validate_known_arms(
            {"r1": 1.0, "r2": 1.0, "rx": 3.0}
        )


def test_solve_rejects_zero_known_resistance_before_division():
    # The opposite arm divides; a zero known arm must be rejected up front,
    # never surface as a ZeroDivisionError mid-solve.
    with pytest.raises(BridgeValidationError) as exc:
        validation.validate_known_arms(
            {"r1": 1.0, "r2": 0.0, "r3": 1.0}
        )
    assert "strictly positive" in str(exc.value)


def test_validate_config_name():
    assert validation.validate_config_name(" lab-1 ") == "lab-1"
    for bad in ["", "   ", 5, None]:
        with pytest.raises(BridgeValidationError):
            validation.validate_config_name(bad)
