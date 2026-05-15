"""
engine/cli.py — Astrosis CLI
=============================
Demo commands: fetch, propagate, conjunction
"""

import argparse
import sys
import logging
import math

from .io.data import tle_ingestor
from .core.propagator import rk4_step
from .core.conjunction import ConjunctionDetector
from .constants import MU, RE

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("Astrosis")


def _cmd_fetch(args):
    logger.info(f"Fetching TLE data (ID={args.id if args.id else 'active constellation'})")
    satellites = tle_ingestor.get_satellites(satellite_id=args.id, force_refresh=args.force)
    logger.info(f"Successfully processed {len(satellites)} TLE entries.")


def _cmd_propagate(args):
    line1 = "1 25544U 98067A   25135.54166667  .00007700  00000+0  14217-3 0  9994"
    line2 = "2 25544  51.6412 227.8960 0002170 183.9820 176.1230 15.49534348505800"

    from sgp4.api import Satrec, jday
    sat = Satrec.twoline2rv(line1, line2)
    jd, jf = jday(2025, 5, 15, 12, 0, 0)
    err, r, v = sat.sgp4(jd, jf)
    if err:
        logger.error(f"SGP4 error {err}")
        sys.exit(1)
    state = list(r) + list(v)

    dt = args.dt
    steps = args.steps
    curr = tuple(state)
    e0 = 0.5 * sum(v * v for v in curr[3:]) - MU / math.sqrt(sum(x * x for x in curr[:3]))
    max_drift = 0.0
    for i in range(steps):
        curr = rk4_step(curr, dt)
        if i % max(1, steps // 20) == 0:
            ei = 0.5 * sum(x * x for x in curr[3:]) - MU / math.sqrt(sum(x * x for x in curr[:3]))
            max_drift = max(max_drift, abs((ei - e0) / e0))

    logger.info(f"Propagated ISS for {steps} steps (dt={dt}s, total={steps * dt:.0f}s)")
    logger.info(f"  Final state: x={curr[0]:.2f} y={curr[1]:.2f} z={curr[2]:.2f} km")
    logger.info(f"  Final velocity: vx={curr[3]:.4f} vy={curr[4]:.4f} vz={curr[5]:.4f} km/s")
    logger.info(f"  Max energy drift: {max_drift:.2e} (target < 1e-5)")


def _cmd_conjunction(args):
    detector = ConjunctionDetector()

    def orbit(alt, inc_deg):
        r = RE + alt
        v = math.sqrt(MU / r)
        inc = math.radians(inc_deg)
        return [r, 0.0, 0.0, 0.0, v * math.cos(inc), v * math.sin(inc)]

    sats = [orbit(400.0, 0.0)]
    deb = [orbit(400.05, 0.0)]
    sats[0][0] = -sats[0][0]
    deb[0][0] = -deb[0][0]
    deb[0][4] += 0.001

    warns = detector.detect(sats, deb, lookahead_s=args.lookahead, step_s=args.step)
    if not warns:
        logger.info("No conjunctions detected.")
        return

    for w in warns:
        logger.info(
            f"Conjunction: sat={w.sat_id} debris={w.debris_id} "
            f"distance={w.current_distance:.4f} km "
            f"TCA={w.time_to_closest_approach:.1f}s "
            f"severity={w.severity}"
        )


def main():
    parser = argparse.ArgumentParser(description="Astrosis — GPU-Accelerated Orbital Propagation Engine")
    sub = parser.add_subparsers(dest="command")

    fetch_p = sub.add_parser("fetch", help="Fetch and cache TLE data")
    fetch_p.add_argument("--id", type=str, help="NORAD ID")
    fetch_p.add_argument("--force", action="store_true", help="Force refresh")

    prop_p = sub.add_parser("propagate", help="Propagate ISS for N steps")
    prop_p.add_argument("--steps", type=int, default=8640, help="Number of steps")
    prop_p.add_argument("--dt", type=float, default=10.0, help="Step size (s)")

    conj_p = sub.add_parser("conjunction", help="Demo conjunction screening")
    conj_p.add_argument("--lookahead", type=float, default=3600.0, help="Lookahead (s)")
    conj_p.add_argument("--step", type=float, default=60.0, help="Sweep step (s)")

    args = parser.parse_args()
    if args.command == "fetch":
        _cmd_fetch(args)
    elif args.command == "propagate":
        _cmd_propagate(args)
    elif args.command == "conjunction":
        _cmd_conjunction(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
