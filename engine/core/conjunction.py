"""
astrosis/physics/conjunction.py — Space Traffic Management Logic
================================================================
Identifies close approaches between objects using:
  - Full temporal sweep with pre-propagated history
  - Brent's method for sub-step TCA refinement (< 1 s accuracy)
  - ADVISORY / WARNING / CRITICAL severity tiers
  - Chan's Probability of Collision (simplified 2D Gaussian)
  - State covariance estimated from TLE age
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

from .propagator import rk4_step, propagate_batch_numpy
from ..constants import CRITICAL_DISTANCE, WARNING_DISTANCE, ADVISORY_DISTANCE


@dataclass
class PcResult:
    pc: float = 0.0
    sigma_pos_km: float = 0.0
    computed: bool = False


@dataclass
class ConjunctionWarning:
    sat_id: int = 0
    debris_id: int = 0
    current_distance: float = 0.0   # km at TCA (Brent-refined)
    time_to_closest_approach: float = 0.0  # s
    severity: str = "NONE"
    relative_velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    pc_result: PcResult = field(default_factory=PcResult)

    @property
    def pc(self) -> float:
        return self.pc_result.pc


def _brent_minimise(f, a: float, b: float, tol: float = 0.1) -> float:
    """
    Brent's parabolic interpolation method to minimise f over [a, b].
    Converges super-linearly, guaranteed to find minimum in O(log(1/tol)) steps.
    """
    GOLDEN = 0.3819660
    x = w = v = a + GOLDEN * (b - a)
    fx = fw = fv = f(x)
    d = e = 0.0

    for _ in range(50):
        m = 0.5 * (a + b)
        tol1 = tol * abs(x) + 1e-10
        tol2 = 2.0 * tol1
        if abs(x - m) <= tol2 - 0.5 * (b - a):
            break
        do_golden = True
        if abs(e) > tol1:
            r = (x - w) * (fx - fv)
            q = (x - v) * (fx - fw)
            p = (x - v) * q - (x - w) * r
            q = 2.0 * (q - r)
            if q > 0:
                p = -p
            else:
                q = -q
            r, e = e, d
            if abs(p) < abs(0.5 * q * r) and p > q * (a - x) and p < q * (b - x):
                d = p / q
                u = x + d
                if (u - a) < tol2 or (b - u) < tol2:
                    d = tol1 if x < m else -tol1
                do_golden = False
        if do_golden:
            e = (b - x) if x < m else (a - x)
            d = GOLDEN * e
        u = x + (d if abs(d) >= tol1 else (tol1 if d > 0 else -tol1))
        fu = f(u)
        if fu <= fx:
            if u < x:
                b = x
            else:
                a = x
            v, fv, w, fw, x, fx = w, fw, x, fx, u, fu
        else:
            if u < x:
                a = u
            else:
                b = u
            if fu <= fw or w == x:
                v, fv, w, fw = w, fw, u, fu
            elif fu <= fv or v == x or v == w:
                v, fv = u, fu
    return x


def _chan_pc(miss_dist_km: float, sigma_r_km: float,
             rel_speed_km_s: float, hbr_km: float = 0.01) -> PcResult:
    """
    Chan's method (1997) Probability of Collision.
    Uses the circular encounter approximation for the 2D Gaussian integral:
        Pc ≈ (HBR² / 2σ²) * exp(-x²/2)    where x = miss_dist / sigma_r

    Valid when miss_dist >> sigma_r (dilute encounter regime, most LEO CDMs).
    HBR (hard-body radius) defaults to 10 m for a typical small satellite.
    """
    r = PcResult()
    r.sigma_pos_km = sigma_r_km
    if sigma_r_km <= 0 or rel_speed_km_s <= 0:
        return r
    x = miss_dist_km / sigma_r_km
    r.pc = min((hbr_km**2 / (2.0 * sigma_r_km**2)) * math.exp(-0.5 * x * x), 1.0)
    r.computed = True
    return r


class ConjunctionDetector:
    def __init__(self):
        pass

    def detect(
        self,
        sat_states: List[List[float]],
        debris_states: List[List[float]],
        lookahead_s: float = 86400.0,
        step_s: float = 60.0,
        tle_age_days: float = 1.0,
        mjd0: float = 0.0,
    ) -> List[ConjunctionWarning]:
        """
        Detect potential collisions within a lookahead window.

        Uses KDTree for O(N log N) broad-phase culling, then a temporal sweep
        over pre-propagated history, then Brent's method for TCA refinement.

        tle_age_days controls the position covariance estimate:
            σ_pos ≈ 0.3 * sqrt(tle_age_days)  [km]
        """
        if not sat_states or not debris_states:
            return []

        # 1. Broad Phase: initial-position KDTree cull
        # We cannot rely on t=0 distance alone (pairs may converge), but it
        # eliminates pairs on opposite sides of Earth (> 12,000 km apart).
        sat_pos = [s[:3] for s in sat_states]
        deb_pos = [d[:3] for d in debris_states]
        # Conservative radius: LEO relative velocity ~15 km/s × lookahead; cap at Earth diameter
        broad_radius = min(15.0 * lookahead_s, 12742.0)
        try:
            from scipy.spatial import KDTree
            tree = KDTree(deb_pos)
            candidates = tree.query_ball_point(sat_pos, r=broad_radius)
        except ImportError:
            broad_radius2 = broad_radius * broad_radius
            candidates = []
            for s_pos in sat_pos:
                candidate_list = []
                for deb_idx, d_pos in enumerate(deb_pos):
                    dx = s_pos[0] - d_pos[0]
                    dy = s_pos[1] - d_pos[1]
                    dz = s_pos[2] - d_pos[2]
                    if dx*dx + dy*dy + dz*dz <= broad_radius2:
                        candidate_list.append(deb_idx)
                candidates.append(candidate_list)

        # 2. Pre-propagate all satellites and debris (batch RK4)
        n_steps = int(lookahead_s / step_s)
        remainder_s = lookahead_s - n_steps * step_s
        sample_times = [step * step_s for step in range(n_steps + 1)]

        # Lazy import from accelerator to avoid module-level circular dependency
        from .accelerator import propagate_batch_full_history
        # Pass mjd0 to ensure history matches high-fidelity requirements if mjd0 > 0
        all_sats = propagate_batch_full_history(sat_states, step_s, n_steps, mjd0=mjd0)
        all_debs = propagate_batch_full_history(debris_states, step_s, n_steps, mjd0=mjd0)
        if remainder_s > 1e-9:
            remainder_mjd = mjd0 + (n_steps * step_s) / 86400.0 if mjd0 > 0 else 0.0
            sat_tail = propagate_batch_numpy(all_sats[-1].tolist(), remainder_s, 1, mjd0=remainder_mjd)
            deb_tail = propagate_batch_numpy(all_debs[-1].tolist(), remainder_s, 1, mjd0=remainder_mjd)
            all_sats = np.concatenate((all_sats, np.array([sat_tail], dtype=np.float64)), axis=0)
            all_debs = np.concatenate((all_debs, np.array([deb_tail], dtype=np.float64)), axis=0)
            sample_times.append(lookahead_s)

        # 3. TCA covariance: empirical 1-sigma grows with TLE age
        sigma_pos = 0.3 * math.sqrt(max(tle_age_days, 0.1))

        warnings = []
        for sat_idx, candidate_list in enumerate(candidates):
            for deb_idx in candidate_list:
                min_dist = float('inf')
                tca_coarse = 0.0
                rel_v_at_tca = [0.0, 0.0, 0.0]

                for step, sample_t in enumerate(sample_times):
                    s = all_sats[step][sat_idx]
                    d = all_debs[step][deb_idx]
                    dx = s[0] - d[0]; dy = s[1] - d[1]; dz = s[2] - d[2]
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if dist < min_dist:
                        min_dist = dist
                        tca_coarse = sample_t
                        rel_v_at_tca = [s[3]-d[3], s[4]-d[4], s[5]-d[5]]

                # Quick cull — only refine if under ADVISORY threshold
                if min_dist >= ADVISORY_DISTANCE:
                    continue

                # 4. Brent refinement within ±1 step of coarse TCA
                s0 = tuple(sat_states[sat_idx])
                d0 = tuple(debris_states[deb_idx])
                t_lo = max(0.0, tca_coarse - step_s)
                t_hi = min(lookahead_s, tca_coarse + step_s)

                def dist_at_t(t: float) -> float:
                    # Optimize: Start from nearest pre-propagated step in the history
                    n_nearest = int(t / step_s)
                    t_rem = t - n_nearest * step_s
                    
                    curr_s = tuple(all_sats[n_nearest][sat_idx])
                    curr_d = tuple(all_debs[n_nearest][deb_idx])
                    
                    if t_rem > 1e-9:
                        # Only propagate the remaining small delta
                        curr_s = rk4_step(curr_s, t_rem, mjd0=mjd0, current_step=n_nearest)
                        curr_d = rk4_step(curr_d, t_rem, mjd0=mjd0, current_step=n_nearest)
                        
                    dx = curr_s[0]-curr_d[0]; dy = curr_s[1]-curr_d[1]; dz = curr_s[2]-curr_d[2]
                    return math.sqrt(dx*dx + dy*dy + dz*dz)

                tca_refined = _brent_minimise(dist_at_t, t_lo, t_hi, tol=0.1)
                dist_refined = dist_at_t(tca_refined)

                final_dist = min(min_dist, dist_refined)
                final_tca  = tca_refined if dist_refined < min_dist else tca_coarse

                # 5. Classify severity
                if   final_dist < CRITICAL_DISTANCE:  severity = "CRITICAL"
                elif final_dist < WARNING_DISTANCE:   severity = "WARNING"
                elif final_dist < ADVISORY_DISTANCE:  severity = "ADVISORY"
                else:
                    continue

                # Relative velocity at TCA
                rel_speed = math.sqrt(sum(v*v for v in rel_v_at_tca))
                pc = _chan_pc(final_dist, sigma_pos, rel_speed)

                warnings.append(ConjunctionWarning(
                    sat_id=sat_idx,
                    debris_id=deb_idx,
                    current_distance=final_dist,
                    time_to_closest_approach=final_tca,
                    severity=severity,
                    relative_velocity=rel_v_at_tca,
                    pc_result=pc,
                ))

        return warnings
