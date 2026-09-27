"""Tests for the in-process preset registry.

Two presets must hold independent arm values -- editing one never leaks
into the other. State is process-local by design.
"""
from __future__ import annotations

import threading

import pytest

from app.registry import BridgeRegistry, ConfigNotFoundError
from app.validation import BridgeValidationError


def make_registry():
    return BridgeRegistry()


def test_register_and_retrieve_roundtrip():
    reg = make_registry()
    arms = {"r1": 100.0, "r2": 200.0, "r3": 300.0, "r4": 400.0}
    reg.register("lab-a", arms)
    config = reg.get("lab-a")
    assert config.arms() == arms
    assert [c.name for c in reg.list()] == ["lab-a"]


def test_two_configs_have_independent_arms():
    reg = make_registry()
    arms_a = {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 100.0}
    arms_b = {"r1": 50.0, "r2": 60.0, "r3": 70.0, "r4": 80.0}
    reg.register("alpha", arms_a)
    reg.register("beta", arms_b)

    # Reregister alpha; beta must remain untouched.
    reg.register("alpha", {**arms_a, "r4": 999.0})
    assert reg.get("alpha").arms()["r4"] == 999.0
    assert reg.get("beta").arms() == arms_b
    assert reg.get("alpha").arms()["r1"] == arms_a["r1"]


def test_mutating_caller_dict_does_not_change_stored_config():
    reg = make_registry()
    arms = {"r1": 100.0, "r2": 100.0, "r3": 100.0, "r4": 100.0}
    reg.register("alpha", arms)
    arms["r1"] = -1.0  # caller-side mutation after registration
    assert reg.get("alpha").arms()["r1"] == 100.0


def test_missing_config_raises_named_error():
    reg = make_registry()
    with pytest.raises(ConfigNotFoundError):
        reg.get("ghost")
    with pytest.raises(ConfigNotFoundError):
        reg.delete("ghost")


def test_register_validates_arms():
    reg = make_registry()
    with pytest.raises(BridgeValidationError):
        reg.register("bad", {"r1": 1, "r2": 1, "r3": 1})  # missing r4
    with pytest.raises(BridgeValidationError):
        reg.register("bad", {"r1": 0, "r2": 1, "r3": 1, "r4": 1})


def test_delete_and_re_register():
    reg = make_registry()
    reg.register("c", {"r1": 1, "r2": 1, "r3": 1, "r4": 1})
    reg.delete("c")
    with pytest.raises(ConfigNotFoundError):
        reg.get("c")
    reg.register("c", {"r1": 2, "r2": 2, "r3": 2, "r4": 2})
    assert reg.get("c").r1 == 2.0


def test_concurrent_register_does_not_corrupt_store():
    reg = make_registry()

    def worker(i):
        for j in range(100):
            reg.register(
                f"cfg-{i % 4}",
                {"r1": float(i * 100 + j + 1), "r2": 1.0, "r3": 1.0, "r4": 1.0},
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(c.name for c in reg.list()) == [
        "cfg-0",
        "cfg-1",
        "cfg-2",
        "cfg-3",
    ]
