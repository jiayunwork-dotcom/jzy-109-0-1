"""Tests for the closed-form balance solve and its self-consistency closure.

The key closure property: the arm solved from any three known arms, when
inserted back into the forward open-circuit calculation, must give zero
output. Every unknown arm position is exercised.
"""
from __future__ import annotations

import itertools

import pytest

from app import balance, divider

EQUAL_ARMS = {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 100.0}


@pytest.mark.parametrize("unknown", balance.ARMS)
def test_solve_each_unknown_arm_closes_to_zero_output(unknown):
    known = {arm: value for arm, value in EQUAL_ARMS.items() if arm != unknown}
    solved_arm, value = balance.solve_unknown_arm(known)
    assert solved_arm == unknown

    completed = {**known, solved_arm: value}
    assert balance.is_balanced(**completed)
    assert balance.balance_residual(**completed) == pytest.approx(0.0, abs=1e-10)
    # Forward calculation with the solved arm -> zero output at any Vs.
    for vs in (1.0, 6.0, 24.0):
        assert divider.open_circuit_voltage(
            **completed, source_voltage=vs
        ) == pytest.approx(0.0, abs=1e-12)


def test_solve_r3_from_unequal_known_arms():
    # r1=100, r2=200, r4=50 -> r3 = r2*r4/r1 = 100.
    unknown, value = balance.solve_unknown_arm(
        {"r1": 100.0, "r2": 200.0, "r4": 50.0}
    )
    assert unknown == "r3"
    assert value == pytest.approx(100.0)
    completed = {"r1": 100.0, "r2": 200.0, "r3": value, "r4": 50.0}
    assert divider.open_circuit_voltage(
        **completed, source_voltage=9.0
    ) == pytest.approx(0.0, abs=1e-12)


def test_solve_r1_closed_form():
    # r1 = r2*r4/r3 = 200*120/300 = 80
    unknown, value = balance.solve_unknown_arm(
        {"r2": 200.0, "r3": 300.0, "r4": 120.0}
    )
    assert unknown == "r1"
    assert value == pytest.approx(80.0)


@pytest.mark.parametrize(
    "known,expected",
    [
        ({"r1": 100.0, "r2": 200.0, "r3": 300.0}, "r4"),
        ({"r1": 100.0, "r2": 200.0, "r4": 300.0}, "r3"),
        ({"r1": 100.0, "r3": 200.0, "r4": 300.0}, "r2"),
        ({"r2": 100.0, "r3": 200.0, "r4": 300.0}, "r1"),
    ],
)
def test_unknown_arm_is_identified(known, expected):
    solved_arm, _ = balance.solve_unknown_arm(known)
    assert solved_arm == expected


def test_balance_condition_is_opposite_product_not_adjacent_equality():
    # r1 == r2 (adjacent arms equal) but r3 != r4, so r1*r3 != r2*r4 and the
    # bridge is NOT balanced: balance is about opposite-arm products, not
    # about any "adjacent arms must match" rule.
    arms = {"r1": 100.0, "r2": 100.0, "r3": 300.0, "r4": 200.0}
    assert balance.balance_residual(**arms) == pytest.approx(10000.0)
    assert not balance.is_balanced(**arms)

    # Restore balance by the closed-form solve rather than by matching neighbours:
    # given r1=120, r2=80, r3=200 -> r4 = r1*r3/r2 = 300 (no adjacent pair equal).
    _, r4 = balance.solve_unknown_arm({"r1": 120.0, "r2": 80.0, "r3": 200.0})
    assert r4 == pytest.approx(300.0)
    assert divider.open_circuit_voltage(
        r1=120.0, r2=80.0, r3=200.0, r4=r4, source_voltage=10.0
    ) == pytest.approx(0.0, abs=1e-12)


def test_solve_is_deterministic_across_all_permutations():
    base = {"r1": 75.0, "r2": 125.0, "r3": 300.0}
    # r4 = 75*300/125 = 180; order of the mapping must not matter.
    values = [
        balance.solve_unknown_arm(dict(perm))[1]
        for perm in itertools.permutations(base.items())
    ]
    assert all(v == pytest.approx(180.0) for v in values)
