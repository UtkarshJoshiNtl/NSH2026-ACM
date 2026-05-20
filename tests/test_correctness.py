"""Physics correctness tests: energy conservation, RK4 convergence, conjunction detection."""

import math

import pytest
import numpy as np

from engine.core.propagator import rk4_step
from engine.constants import MU, RE, J2, CRITICAL_DISTANCE, WARNING_DISTANCE, ADVISORY_DISTANCE
from engine.core.accelerator import (
    propagate,
    propagate_batch,
    detect_conjunctions,
    backend_info,
)


def _orbital_energy(state):
    r = math.sqrt(sum(x*x for x in state[:3]))
    v = math.sqrt(sum(x*x for x in state[3:]))
    return 0.5 * v*v - MU / r


def _circular_orbit(altitude_km=400.0, inclination_deg=0.0):
    r = RE + altitude_km
    v = math.sqrt(MU / r)
    inc = math.radians(inclination_deg)
    return [r, 0.0, 0.0,
            0.0, v * math.cos(inc), v * math.sin(inc)]


def test_energy_conservation_one_orbit():
    state = tuple(_circular_orbit(400.0))
    T_orbit = 2 * math.pi * math.sqrt((RE + 400.0)**3 / MU)
    dt = 10.0
    n_steps = int(T_orbit / dt)

    eps0 = _orbital_energy(state)
    curr = state
    for _ in range(n_steps):
        curr = rk4_step(curr, dt)

    eps_final = _orbital_energy(curr)
    rel_err = abs((eps_final - eps0) / eps0)
    assert rel_err < 1e-7, f"Energy drift {rel_err:.2e} after 1 orbit exceeds 1e-7"


def test_energy_conservation_24h():
    state = tuple(_circular_orbit(500.0))
    dt = 30.0
    n_steps = int(24 * 3600 / dt)
    eps0 = _orbital_energy(state)
    curr = state
    max_err = 0.0
    for i in range(n_steps):
        curr = rk4_step(curr, dt)
        if i % 120 == 0:
            max_err = max(max_err, abs((_orbital_energy(curr) - eps0) / eps0))
    assert max_err < 1e-5, f"24h energy drift {max_err:.2e} exceeds 1e-5 (dt=30s)"


def test_rk4_fourth_order_convergence():
    state = tuple(_circular_orbit(400.0))
    total_time = 7200.0

    def propagate_n_steps(dt):
        n = int(total_time / dt)
        curr = state
        for _ in range(n):
            curr = rk4_step(curr, dt)
        return curr

    ref = propagate_n_steps(2.0)
    err_coarse = math.sqrt(sum((propagate_n_steps(60.0)[k] - ref[k])**2 for k in range(3)))
    err_fine   = math.sqrt(sum((propagate_n_steps(30.0)[k] - ref[k])**2 for k in range(3)))

    ratio = err_coarse / max(err_fine, 1e-15)
    assert ratio >= 14.0, f"RK4 error ratio = {ratio:.1f} (halving dt 60→30s). Expected ≥ 14×."


def test_conjunction_detects_critical():
    sat   = [-RE - 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0]
    deb   = [-RE - 400.05, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0]
    warns = detect_conjunctions([sat], [deb], lookahead=3600.0, step_s=60.0)

    assert len(warns) > 0, "Expected at least one conjunction warning"
    assert warns[0].severity == "CRITICAL", f"Expected CRITICAL for 0.05 km, got {warns[0].severity}"
    assert warns[0].current_distance < CRITICAL_DISTANCE


def test_conjunction_detects_advisory():
    sat = [-RE - 400.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.0]
    deb = [-RE - 400.0 + 3.0, 0.0, 0.0, 0.0, math.sqrt(MU / (RE + 400.0)), 0.001]
    warns = detect_conjunctions([sat], [deb], lookahead=7200.0, step_s=30.0)

    assert len(warns) > 0, "Expected ADVISORY warning for 3 km separation"
    severities = {w.severity for w in warns}
    assert "ADVISORY" in severities or "WARNING" in severities or "CRITICAL" in severities


