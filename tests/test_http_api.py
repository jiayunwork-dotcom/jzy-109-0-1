"""End-to-end HTTP tests against the FastAPI app.

Pins the required relations through the wire:

* opposite-arm products equal -> open-circuit output is zero;
* doubling Vs doubles |output| at the same imbalance;
* the solve endpoint's unknown arm, fed back into the output endpoint,
  gives zero (forward/inverse closure over HTTP);
* plus the equal-arm baseline, sign-flip on crossing balance, zero-Vs
  handling, validation errors with reasons, and preset independence.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.registry import registry


@pytest.fixture()
def client():
    registry.clear()
    with TestClient(app) as c:
        yield c
    registry.clear()


def output(client, **body):
    return client.post("/bridge/output", json=body)


# ---------------------------------------------------------------- baseline

def test_equal_arm_baseline_zero_output_is_pinned(client):
    response = output(
        client,
        source_voltage=10.0,
        arms={"r1": 100, "r2": 100, "r3": 100, "r4": 100},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["balanced"] is True
    assert data["open_circuit_voltage"] == 0.0
    assert data["branch_potentials"] == {"b": 5.0, "d": 5.0}


# ----------------------------------------------------- required relation 1

def test_opposite_product_balance_gives_zero_output(client):
    # 100*300 = 150*200 = 30000, arms themselves unequal.
    response = output(
        client,
        source_voltage=12.0,
        arms={"r1": 100, "r2": 150, "r3": 300, "r4": 200},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["balanced"] is True
    assert data["open_circuit_voltage"] == pytest.approx(0.0, abs=1e-12)
    assert data["note"] is not None and "balanced" in data["note"]


def test_adjacent_equality_without_opposite_product_is_unbalanced(client):
    response = output(
        client,
        source_voltage=10.0,
        arms={"r1": 100, "r2": 100, "r3": 300, "r4": 200},
    )
    data = response.json()
    assert data["balanced"] is False
    assert data["open_circuit_voltage"] != 0.0


# ----------------------------------------------------- required relation 2

def test_doubling_source_voltage_doubles_output(client):
    arms = {"r1": 100, "r2": 100, "r3": 100, "r4": 175}
    v1 = output(client, source_voltage=5.0, arms=arms).json()["open_circuit_voltage"]
    v2 = output(client, source_voltage=10.0, arms=arms).json()["open_circuit_voltage"]
    assert v1 != 0.0
    assert abs(v2) == pytest.approx(2 * abs(v1), rel=1e-12)


def test_sign_flips_when_arm_crosses_balance(client):
    fixed = {"r1": 100, "r2": 100, "r3": 100}
    below = output(client, source_voltage=10.0, arms={**fixed, "r4": 80}).json()
    at = output(client, source_voltage=10.0, arms={**fixed, "r4": 100}).json()
    above = output(client, source_voltage=10.0, arms={**fixed, "r4": 130}).json()
    assert below["open_circuit_voltage"] < 0.0
    assert at["open_circuit_voltage"] == 0.0
    assert above["open_circuit_voltage"] > 0.0


# ----------------------------------------------------- required relation 3

@pytest.mark.parametrize("missing", ["r1", "r2", "r3", "r4"])
def test_solve_then_forward_is_a_zero_output_closure(client, missing):
    known = {"r1": 120.0, "r2": 80.0, "r3": 200.0, "r4": 300.0}
    del known[missing]
    solve = client.post("/bridge/solve", json={"known_arms": known})
    assert solve.status_code == 200, solve.text
    s = solve.json()
    assert s["unknown_arm"] == missing
    assert s["balance_residual"] == pytest.approx(0.0, abs=1e-9)

    completed = {**known, missing: s["resistance"]}
    forward = output(client, source_voltage=15.0, arms=completed)
    assert forward.status_code == 200
    f = forward.json()
    assert f["balanced"] is True
    assert f["open_circuit_voltage"] == pytest.approx(0.0, abs=1e-12)


def test_solve_returns_closed_form_formula(client):
    s = client.post(
        "/bridge/solve",
        json={"known_arms": {"r1": 100, "r2": 200, "r4": 50}},
    ).json()
    assert s["unknown_arm"] == "r3"
    assert s["resistance"] == pytest.approx(100.0)
    assert "r3 = r2 * r4 / r1" in s["formula"]


# -------------------------------------------------------- galvanometer load

def test_galvanometer_reading_uses_thevenin(client):
    arms = {"r1": 100, "r2": 100, "r3": 100, "r4": 150}
    body = dict(source_voltage=10.0, arms=arms, galvanometer_resistance=250)
    data = output(client, **body).json()
    g = data["galvanometer"]
    assert g is not None
    assert g["thevenin_voltage"] == pytest.approx(data["open_circuit_voltage"])
    assert g["current"] == pytest.approx(
        g["thevenin_voltage"]
        / (g["thevenin_resistance"] + g["galvanometer_resistance"])
    )
    assert g["terminal_voltage"] == pytest.approx(
        g["current"] * g["galvanometer_resistance"]
    )
    assert abs(g["terminal_voltage"]) < abs(data["open_circuit_voltage"])


def test_galvanometer_at_balance_reads_zero(client):
    data = output(
        client,
        source_voltage=10.0,
        arms={"r1": 100, "r2": 150, "r3": 300, "r4": 200},
        galvanometer_resistance=50,
    ).json()
    assert data["galvanometer"]["current"] == pytest.approx(0.0, abs=1e-12)


# --------------------------------------------------------------- zero source

def test_zero_source_voltage_is_zero_output_flagged_not_error(client):
    response = output(
        client,
        source_voltage=0.0,
        arms={"r1": 100, "r2": 200, "r3": 300, "r4": 400},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["open_circuit_voltage"] == 0.0
    assert "zero" in data["note"]

    with_g = output(
        client,
        source_voltage=0.0,
        arms={"r1": 100, "r2": 200, "r3": 300, "r4": 400},
        galvanometer_resistance=100,
    ).json()
    assert with_g["galvanometer"]["current"] == 0.0
    assert with_g["galvanometer"]["terminal_voltage"] == 0.0


# ------------------------------------------------------------- invalid input

def test_non_positive_arm_rejected_before_calculation(client):
    response = output(
        client,
        source_voltage=10.0,
        arms={"r1": 0, "r2": 100, "r3": 100, "r4": 100},
    )
    assert response.status_code == 400
    err = response.json()
    assert err["error"] == "invalid_input"
    assert "strictly positive" in err["reason"]
    assert "r1" in err["reason"]


def test_negative_arm_rejected(client):
    response = output(
        client,
        source_voltage=10.0,
        arms={"r1": 100, "r2": -5, "r3": 100, "r4": 100},
    )
    assert response.status_code == 400
    assert "r2" in response.json()["reason"]


def test_missing_arm_returns_reason_not_500(client):
    response = output(client, source_voltage=10.0, arms={"r1": 1, "r2": 1, "r3": 1})
    assert response.status_code == 400
    reason = response.json()["reason"]
    assert "missing" in reason and "r4" in reason


def test_extra_unknown_arm_name_rejected(client):
    response = output(
        client,
        source_voltage=10.0,
        arms={"r1": 1, "r2": 1, "r3": 1, "r4": 1, "rx": 2},
    )
    assert response.status_code == 400
    assert "rx" in response.json()["reason"]


def test_solve_with_four_arms_is_self_inconsistent_400(client):
    response = client.post(
        "/bridge/solve",
        json={"known_arms": {"r1": 1, "r2": 1, "r3": 1, "r4": 1}},
    )
    assert response.status_code == 400
    assert "self-inconsistent" in response.json()["reason"]


def test_solve_with_two_arms_rejected(client):
    response = client.post(
        "/bridge/solve", json={"known_arms": {"r1": 1, "r2": 1}}
    )
    assert response.status_code == 400
    assert "exactly three" in response.json()["reason"]


def test_solve_with_zero_known_arm_does_not_divide_by_zero(client):
    response = client.post(
        "/bridge/solve",
        json={"known_arms": {"r1": 1, "r2": 0, "r3": 1}},
    )
    assert response.status_code == 400
    assert "strictly positive" in response.json()["reason"]


def test_must_supply_arms_or_config_exactly_once(client):
    both = output(
        client, source_voltage=1.0,
        arms={"r1": 1, "r2": 1, "r3": 1, "r4": 1}, config="x",
    )
    neither = output(client, source_voltage=1.0)
    assert both.status_code == 400
    assert neither.status_code == 400


# ------------------------------------------------------------------ presets

def test_preset_lifecycle_and_use(client):
    created = client.post(
        "/configs",
        json={
            "name": "lab-equal",
            "arms": {"r1": 100, "r2": 100, "r3": 100, "r4": 100},
        },
    )
    assert created.status_code == 201
    listed = client.get("/configs").json()["configs"]
    assert [c["name"] for c in listed] == ["lab-equal"]

    data = output(client, source_voltage=8.0, config="lab-equal").json()
    assert data["arms"] == {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 100.0}
    assert data["open_circuit_voltage"] == 0.0

    assert client.delete("/configs/lab-equal").status_code == 204
    assert client.get("/configs/lab-equal").status_code == 404


def test_two_presets_keep_independent_arms(client):
    client.post(
        "/configs",
        json={"name": "a", "arms": {"r1": 100, "r2": 100, "r3": 100, "r4": 100}},
    )
    client.post(
        "/configs",
        json={"name": "b", "arms": {"r1": 50, "r2": 60, "r3": 70, "r4": 80}},
    )
    # Replace a only; b must be unchanged.
    client.post(
        "/configs",
        json={"name": "a", "arms": {"r1": 1, "r2": 2, "r3": 3, "r4": 4}},
    )
    a = client.get("/configs/a").json()["arms"]
    b = client.get("/configs/b").json()["arms"]
    assert a == {"r1": 1.0, "r2": 2.0, "r3": 3.0, "r4": 4.0}
    assert b == {"r1": 50.0, "r2": 60.0, "r3": 70.0, "r4": 80.0}


def test_unknown_config_is_404(client):
    assert output(client, source_voltage=1.0, config="nope").status_code == 404


def test_register_invalid_arms_rejected(client):
    response = client.post(
        "/configs",
        json={"name": "bad", "arms": {"r1": -1, "r2": 1, "r3": 1, "r4": 1}},
    )
    assert response.status_code == 400


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
