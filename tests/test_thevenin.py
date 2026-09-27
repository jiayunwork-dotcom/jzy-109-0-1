"""Tests for the Thevenin-equivalent galvanometer solve."""
from __future__ import annotations

import pytest

from app import divider, thevenin


def test_thevenin_resistance_is_two_parallel_pairs_in_series():
    # (r1 || r4) + (r2 || r3)
    r_th = thevenin.thevenin_resistance(100.0, 200.0, 300.0, 400.0)
    expected = 100.0 * 400.0 / 500.0 + 200.0 * 300.0 / 500.0
    assert r_th == pytest.approx(expected)
    assert r_th < 400.0 / 2 + 500.0 / 2


def test_loaded_galvanometer_follows_thevenin_formula():
    arms = {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 150.0}
    r_g = 250.0
    reading = thevenin.galvanometer_reading(
        **arms, source_voltage=10.0, galvanometer_resistance=r_g
    )
    v_oc = divider.open_circuit_voltage(**arms, source_voltage=10.0)
    r_th = thevenin.thevenin_resistance(**arms)

    assert reading.thevenin_voltage == pytest.approx(v_oc)
    assert reading.thevenin_resistance == pytest.approx(r_th)
    assert reading.current == pytest.approx(v_oc / (r_th + r_g))
    assert reading.terminal_voltage == pytest.approx(
        v_oc * r_g / (r_th + r_g)
    )
    # Loading can only shrink the terminal voltage magnitude.
    assert abs(reading.terminal_voltage) < abs(v_oc)
    # V = I*R consistency.
    assert reading.terminal_voltage == pytest.approx(
        reading.current * r_g
    )


def test_infinite_galvanometer_resistance_recovers_open_circuit():
    arms = {"r1": 100.0, "r2": 150.0, "r3": 300.0, "r4": 175.0}
    reading = thevenin.galvanometer_reading(
        **arms, source_voltage=5.0, galvanometer_resistance=1e12
    )
    v_oc = divider.open_circuit_voltage(**arms, source_voltage=5.0)
    assert reading.terminal_voltage == pytest.approx(v_oc, rel=1e-9)
    # I = V_th/(R_th+Rg) -> vanishingly small; terminal voltage -> V_th.
    assert abs(reading.current) == pytest.approx(abs(v_oc) / 1e12, rel=1e-3)


def test_balanced_bridge_gives_zero_galvanometer_current():
    # r1*r3 = 100*300 = 30000 = 150*200 = r2*r4
    reading = thevenin.galvanometer_reading(
        r1=100.0, r2=150.0, r3=300.0, r4=200.0,
        source_voltage=10.0, galvanometer_resistance=100.0,
    )
    assert reading.thevenin_voltage == pytest.approx(0.0, abs=1e-12)
    assert reading.current == pytest.approx(0.0, abs=1e-12)
    assert reading.terminal_voltage == pytest.approx(0.0, abs=1e-12)


def test_galvanometer_sign_matches_open_circuit_sign():
    reading = thevenin.galvanometer_reading(
        r1=100.0, r2=100.0, r3=100.0, r4=50.0,
        source_voltage=10.0, galvanometer_resistance=120.0,
    )
    v_oc = divider.open_circuit_voltage(
        r1=100.0, r2=100.0, r3=100.0, r4=50.0, source_voltage=10.0
    )
    assert v_oc < 0.0
    assert reading.current < 0.0  # current direction flips with the polarity
