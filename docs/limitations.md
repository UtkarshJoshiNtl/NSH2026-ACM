# Known Limitations

> Every model breaks somewhere. This document describes where and why Astrosis
> deviates from reality, so users can make informed decisions about applicability.

## Fixed-Step Integration (RK4)

`dt=10 s` is tuned for circular LEO orbits (altitude 200–2000 km). The fixed
step size is suboptimal for:

- **High eccentricity (e > 0.5):** Satellites move fastest near periapsis. A
  fixed step that is safe at apoapsis may be too coarse at periapsis, causing
  energy drift to accumulate rapidly. For Molniya (e ≈ 0.74) and GTO
  (e ≈ 0.73) orbits, use `dt ≤ 1 s` or switch to an adaptive integrator.
- **Very low altitude (< 180 km):** Drag deceleration becomes large relative to
  gravity. The RK4 local truncation error grows, and the fixed atmosphere table
  resolution at the lower boundary is poor.
- **Very long propagation (> 7 days):** Secular drift from the J4–drag
  cross-coupling term accumulates. Position error grows super-linearly beyond
  7 days. Refresh from TLE epoch every 1–2 days for operational use.

## Atmospheric Model

The US Standard Atmosphere 1976 (USSA1976) is a piecewise exponential
approximation:

- **Above 600 km:** The table extends to a single sentinel entry at 1000 km.
  Density estimates above 600 km are extrapolations; real density varies by
  2–5× due to solar EUV flux and geomagnetic activity.
- **No space weather:** USSA1976 is a static model. It does not account for
  solar cycle variation, geomagnetic storms, or diurnal bulge effects. For
  operational drag modeling, use NRLMSISE-00 or HASDM with real-time
  geomagnetic indices (Kp, F10.7).
- **No thermospheric winds:** The co-rotating atmosphere approximation
  (Earth-rotation velocity correction) neglects high-latitude wind patterns.

## Gravity Model

J2–J4 captures > 99.97 % of the gravitational perturbation in LEO:

| Term   | Contribution | Cumulative |
|--------|-------------|------------|
| J2     | 0.030 %     | 99.970 %   |
| J3     | 0.000023 %  | 99.993 %   |
| J4     | 0.000018 %  | 99.998 %   |
| J5+    | < 0.002 %   | < 100 %    |

The missing 0.002 % from higher harmonics (J5+, tesseral and sectorial terms)
matters in specific regimes:

- **Resonant orbits** (GPS ~ 12 h, Molniya ~ 12 h): Tesseral harmonics cause
  longitudinal drifts that accumulate over weeks.
- **Very low altitude (< 250 km):** Higher-order gravity gradients couple with
  drag to produce measurable trajectory differences.

For engineering-grade conjunction analysis (TLE uncertainty ≈ 0.1–1 km),
the missing terms are negligible.

## TLE Uncertainty

Astrosis propagates from TLE orbital elements. The dominant error source is
the TLE itself, not the propagator:

| TLE age | Typical position uncertainty (LEO) |
|---------|----------------------------------|
| < 1 day | 0.1–0.5 km                       |
| 1–3 days| 0.5–1.5 km                       |
| 7 days  | 1–5 km                           |
| 30 days | 10–50 km                         |

TLEs are mean elements fit to observations over several orbits. They do not
contain covariance information. Any conjunction probability computed from TLEs
uses an empirical uncertainty model (`σ ≈ 0.3 × √age_days` km, Vallado 2013)
and should be treated as **indicative, not authoritative**.

## Probability of Collision (Pc)

Chan's method (simplified 2D circular encounter) is used:

```
Pc ≈ (HBR² / 2σ²) × exp(−x² / 2)
```

Where `HBR = 10 m`, `σ = combined position uncertainty`, `x = miss/σ`.

This model:

- Assumes a circular encounter geometry (valid for short TCA windows).
- Requires `miss_distance >> σ` (dilute regime). Ultra-close approaches
  (`miss < σ`) require numerical integration (Foster / Patera method).
- Uses a fixed hard-body radius. Real HBR depends on satellite attitude,
  shape, and relative orientation at TCA.
- **Is not suitable for operational collision avoidance decisions.**

## No Covariance Propagation

Astrosis propagates deterministic states only. There is no:

- State transition matrix (STM) propagation.
- Unscented / extended Kalman filter.
- Consider covariance analysis.

Without covariance propagation, uncertainty growth over long arcs must be
estimated empirically from TLE age.

## Regime-Specific Breakdowns

| Regime | Issue | Recommended alternative |
|--------|-------|------------------------|
| LEO (200–2000 km) | Well handled | — |
| MEO (GPS, ~ 20 000 km) | SRP + lunisolar are significant | Include with `mjd0 > 0` |
| GEO (~ 35 800 km) | SRP dominates; station-keeping maneuvers needed | Requires maneuver model |
| High e > 0.5 | Fixed dt too coarse near periapsis | Use adaptive integrator |
| Re-entry (< 120 km) | Drag model degrades; aerodynamic heating ignored | Specialised re-entry code |
| Cis-lunar | Earth gravity not dominant | N-body propagator required |

## Benchmarking Caveats

All published benchmarks were collected on an NVIDIA GeForce RTX 2050
(16 SMs, 4 GB VRAM, Turing architecture). Results depend on:

- GPU architecture (Ampere, Hopper, etc.) and memory bandwidth.
- CPU model and cache topology.
- Compiler flags (`-march=native` means the binary is not portable).
- PCIe version and link width (affects CUDA transfer times).

The roofline analysis (see `validation/plots/8_roofline.png`) was performed
on a single GPU with Nsight Compute. Occupancy, warp stall, and cache
behaviour will differ on other hardware.

## What This Means Operationally

> Astrosis is a **research and engineering tool** for high-throughput
> propagation and conjunction screening. It is not a flight-certified
> system. Do not use Astrosis outputs for manoeuvre decisions without
> independent verification by a qualified operator using certified tools
> (e.g., GMAT, STK, SOAP).
