"""Galvanometer-loaded bridge output via the Thevenin equivalent.

Looking into the output terminals B and D, the whole bridge reduces to:

* V_th = open-circuit output voltage (see :mod:`app.divider`);
* R_th = (r1 || r4) + (r2 || r3), because with the ideal voltage source
  shorted, A and C coincide, so each midpoint sees its two branch arms in
  parallel and the two parallel pairs sit in series between B and D.

With a galvanometer of internal resistance Rg connected between B and D:

      Ig = V_th / (R_th + Rg)          (positive: B -> D)
      Vg = Ig * Rg = V_th * Rg / (R_th + Rg)

As Rg -> infinity, Vg -> V_th (the open-circuit reading), as it must.
"""
from __future__ import annotations

from dataclasses import dataclass

from .divider import open_circuit_voltage


def parallel(a: float, b: float) -> float:
    """Parallel combination of two positive resistances."""
    return a * b / (a + b)


def thevenin_resistance(r1: float, r2: float, r3: float, r4: float) -> float:
    """Equivalent resistance seen from the B-D output terminals."""
    return parallel(r1, r4) + parallel(r2, r3)


@dataclass(frozen=True)
class GalvanometerReading:
    """Actual galvanometer reading once it is connected to the bridge."""

    thevenin_voltage: float
    """V_th: the bridge's open-circuit output, in volts."""

    thevenin_resistance: float
    """R_th: bridge output resistance, in ohms."""

    galvanometer_resistance: float
    """Rg: galvanometer internal resistance, in ohms."""

    current: float
    """Ig through the galvanometer (B -> D when positive), in amperes --
    this is the deflection-driving quantity."""

    terminal_voltage: float
    """Vg actually appearing across the galvanometer terminals, in volts."""


def galvanometer_reading(
    r1: float,
    r2: float,
    r3: float,
    r4: float,
    source_voltage: float,
    galvanometer_resistance: float,
) -> GalvanometerReading:
    """Strict Thevenin solve for the loaded galvanometer.

    Callers validate resistances beforehand, so no division-by-zero is
    possible here: all arms and Rg are positive, hence ``R_th + Rg > 0``.
    """
    v_th = open_circuit_voltage(r1, r2, r3, r4, source_voltage)
    r_th = thevenin_resistance(r1, r2, r3, r4)
    total = r_th + galvanometer_resistance
    current = v_th / total
    terminal_voltage = current * galvanometer_resistance
    return GalvanometerReading(
        thevenin_voltage=v_th,
        thevenin_resistance=r_th,
        galvanometer_resistance=galvanometer_resistance,
        current=current,
        terminal_voltage=terminal_voltage,
    )