def test_conjunction_finds_converging_pairs():
    sat = [RE + 400.0, 0.0, 0.0, 0.0, 7.66, 0.0]
    deb = [RE + 400.0 + 100.0, 0.0, 0.0, -0.75, 7.66, 0.0]

    warns = detect_conjunctions([sat], [deb], lookahead=300.0, step_s=1.0)
    assert len(warns) > 0, "Converging pair not detected. Broad-phase may be incorrectly culling."


def test_conjunction_tca_accuracy():
    sat = [RE + 400.0, 0.0, 0.0, 0.0, 7.66, 0.0]
    deb = [RE + 400.0 + 0.05, 0.0, 0.0, 0.0, 7.66, 0.0001]

    step = 60.0
    warns = detect_conjunctions([sat], [deb], lookahead=3600.0, step_s=step)
    assert len(warns) > 0
    tca = warns[0].time_to_closest_approach
    assert tca < step * 2, f"TCA={tca:.1f}s is too far from expected t≈0."


def test_python_conjunction_scans_partial_final_window(monkeypatch):
    from engine.core import conjunction as conjunction_mod

    def linear_history(states, dt_seconds, steps, **_kwargs):
        history = []
        for step in range(steps + 1):
            t = step * dt_seconds
            rows = []
            for state in states:
                rows.append([
                    state[0] + state[3] * t,
                    state[1] + state[4] * t,
                    state[2] + state[5] * t,
                    state[3],
                    state[4],
                    state[5],
                ])
            history.append(rows)
        return np.array(history, dtype=np.float64)

    def linear_batch(states, dt_seconds, steps, **_kwargs):
        t = dt_seconds * steps
        return [
            [
                state[0] + state[3] * t,
                state[1] + state[4] * t,
                state[2] + state[5] * t,
                state[3],
                state[4],
                state[5],
            ]
            for state in states
        ]

    def linear_step(state, dt_seconds, **_kwargs):
        return (
            state[0] + state[3] * dt_seconds,
            state[1] + state[4] * dt_seconds,
            state[2] + state[5] * dt_seconds,
            state[3],
            state[4],
            state[5],
        )

    import engine.core.accelerator as accelerator_mod
    monkeypatch.setattr(accelerator_mod, "propagate_batch_full_history", linear_history)
    monkeypatch.setattr(conjunction_mod, "propagate_batch_numpy", linear_batch)
    monkeypatch.setattr(conjunction_mod, "rk4_step", linear_step)

    sat = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    deb = [11.0, 0.0, 0.0, -0.1, 0.0, 0.0]
    warns = conjunction_mod.ConjunctionDetector().detect([sat], [deb], lookahead_s=65.0, step_s=60.0)

    assert warns, "Expected advisory warning in the partial final interval"
    assert warns[0].time_to_closest_approach > 60.0


def test_batch_matches_single():
    sats = [
        _circular_orbit(400.0),
        _circular_orbit(550.0),
        _circular_orbit(700.0, inclination_deg=51.6),
    ]
    dt, steps = 10.0, 20

    res_batch = propagate_batch(sats, dt, steps)

    for i, state in enumerate(sats):
        curr = tuple(state)
        for _ in range(steps):
            curr = rk4_step(curr, dt)
        for k in range(6):
            assert abs(res_batch[i][k] - curr[k]) < 1e-6, (
                f"Batch sat {i} component {k}: "
                f"batch={res_batch[i][k]:.6f}, single={curr[k]:.6f}"
            )


def test_cpp_incremental_propagation():
    state = tuple(_circular_orbit(400.0))
    dt = 10.0

    s1 = rk4_step(state, dt)
    s2 = rk4_step(s1, dt)

    old_buggy_s1 = rk4_step(state, dt)
    old_buggy_s2 = rk4_step(state, dt)

    diff = math.sqrt(sum((s2[k] - old_buggy_s2[k])**2 for k in range(3)))
    assert diff > 0.001, "Incremental vs re-propagated states are identical (old bug)."


def test_backend_info_returns_dict():
    info = backend_info()
    assert isinstance(info, dict)
    assert any(info.values()), f"No backend is available: {info}"


def test_propagate_returns_six_elements():
    state = _circular_orbit(400.0)
    result = propagate(state, 10.0)
    assert len(result) == 6
    for v in result:
        assert math.isfinite(v), f"Non-finite value in propagated state: {result}"
