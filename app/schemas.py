"""Pydantic request/response models for the HTTP boundary.

These describe the wire shape only; semantic validation (positive
resistances, exactly three known arms, ...) lives in
:mod:`app.validation` so it can be reused outside HTTP.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .balance import ARMS


class OutputRequest(BaseModel):
    """Forward calculation: bridge output for one operating point.

    Arms travel as an unvalidated mapping so that missing/extra/non-positive
    arms are all caught by app.validation with an explicit ``reason`` (400)
    rather than a schema-level 422. Provide exactly one of ``arms``/``config``.
    """

    source_voltage: float = Field(..., description="bridge source Vs, volts")
    arms: Optional[dict[str, Any]] = Field(
        default=None, description="explicit four arms keyed r1..r4"
    )
    config: Optional[str] = Field(
        default=None, description="name of a registered bridge preset"
    )
    galvanometer_resistance: Optional[float] = Field(
        default=None,
        description="galvanometer internal resistance Rg, ohms; when given, "
        "the loaded deflection is returned as well",
    )

    @field_validator("source_voltage")
    @classmethod
    def _vs_is_number(cls, v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("source_voltage must be a real number")
        return v


class GalvanometerResult(BaseModel):
    thevenin_voltage: float = Field(..., description="V_th, volts")
    thevenin_resistance: float = Field(..., description="R_th, ohms")
    galvanometer_resistance: float = Field(..., description="Rg, ohms")
    current: float = Field(
        ..., description="Ig through the galvanometer (B -> D if positive), A"
    )
    terminal_voltage: float = Field(
        ..., description="voltage across the galvanometer, volts"
    )


class OutputResponse(BaseModel):
    arms: dict[str, float]
    source_voltage: float
    balanced: bool = Field(
        ..., description="whether opposite-arm products are equal (r1*r3 = r2*r4)"
    )
    open_circuit_voltage: float = Field(
        ..., description="V_B - V_D with the output open, volts"
    )
    branch_potentials: dict[str, float] = Field(
        ..., description="midpoint potentials {b: V_B, d: V_D}, volts"
    )
    thevenin_resistance: Optional[float] = Field(
        default=None, description="R_th, ohms (always reported)"
    )
    galvanometer: Optional[GalvanometerResult] = Field(
        default=None,
        description="present only when galvanometer_resistance was supplied",
    )
    note: Optional[str] = None


class SolveRequest(BaseModel):
    """Inverse calculation: exactly three known arms, solve the fourth."""

    known_arms: dict[str, Any] = Field(
        ...,
        description="exactly three of {r1, r2, r3, r4}; the missing arm is "
        "solved from r1*r3 = r2*r4",
    )


class SolveResponse(BaseModel):
    unknown_arm: str
    resistance: float = Field(..., description="required value of the unknown arm, ohms")
    known_arms: dict[str, float]
    formula: str = Field(..., description="closed form applied")
    balance_residual: float = Field(
        ..., description="r1*r3 - r2*r4 after inserting the solved arm (must be ~0)"
    )
    note: str


class ConfigRegisterRequest(BaseModel):
    name: str
    arms: dict[str, Any] = Field(
        ..., description="four arms keyed r1..r4; validated in app.validation"
    )


class ConfigResponse(BaseModel):
    name: str
    arms: dict[str, float]


class ConfigListResponse(BaseModel):
    configs: list[ConfigResponse]


class ErrorResponse(BaseModel):
    error: str
    reason: str


__all__ = [
    "ARMS",
    "ConfigListResponse",
    "ConfigRegisterRequest",
    "ConfigResponse",
    "ErrorResponse",
    "GalvanometerResult",
    "OutputRequest",
    "OutputResponse",
    "SolveRequest",
    "SolveResponse",
]
