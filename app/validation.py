"""Input validation, performed before any physics is computed.

Every rejection raises :class:`BridgeValidationError` carrying an explicit
human-readable ``reason``; the HTTP layer maps that to a 400 response.
Nothing here ever lets a stray ZeroDivisionError escape from a solver.

Rules:

* every bridge arm resistance must be a finite positive number;
* forward output needs all four arms;
* the balance solve needs EXACTLY three known arms -- four means there is
  nothing left to solve and the request is self-inconsistent, fewer than
  three is underdetermined;
* source voltage must be finite; zero is allowed and is NOT an error -- the
  service short-circuits to a zero output and flags it in the response;
* galvanometer internal resistance, when given, must be finite and positive.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .balance import ARMS


class BridgeValidationError(ValueError):
    """Raised for any input rejected before the computation runs."""


def _finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BridgeValidationError(
            f"{name} must be a real number, got {value!r}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise BridgeValidationError(
            f"{name} must be finite (no NaN/inf), got {value!r}"
        )
    return number


def validate_resistance(name: str, value: Any) -> float:
    """Validate one resistance: finite and strictly positive."""
    number = _finite_number(name, value)
    if number <= 0.0:
        raise BridgeValidationError(
            f"{name} must be strictly positive (ohms > 0), got {value!r}"
        )
    return number


def validate_arms(arms: Mapping[str, Any]) -> dict[str, float]:
    """Validate a complete set of four arms for the forward calculation."""
    missing = [arm for arm in ARMS if arm not in arms]
    if missing:
        raise BridgeValidationError(
            "missing bridge arm(s): " + ", ".join(missing)
            + "; all four arms r1, r2, r3, r4 are required"
        )
    extra = sorted(key for key in arms if key not in ARMS)
    if extra:
        raise BridgeValidationError(
            "unknown bridge arm name(s): " + ", ".join(extra)
            + "; valid names are r1, r2, r3, r4"
        )
    return {arm: validate_resistance(arm, arms[arm]) for arm in ARMS}


def validate_known_arms(known: Mapping[str, Any]) -> dict[str, float]:
    """Validate the partial arm map used by the balance solve.

    Must hold exactly three of the four arm names.
    """
    extra = sorted(key for key in known if key not in ARMS)
    if extra:
        raise BridgeValidationError(
            "unknown bridge arm name(s): " + ", ".join(extra)
            + "; valid names are r1, r2, r3, r4"
        )
    present = [arm for arm in ARMS if arm in known]
    if len(present) == 4:
        raise BridgeValidationError(
            "all four arms r1, r2, r3, r4 were supplied, so the balance "
            "target is self-inconsistent: there is no unknown arm left to "
            "solve for (use the output endpoint to check an existing bridge)"
        )
    if len(present) < 3:
        raise BridgeValidationError(
            f"balance solve needs exactly three known arms and one unknown "
            f"arm, got {len(present)} known arm(s): {', '.join(present) or 'none'}; "
            "provide exactly three of r1, r2, r3, r4"
        )
    return {arm: validate_resistance(arm, known[arm]) for arm in present}


def validate_source_voltage(value: Any) -> float:
    """Validate Vs. Zero is permitted (caller returns a flagged zero output)."""
    return _finite_number("source_voltage", value)


def validate_galvanometer_resistance(value: Any) -> float:
    """Validate Rg: finite and strictly positive."""
    return validate_resistance("galvanometer_resistance", value)


def validate_config_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise BridgeValidationError(
            "config name must be a non-empty string, got "
            f"{name!r}"
        )
    return name.strip()
