"""
backend/routers/simulations.py — Simulation Context Management
==============================================================
API endpoints for managing simulation contexts (multi-tenancy).
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.database import get_db, Simulation, User
from backend.core.state_manager import state_mgr
from backend.middleware import get_current_user

router = APIRouter()


# Request/Response Models
class SimulationCreate(BaseModel):
    name: str


class SimulationResponse(BaseModel):
    id: str
    name: str
    simulation_time: float
    created_at: str
    updated_at: str
    is_active: bool
    
    class Config:
        from_attributes = True


@router.post("/simulations", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
async def create_simulation(
    sim_data: SimulationCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new simulation context for the user."""
    # Verify user exists
    db_user = db.query(User).filter(User.id == user["user_id"]).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create simulation record in database
    db_sim = Simulation(
        user_id=user["user_id"],
        name=sim_data.name,
        simulation_time=0.0
    )
    db.add(db_sim)
    db.commit()
    db.refresh(db_sim)
    
    # Create simulation context in state manager
    try:
        state_mgr.create_context(db_sim.id)
    except ValueError as e:
        # Rollback if context creation fails
        db.delete(db_sim)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return SimulationResponse(
        id=db_sim.id,
        name=db_sim.name,
        simulation_time=db_sim.simulation_time,
        created_at=db_sim.created_at.isoformat(),
        updated_at=db_sim.updated_at.isoformat(),
        is_active=db_sim.is_active
    )


@router.get("/simulations", response_model=List[SimulationResponse])
async def list_simulations(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all simulations for the current user."""
    simulations = db.query(Simulation).filter(
        Simulation.user_id == user["user_id"],
        Simulation.is_active == True
    ).all()
    
    return [
        SimulationResponse(
            id=sim.id,
            name=sim.name,
            simulation_time=sim.simulation_time,
            created_at=sim.created_at.isoformat(),
            updated_at=sim.updated_at.isoformat(),
            is_active=sim.is_active
        )
        for sim in simulations
    ]


@router.get("/simulations/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific simulation."""
    sim = db.query(Simulation).filter(
        Simulation.id == simulation_id,
        Simulation.user_id == user["user_id"]
    ).first()
    
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found"
        )
    
    return SimulationResponse(
        id=sim.id,
        name=sim.name,
        simulation_time=sim.simulation_time,
        created_at=sim.created_at.isoformat(),
        updated_at=sim.updated_at.isoformat(),
        is_active=sim.is_active
    )


@router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation(
    simulation_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a simulation context."""
    sim = db.query(Simulation).filter(
        Simulation.id == simulation_id,
        Simulation.user_id == user["user_id"]
    ).first()
    
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found"
        )
    
    # Delete simulation context from state manager
    state_mgr.delete_context(simulation_id)
    
    # Mark as inactive in database (soft delete)
    sim.is_active = False
    db.commit()
    
    return None


@router.get("/simulations/{simulation_id}/state")
async def get_simulation_state(
    simulation_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current state summary of a simulation."""
    # Verify ownership
    sim = db.query(Simulation).filter(
        Simulation.id == simulation_id,
        Simulation.user_id == user["user_id"]
    ).first()
    
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found"
        )
    
    # Get state from state manager
    summary = state_mgr.get_summary(simulation_id)
    
    return summary
