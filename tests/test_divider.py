"""Relationship tests for the open-circuit divider calculation.

These pin the physical relationships the service is built on:

* equal-arm baseline -> zero output (hand-checkable regression case);
* equal opposite-arm products -> zero open-circuit output;
* "adjacent arms equal" that does NOT satisfy r1*r3 = r2*r4 is NOT balance;
* sweeping one arm through balance changes the output monotonically and
  flips its sign at the crossing;
* doubling the source voltage doubles |output| at fixed imbalance.
"""
from __future__ import annotations

import pytest

from app import balance, divider

# Hand-checkable baseline: four equal arms.
EQUAL_ARMS = {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 100.0}


def test_equal_arm_baseline_output_is_exactly_zero():
    # Every midpoint sits at Vs/2; V_B - V_D = 0 for any source.
    for vs in (1.0, 5.0, 12.0):
        assert divider.open_circuit_voltage(**EQUAL_ARMS, source_voltage=vs) == 0.0


def test_equal_arm_baseline_branch_potentials_are_half_source():
    vs = 8.0
    v_b = divider.branch_potential(100.0, 100.0, vs)
    v_d = divider.branch_potential(100.0, 100.0, vs)
    assert v_b == v_d == vs / 2


def test_opposite_arm_products_equal_implies_zero_output():
    # r1*r3 = 100*300 = 30000 = 150*200 = r2*r4, arms deliberately NOT equal.
    arms = {"r1": 100.0, "r2": 150.0, "r3": 300.0, "r4": 200.0}
    assert balance.is_balanced(**arms)
    assert divider.open_circuit_voltage(
        **arms, source_voltage=12.0
    ) == pytest.approx(0.0, abs=1e-12)


def test_adjacent_arms_equal_is_not_balance():
    # r1 == r2 (adjacent) yet r1*r3 = 30000 != 20000 = r2*r4: output nonzero.
    # Guards against the classic misstatement "balanced when adjacent arms equal".
    arms = {"r1": 100.0, "r2": 100.0, "r3": 300.0, "r4": 200.0}
    assert not balance.is_balanced(**arms)
    assert divider.open_circuit_voltage(**arms, source_voltage=10.0) != 0.0


def test_sweeping_unknown_arm_monotone_and_sign_flips_at_balance():
    # Fix r1 = r2 = r3 = 100; balance is at r4 = 100.
    fixed = {"r1": 100.0, "r2": 100.0, "r3": 100.0}
    vs = 10.0

    at_balance = divider.open_circuit_voltage(**fixed, r4=100.0, source_voltage=vs)
    below = divider.open_circuit_voltage(**fixed, r4=50.0, source_voltage=vs)
    above = divider.open_circuit_voltage(**fixed, r4=200.0, source_voltage=vs)

    assert at_balance == 0.0
    assert below < 0.0 < above  # sign flips crossing the balance point

    # Monotonic change of the output as r4 alone increases.
    sweep = [
        divider.open_circuit_voltage(**fixed, r4=r4, source_voltage=vs)
        for r4 in (60.0, 80.0, 100.0, 120.0, 140.0)
    ]
    assert all(earlier < later for earlier, later in zip(sweep, sweep[1:]))


def test_doubling_source_voltage_doubles_output_magnitude():
    # Pinned relationship: output is linear in Vs for fixed arms.
    arms = {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 150.0}
    v_one = divider.open_circuit_voltage(**arms, source_voltage=5.0)
    v_two = divider.open_circuit_voltage(**arms, source_voltage=10.0)
    assert v_one != 0.0
    assert abs(v_two) == pytest.approx(2.0 * abs(v_one), rel=1e-12)
    # Same ratio around the other sign too.
    v_neg = divider.open_circuit_voltage(**arms, source_voltage=-5.0)
    assert v_neg == pytest.approx(-v_one)
