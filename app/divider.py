"""Open-circuit output voltage of the Wheatstone bridge.

The output is computed strictly as the difference of the two divider-branch
midpoint potentials -- never as an informal "a few ohms off" estimate.

Arm numbering convention (see ``docs/bridge-model.md`` for the full diagram)::

            A o---------------- source Vs (+)
               \\        /
                r1      r2
                /        \\
     output  B o          o D  output
                \\        /
                r4      r3
                /        \\
            C o---------------- source Vs (-), reference 0 V

* Left branch  A -> B -> C: r1 (upper) then r4 (lower); midpoint is B.
* Right branch A -> D -> C: r2 (upper) then r3 (lower); midpoint is D.
* The open-circuit output is measured between B and D:

      V_out = V_B - V_D
            = Vs * ( r4 / (r1 + r4) - r3 / (r2 + r3) )

Balance (V_out == 0) holds iff the products of the two pairs of OPPOSITE
arms are equal:

      r1 * r3 = r2 * r4      (r1 faces r3; r2 faces r4)

It is NOT "adjacent arms equal".
"""
from __future__ import annotations


def branch_potential(upper: float, lower: float, source_voltage: float) -> float:
    """Midpoint potential of one divider branch.

    Potential at the junction of *upper* (towards the source +) and *lower*
    (towards the source - reference), as a plain voltage divider. Callers are
    expected to have validated that both resistances are positive.
    """
    return source_voltage * lower / (upper + lower)


def open_circuit_voltage(
    r1: float,
    r2: float,
    r3: float,
    r4: float,
    source_voltage: float,
) -> float:
    """Open-circuit bridge output ``V_B - V_D`` in volts.

    Linearity in ``source_voltage`` is exact: doubling Vs doubles the output
    at the same imbalance. The sign flips when the swept arm crosses balance.
    """
    v_b = branch_potential(r1, r4, source_voltage)
    v_d = branch_potential(r2, r3, source_voltage)
    return v_b - v_d
