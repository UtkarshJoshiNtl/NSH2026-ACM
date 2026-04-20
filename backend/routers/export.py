"""
backend/routers/export.py — Data Export Endpoints
===============================================
Export simulation data, CDMs, and state history in various formats.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, CSVResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import json
import csv
import io

from backend.core.state_manager import state_mgr
from backend.middleware import get_current_user

router = APIRouter()


class ExportRequest(BaseModel):
    format: str = "json"  # json, csv
    include_debris: bool = True
    include_satellites: bool = True
    include_cdms: bool = True


@router.post("/export/snapshot")
async def export_snapshot(req: ExportRequest, user: dict = Depends(get_current_user)):
    """Export current simulation snapshot."""
    try:
        snapshot = state_mgr.get_summary()

        if req.format == "json":
            return JSONResponse(content=snapshot)
        elif req.format == "csv":
            # Create CSV for satellites
            output = io.StringIO()
            writer = csv.writer(output)

            # Write satellites
            if req.include_satellites:
                writer.writerow(
                    ["TYPE", "ID", "X", "Y", "Z", "VX", "VY", "VZ", "FUEL", "STATUS"]
                )
                for sat in state_mgr.get_all_satellites():
                    writer.writerow(
                        [
                            "SATELLITE",
                            sat.id,
                            sat.r[0],
                            sat.r[1],
                            sat.r[2],
                            sat.v[0],
                            sat.v[1],
                            sat.v[2],
                            sat.m_fuel,
                            sat.status,
                        ]
                    )

            # Write debris
            if req.include_debris:
                writer.writerow([])
                writer.writerow(["TYPE", "ID", "X", "Y", "Z", "VX", "VY", "VZ"])
                for deb in state_mgr.get_all_debris():
                    writer.writerow(
                        [
                            "DEBRIS",
                            deb.id,
                            deb.r[0],
                            deb.r[1],
                            deb.r[2],
                            deb.v[0],
                            deb.v[1],
                            deb.v[2],
                        ]
                    )

            output.seek(0)
            return CSVResponse(
                content=output.getvalue(),
                filename=f"astrosis_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported format: {req.format}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/cdms")
async def export_cdms(user: dict = Depends(get_current_user)):
    """Export active Conjunction Data Messages (CDMs)."""
    try:
        cdms = state_mgr.active_cdms

        # Convert to JSON-serializable format
        export_data = []
        for cdm in cdms:
            export_data.append(
                {
                    "satellite_id": cdm.get("satellite_id"),
                    "debris_id": cdm.get("debris_id"),
                    "distance_km": cdm.get("distance_km"),
                    "severity": cdm.get("severity"),
                    "time_to_closest_approach": cdm.get("time_to_closest_approach"),
                }
            )

        return JSONResponse(
            content={
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "count": len(export_data),
                "cdms": export_data,
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/history")
async def export_history(user: dict = Depends(get_current_user)):
    """Export simulation history (maneuvers and CDMs)."""
    try:
        context = state_mgr.get_context("default")

        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "simulation_time": context.simulation_time if context else 0,
            "maneuver_history": context.maneuver_history if context else [],
            "active_cdms": state_mgr.active_cdms,
        }

        return JSONResponse(content=export_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
