import argparse
import sys
import logging
import json
from datetime import datetime, timezone

from .io.data import tle_ingestor
from .simulation import SimulationContext
from .geo.analysis import report_passes


def main():
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    logger = logging.getLogger("Astrosis")

    parser = argparse.ArgumentParser(description="Astrosis Orbital Simulator & Analysis Engine")
    parser.add_argument("--version", action="version", version="Astrosis 0.1.0")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch and cache TLE data")
    fetch_parser.add_argument("--id", type=str, help="NORAD ID")
    fetch_parser.add_argument("--force", action="store_true", help="Force refresh")

    run_parser = subparsers.add_parser("run", help="Run simulation propagation")
    run_parser.add_argument("--steps", type=int, default=100, help="Number of steps")
    run_parser.add_argument("--dt", type=float, default=60.0, help="Step size (s)")

    passes_parser = subparsers.add_parser("passes", help="Predict satellite passes")
    passes_parser.add_argument("--id", type=int, required=True, help="NORAD ID")
    passes_parser.add_argument("--lat", type=float, required=True, help="Station lat (deg)")
    passes_parser.add_argument("--lon", type=float, required=True, help="Station lon (deg)")
    passes_parser.add_argument("--alt", type=float, default=0.0, help="Station alt (km)")
    passes_parser.add_argument("--hours", type=float, default=24.0, help="Hours to simulate")
    passes_parser.add_argument("--output", type=str, help="Output JSON file")
    passes_parser.add_argument("--area", type=float, default=10.0, help="Sat area (m²)")
    passes_parser.add_argument("--mass", type=float, default=1000.0, help="Sat mass (kg)")
    passes_parser.add_argument("--cd", type=float, default=2.2, help="Drag coefficient")

    args = parser.parse_args()

    if args.command == "fetch":
        satellites = tle_ingestor.get_satellites(satellite_id=args.id, force_refresh=args.force)
        logger.info(f"Processed {len(satellites)} TLE entries.")

    elif args.command == "run":
        ctx = SimulationContext(start_time=0.0)
        satellites = tle_ingestor.get_satellites(force_refresh=False)
        for step in range(args.steps):
            ctx.advance_time(args.dt)
            if step % max(1, args.steps // 10) == 0:
                logger.info(f"Step {step}/{args.steps} (t={ctx.simulation_time:.1f}s)")
        logger.info(f"Finished {args.steps} steps at dt={args.dt}s. Output not yet wired.")

    elif args.command == "passes":
        start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info(f"Passes for {args.id} from {start_dt.isoformat()}Z, {args.hours}h.")

        result = report_passes(
            norad_id=args.id, lat=args.lat, lon=args.lon, alt=args.alt,
            start_dt=start_dt, hours=args.hours,
            sat_area=args.area, sat_mass=args.mass, sat_cd=args.cd,
        )

        if "error" in result:
            logger.error(result["error"])
            sys.exit(1)

        logger.info(f"Found {len(result.get('passes', []))} passes.")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Wrote to {args.output}")
        else:
            print(json.dumps(result, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
