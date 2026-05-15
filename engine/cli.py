"""
astrosis/cli.py — Astrosis CLI implementation
==============================================
"""

import argparse
import sys
import logging
import json
from datetime import datetime, timezone

from .data import tle_ingestor
from .simulation import SimulationContext
from .analysis import report_passes

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("Astrosis")

def main():
    parser = argparse.ArgumentParser(description="Astrosis Orbital Simulator & Analysis Engine")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch and cache TLE data")
    fetch_parser.add_argument("--id", type=str, help="Specific NORAD ID to fetch")
    fetch_parser.add_argument("--force", action="store_true", help="Force refresh from CelesTrak bypassing cache")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run simulation propagation")
    run_parser.add_argument("--steps", type=int, default=100, help="Number of propagation steps")
    run_parser.add_argument("--dt", type=float, default=60.0, help="Time step in seconds")
    
    # Command: passes
    passes_parser = subparsers.add_parser("passes", help="Predict satellite passes for a ground station")
    passes_parser.add_argument("--id", type=int, required=True, help="NORAD ID of satellite")
    passes_parser.add_argument("--lat", type=float, required=True, help="Ground station latitude (deg)")
    passes_parser.add_argument("--lon", type=float, required=True, help="Ground station longitude (deg)")
    passes_parser.add_argument("--alt", type=float, default=0.0, help="Ground station altitude (km)")
    passes_parser.add_argument("--hours", type=float, default=24.0, help="Hours to simulate")
    passes_parser.add_argument("--output", type=str, help="Output JSON file for results")
    passes_parser.add_argument("--area", type=float, default=10.0, help="Satellite cross-section area in m² (drag, default 10 m²)")
    passes_parser.add_argument("--mass", type=float, default=1000.0, help="Satellite mass in kg (drag, default 1000 kg)")
    passes_parser.add_argument("--cd", type=float, default=2.2, help="Drag coefficient (default 2.2)")
    
    args = parser.parse_args()

    if args.command == "fetch":
        logger.info(f"Fetching TLE data (ID={args.id if args.id else 'active constellation'})")
        satellites = tle_ingestor.get_satellites(satellite_id=args.id, force_refresh=args.force)
        logger.info(f"Successfully processed {len(satellites)} TLE entries.")
        
    elif args.command == "run":
        logger.info(f"Initializing simulation context with {args.steps} steps (dt={args.dt}s)")
        ctx = SimulationContext(start_time=0.0)
        
        # Load TLEs (we assume they are fetched already, or fetch active lazily)
        satellites = tle_ingestor.get_satellites(force_refresh=False)
        logger.info(f"Loaded {len(satellites)} satellites.")
        
        # We need SGP4 initialization & ECI propagation logic to be connected.
        logger.info("Starting integration...")
        
        for step in range(args.steps):
            ctx.advance_time(args.dt)
            if step % max(1, args.steps // 10) == 0:
                logger.info(f"Step {step}/{args.steps} (t={ctx.simulation_time:.1f}s)")
                
        logger.info("Simulation completed.")
        
    elif args.command == "passes":
        # Use timezone-aware UTC time, then strip tzinfo to keep naïve UTC convention
        start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info(f"Predicting passes for {args.id} from {start_dt.isoformat()}Z for {args.hours} hours.")
        
        result = report_passes(
            norad_id=args.id,
            lat=args.lat,
            lon=args.lon,
            alt=args.alt,
            start_dt=start_dt,
            hours=args.hours,
            sat_area=args.area,
            sat_mass=args.mass,
            sat_cd=args.cd,
        )
        
        if "error" in result:
            logger.error(f"Error: {result['error']}")
            sys.exit(1)
            
        logger.info(f"Found {len(result.get('passes', []))} passes.")
        
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Wrote pass report to {args.output}")
        else:
            print(json.dumps(result, indent=2))
        
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
