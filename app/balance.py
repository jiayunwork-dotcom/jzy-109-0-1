"""Balance condition and closed-form solve for the unknown arm.

Balance requires the products of OPPOSITE arms to be equal::

    r1 * r3 = r2 * r4

Solving for any single arm gives a closed form: each arm equals the product
of its two neighbours divided by its opposite arm::

    r1 = r2 * r4 / r3
    r2 = r1 * r3 / r4
    r3 = r2 * r4 / r1
    r4 = r1 * r3 / r2
"""
from __future__ import annotations

import math
from typing import Mapping

ARMS: tuple[str, str, str, str] = ("r1", "r2", "r3", "r4")

#: Arm directly across from each arm (the other member of its product pair).
OPPOSITE: dict[str, str] = {
    "r1": "r3",
    "r3": "r1",
    "r2": "r4",
    "r4": "r2",
}

#: The two arms adjacent to each arm around the ring A-B-C-D.
NEIGHBOURS: dict[str, tuple[str, str]] = {
    "r1": ("r2", "r4"),
    "r2": ("r1", "r3"),
    "r3": ("r2", "r4"),
    "r4": ("r1", "r3"),
}

#: Closed-form expression used when solving for each arm, for responses/docs.
FORMULA: dict[str, str] = {
    "r1": "r1 = r2 * r4 / r3",
    "r2": "r2 = r1 * r3 / r4",
    "r3": "r3 = r2 * r4 / r1",
    "r4": "r4 = r1 * r3 / r2",
}


def balance_residual(
    r1: float, r2: float, r3: float, r4: float
) -> float:
    """Signed balance residual ``r1*r3 - r2*r4``; zero exactly at balance."""
    return r1 * r3 - r2 * r4


def is_balanced(
    r1: float,
    r2: float,
    r3: float,
    r4: float,
    rel_tol: float = 1e-9,
) -> bool:
    """True iff the opposite-arm products are (numerically) equal.

    Adjacent arms being equal is deliberately irrelevant.
    """
    return math.isclose(r1 * r3, r2 * r4, rel_tol=rel_tol, abs_tol=0.0)


def solve_unknown_arm(
    known: Mapping[str, float],
) -> tuple[str, float]:
    """Solve for the single missing arm from the balance condition.

    ``known`` must contain exactly three of r1..r4 with positive values;
    validation of that precondition lives in :mod:`app.validation`.
    Returns ``(unknown_arm_name, required_resistance)``.
    """
    unknown = next(arm for arm in ARMS if arm not in known)
    neighbour_a, neighbour_b = NEIGHBOURS[unknown]
    opposite = OPPOSITE[unknown]
    value = known[neighbour_a] * known[neighbour_b] / known[opposite]
    return unknown, value
