"""
═══════════════════════════════════════════════════════════════════════════
 ACM CORE — autonomy_logic.py
 Decision-making logic for triggering autonomous maneuvers.
 National Space Hackathon 2026

 This module implements the risk-assessment and decision pipeline:
   1. Classify CDM severity (CRITICAL / WARNING / ADVISORY)
   2. Determine if autonomous action is warranted
   3. Coordinate with the physics engine for evasion/recovery planning
   4. Manage satellite status state machine

 The autonomy logic is invoked once per simulation tick after conjunction
 detection has run.

 Usage:
   from core.autonomy_logic import AutonomyManager
   mgr = AutonomyManager(engine)
   actions = mgr.process_cdms(cdms, satellites, current_time)
═══════════════════════════════════════════════════════════════════════════
"""

import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple, Any

# ── Risk Thresholds ───────────────────────────────────────────────────────────
CRITICAL_MISS_KM   = 0.1     # 100 m — triggers autonomous evasion
WARNING_MISS_KM    = 1.0     # 1 km — elevated monitoring
ADVISORY_MISS_KM   = 5.0     # 5 km — logged, no action

SIGNAL_LATENCY_S   = 10.0    # Ground uplink latency (seconds)
COOLDOWN_S         = 600.0   # Thruster rest period (seconds)
EOL_FUEL_KG        = 2.5     # End-of-life fuel threshold (kg)

# Tsiolkovsky constants
ISP_S  = 300.0      # Specific impulse (s)
G0_MS2 = 9.80665    # Standard gravity (m/s²)


# ═══════════════════════════════════════════════════════════════════════════
#  CDM Classification
# ═══════════════════════════════════════════════════════════════════════════

class CDMSeverity:
    CRITICAL = 'CRITICAL'    # miss < 100m → autonomous evasion
    WARNING  = 'WARNING'     # miss < 1km  → elevated monitoring
    ADVISORY = 'ADVISORY'    # miss < 5km  → logged
    CLEAR    = 'CLEAR'       # miss >= 5km → no concern


def classify_cdm(miss_distance_km: float) -> str:
    """Classify a CDM by miss distance."""
    if miss_distance_km < CRITICAL_MISS_KM:
        return CDMSeverity.CRITICAL
    elif miss_distance_km < WARNING_MISS_KM:
        return CDMSeverity.WARNING
    elif miss_distance_km < ADVISORY_MISS_KM:
        return CDMSeverity.ADVISORY
    return CDMSeverity.CLEAR


def compute_fuel_consumed(mass_kg: float, dv_ms: float) -> float:
    """Tsiolkovsky rocket equation: propellant consumed for a given ΔV."""
    return mass_kg * (1.0 - math.exp(-abs(dv_ms) / (ISP_S * G0_MS2)))


# ═══════════════════════════════════════════════════════════════════════════
#  Global Multi-Objective Optimization
# ═══════════════════════════════════════════════════════════════════════════

def optimize_fleet_maneuvers(
    satellites: Dict[str, Any],
    cdms: List[Dict[str, Any]],
    current_time: datetime
) -> Dict[str, Any]:
    """
    Global multi-objective optimization for fleet-wide maneuver planning.
    
    Balances two opposing metrics:
    1. Maximizing Constellation Uptime (time in nominal slots)
    2. Minimizing Total Fuel Expenditure across the fleet
    
    Uses a weighted Pareto optimization approach to find non-dominated solutions.
    
    Args:
        satellites: Dict of satellite_id -> satellite state
        cdms: List of conjunction data messages
        current_time: Current simulation time
        
    Returns:
        Optimization result with recommended maneuvers and metrics
    """
    # Group CDMs by satellite
    cdms_by_sat = {}
    for cdm in cdms:
        sat_id = cdm.get('satelliteId') if isinstance(cdm, dict) else getattr(cdm, 'satelliteId', None)
        if sat_id:
            if sat_id not in cdms_by_sat:
                cdms_by_sat[sat_id] = []
            cdms_by_sat[sat_id].append(cdm)
    
    # Calculate optimization metrics for each satellite
    sat_metrics = {}
    for sat_id, sat in satellites.items():
        fuel_kg = sat.get('fuel_kg', 50.0) if isinstance(sat, dict) else getattr(sat, 'fuel_kg', 50.0)
        status = sat.get('status', 'NOMINAL') if isinstance(sat, dict) else getattr(sat, 'status', 'NOMINAL')
        cdms_for_sat = cdms_by_sat.get(sat_id, [])
        
        # Critical CDMs requiring action
        critical_cdms = [c for c in cdms_for_sat if (c.get('missDistance', 999) if isinstance(c, dict) else getattr(c, 'missDistance', 999)) < CRITICAL_MISS_KM]
        
        # Calculate fuel cost for potential evasion
        total_fuel_cost = 0.0
        for cdm in critical_cdms:
            # Minimum Δv for 100m standoff at LEO ~0.01 km/s = 10 m/s
            dv_ms = 10.0
            mass_kg = (sat.get('currentMass', 500.0) if isinstance(sat, dict) else getattr(sat, 'currentMass', 500.0)) + fuel_kg
            fuel_cost = compute_fuel_consumed(mass_kg, dv_ms)
            total_fuel_cost += fuel_cost
        
        # Uptime penalty if outside nominal slot
        uptime_penalty = 0.0
        if status not in ['NOMINAL', 'RECOVERING']:
            uptime_penalty = 1.0  # Penalty for being evading or EOL
        
        sat_metrics[sat_id] = {
            'fuel_remaining': fuel_kg,
            'fuel_cost': total_fuel_cost,
            'critical_cdms': len(critical_cdms),
            'uptime_penalty': uptime_penalty,
            'can_evade': fuel_kg > total_fuel_cost + EOL_FUEL_KG,
        }
    
    # Optimization: prioritize satellites with critical CDMs but sufficient fuel
    # Weighted score: higher = higher priority for action
    prioritized_sats = []
    for sat_id, metrics in sat_metrics.items():
        if metrics['critical_cdms'] > 0 and metrics['can_evade']:
            # Priority score balances fuel efficiency and urgency
            fuel_ratio = metrics['fuel_remaining'] / 50.0  # Normalized fuel
            urgency = metrics['critical_cdms']  # More CDMs = more urgent
            
            # Higher score = higher priority (more fuel, more urgent)
            priority_score = (fuel_ratio * 0.4) + (urgency * 0.6)
            prioritized_sats.append((sat_id, priority_score, metrics))
    
    # Sort by priority (highest first)
    prioritized_sats.sort(key=lambda x: x[1], reverse=True)
    
    # Fleet-wide optimization: limit total fuel expenditure per tick
    FUEL_BUDGET_PER_TICK = 2.0  # kg maximum total fuel per simulation step
    total_fuel_used = 0.0
    recommended_maneuvers = []
    
    for sat_id, priority_score, metrics in prioritized_sats:
        if total_fuel_used + metrics['fuel_cost'] <= FUEL_BUDGET_PER_TICK:
            recommended_maneuvers.append({
                'satellite_id': sat_id,
                'action': 'evasion',
                'priority_score': priority_score,
                'estimated_fuel_kg': metrics['fuel_cost'],
                'critical_cdms': metrics['critical_cdms'],
            })
            total_fuel_used += metrics['fuel_cost']
    
    # Calculate fleet-wide metrics
    total_fuel_remaining = sum(m['fuel_remaining'] for m in sat_metrics.values())
    total_critical_cdms = sum(m['critical_cdms'] for m in sat_metrics.values())
    avg_uptime = 1.0 - (sum(m['uptime_penalty'] for m in sat_metrics.values()) / len(sat_metrics))
    
    return {
        'recommended_maneuvers': recommended_maneuvers,
        'fleet_metrics': {
            'total_fuel_remaining_kg': total_fuel_remaining,
            'total_critical_cdms': total_critical_cdms,
            'average_uptime': avg_uptime,
            'fuel_efficiency_score': total_fuel_remaining / (50.0 * len(satellites)),
            'uptime_score': avg_uptime,
        },
        'optimization_timestamp': current_time.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Satellite Status State Machine
# ═══════════════════════════════════════════════════════════════════════════

class SatelliteStatus:
    NOMINAL    = 'NOMINAL'     # Normal operations
    EVADING    = 'EVADING'     # Evasion burn in progress
    RECOVERING = 'RECOVERING'  # Return to nominal slot
    EOL        = 'EOL'         # End of life — fuel depleted


# ═══════════════════════════════════════════════════════════════════════════
#  AutonomyManager — Main Decision Engine
# ═══════════════════════════════════════════════════════════════════════════

class AutonomyManager:
    """
    Autonomous decision-making engine for constellation management.

    Processes CDMs, decides when to trigger evasion maneuvers, plans
    recovery burns, and manages the satellite status state machine.
    """

    def __init__(self, state_manager=None):
        """
        Args:
            state_manager: Instance of StateManager.
        """
        self.state = state_manager
        self.engine = state_manager.physics_engine if state_manager else None
        self.action_log: List[Dict] = []
        self._cooldown_tracker: Dict[str, datetime] = {}

    def ingest_telemetry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rulebook-compliant telemetry ingestion (Section 4.1).
        Accepts: {objects: [{id, type, state: {t, r, v}}]}
        Returns: {status, processed_count, active_cdm_warnings}
        """
        processed_count = 0
        objects = payload.get('objects', [])
        
        for obj in objects:
            obj_id = obj.get('id')
            obj_type = obj.get('type')
            state_data = obj.get('state', {})
            
            if obj_type == 'SATELLITE':
                # Update satellite position/velocity
                if obj_id in self.state.satellites:
                    sat = self.state.satellites[obj_id]
                    sat.r = state_data.get('r', sat.r)
                    sat.v = state_data.get('v', sat.v)
                    # Update lat/lon from ECI for dashboard consistency
                    sat.lat, sat.lon, sat.alt_km = self.state._eci_to_latlon(sat.r)
                    processed_count += 1
            elif obj_type == 'DEBRIS':
                # Update or add debris
                if obj_id in self.state.debris:
                    deb = self.state.debris[obj_id]
                    r = state_data.get('r', {'x':0,'y':0,'z':0})
                    deb.lat, deb.lon, deb.alt_km = self.state._eci_to_latlon(r)
                else:
                    r = state_data.get('r', {'x':0,'y':0,'z':0})
                    lat, lon, alt = self.state._eci_to_latlon(r)
                    from api.state_manager import DebrisObject
                    self.state.debris[obj_id] = DebrisObject(id=obj_id, lat=lat, lon=lon, alt_km=alt)
                processed_count += 1

        # Run conjunction detection after ingestion
        self.state.detect_conjunctions()
        
        return {
            "status": "ACK",
            "processed_count": processed_count,
            "active_cdm_warnings": len(self.state.cdms)
        }

    def simulate_step(self, step_seconds: float) -> Dict[str, Any]:
        """
        Rulebook-compliant simulation step (Section 4.3).
        Integrates physics and executes scheduled maneuvers.
        """
        initial_time = self.state.sim_time
        target_time = initial_time + timedelta(seconds=step_seconds)
        
        collisions_detected = 0
        maneuvers_executed = 0
        
        # Integrate physics for all objects using StateManager's simulate_step
        self.state.simulate_step(step_seconds)
        
        # detect_conjunctions is called within propagate_all in most implementations
        # or we call it here manually
        self.state.detect_conjunctions()
        
        # Check for collisions (< 100m)
        for cdm in self.state.cdms:
            if cdm.missDistance < 0.1:
                collisions_detected += 1
        
        # Autonomous Decision Making
        self.process_cdms(self.state.cdms, self.state.satellites, self.state.sim_time)
        
        return {
            "status": "STEP_COMPLETE",
            "new_timestamp": self.state.sim_time.isoformat(),
            "collisions_detected": collisions_detected,
            "maneuvers_executed": maneuvers_executed
        }

    # ── Main Entry Point ──────────────────────────────────────────────────

    def process_cdms(self, cdms: List[Dict], satellites: Dict[str, Dict],
                      current_time: datetime) -> List[Dict]:
        """
        Process CDMs and return a list of autonomous actions taken.

        Args:
            cdms: List of CDMs from detect_conjunctions()
            satellites: Dict of {sat_id: satellite_state}
            current_time: Current simulation time

        Returns:
            List of action dicts: [{type, satellite_id, details}]
        """
        actions = []

        # Step 0: Global multi-objective optimization
        optimization_result = optimize_fleet_maneuvers(satellites, cdms, current_time)
        
        # Log optimization metrics for monitoring
        fleet_metrics = optimization_result['fleet_metrics']
        print(f"[OPTIMIZATION] Fleet metrics - Fuel: {fleet_metrics['total_fuel_remaining_kg']:.1f}kg, "
              f"Critical CDMs: {fleet_metrics['total_critical_cdms']}, "
              f"Uptime: {fleet_metrics['average_uptime']:.2%}")

        # Step 1: Classify and filter CDMs
        actionable = self._filter_actionable_cdms(cdms, satellites, current_time)

        # Step 2: Process each actionable CDM
        for cdm in actionable:
            action = self._process_critical_cdm(cdm, satellites, current_time)
            if action:
                actions.append(action)

        # Step 3: Check for EOL satellites
        eol_actions = self._check_eol_satellites(satellites, current_time)
        actions.extend(eol_actions)

        # Step 4: Update status transitions
        transition_actions = self._update_status_transitions(satellites, current_time)
        actions.extend(transition_actions)

        self.action_log.extend(actions)
        return actions

    # ── Step 1: Filter Actionable CDMs ────────────────────────────────────

    def _filter_actionable_cdms(self, cdms: List[Dict], satellites: Dict[str, Dict],
                                  current_time: datetime) -> List[Dict]:
        """
        A CDM is actionable if ALL of:
          1. missDistance < CRITICAL_MISS_KM (100m)
          2. Satellite status is NOMINAL (not already EVADING/EOL)
          3. Time to TCA > SIGNAL_LATENCY_S (can still uplink)
          4. No existing evasion burn pending for this satellite
          5. Thruster cooldown has elapsed
        """
        now_ts = current_time.timestamp()

        # Pre-filter and classify
        critical = []
        for cdm in cdms:
            miss_dist = cdm.get('missDistance', 999) if isinstance(cdm, dict) else getattr(cdm, 'missDistance', 999)
            severity = classify_cdm(miss_dist)
            if severity != CDMSeverity.CRITICAL:
                continue

            # Check time to TCA
            tca = cdm.get('tca') if isinstance(cdm, dict) else getattr(cdm, 'tca', None)
            if isinstance(tca, str):
                try:
                    tca = datetime.fromisoformat(tca.replace('Z', '+00:00'))
                except ValueError:
                    continue
            elif isinstance(tca, datetime):
                pass
            else:
                continue

            time_to_tca = (tca.timestamp() - now_ts)
            if time_to_tca <= SIGNAL_LATENCY_S:
                print(f"[AUTONOMY] CDM {cdm.get('satelliteId')} — TCA too close "
                      f"({time_to_tca:.0f}s), cannot uplink in time")
                continue

            if isinstance(cdm, dict):
                cdm['_severity'] = severity
                cdm['_tca_dt'] = tca
                cdm['_time_to_tca'] = time_to_tca
            else:
                cdm._severity = severity
                cdm._tca_dt = tca
                cdm._time_to_tca = time_to_tca
            critical.append(cdm)

        # Deduplicate: keep most critical CDM per satellite
        best_per_sat: Dict[str, Dict] = {}
        for cdm_item in critical:
            cdm, metadata = cdm_item if isinstance(cdm_item, tuple) else (cdm_item, {})
            sat_id = cdm['satelliteId'] if isinstance(cdm, dict) else cdm.satelliteId
            existing = best_per_sat.get(sat_id)
            def _get_miss(c):
                c_actual = c[0] if isinstance(c, tuple) else c
                return c_actual['missDistance'] if isinstance(c_actual, dict) else c_actual.missDistance
            if not existing or _get_miss(cdm_item) < _get_miss(existing):
                best_per_sat[sat_id] = cdm_item

        # Filter by satellite status and cooldown
        actionable = []
        for sat_id, cdm in best_per_sat.items():
            sat = satellites.get(sat_id)
            if not sat:
                continue
            sat_r = sat.r.to_np()
            sat_v = sat.v.to_np()
            status = sat.get('status', SatelliteStatus.NOMINAL) if isinstance(sat, dict) else getattr(sat, 'status', SatelliteStatus.NOMINAL)
            if status in (SatelliteStatus.EVADING, SatelliteStatus.EOL):
                print(f"[AUTONOMY] CDM skip: {sat_id} already {status}")
                continue

            # Cooldown check
            last_cooldown = self._cooldown_tracker.get(sat_id)
            if last_cooldown and (current_time - last_cooldown).total_seconds() < COOLDOWN_S:
                print(f"[AUTONOMY] CDM skip: {sat_id} in thruster cooldown")
                continue

            actionable.append(cdm)

        return actionable

    # ── Step 2: Process Critical CDM ──────────────────────────────────────

    def _process_critical_cdm(self, cdm: Dict, satellites: Dict[str, Dict],
                                current_time: datetime, metadata: Dict = None) -> Optional[Dict]:
        """
        Process a single critical CDM:
          1. Plan evasion burn (minimum ΔV in RTN frame)
          2. Plan recovery burn (~0.95× reversal)
          3. Update satellite status → EVADING
          4. Update cooldown tracker

        Returns action dict or None.
        """
        if metadata is None:
            metadata = {}
        sat_id = cdm['satelliteId'] if isinstance(cdm, dict) else cdm.satelliteId
        sat = satellites.get(sat_id)
        if not sat:
            return None

        miss_km = cdm['missDistance'] if isinstance(cdm, dict) else cdm.missDistance
        time_to_tca = metadata.get('_time_to_tca', 3600) if metadata else 3600

        debris_id = cdm.get('debrisId', '?') if isinstance(cdm, dict) else getattr(cdm, 'debrisId', '?')
        print(f"[AUTONOMY] CRITICAL CDM: {sat_id} vs {debris_id} | "
              f"miss={miss_km:.3f}km | TCA=T+{time_to_tca/3600:.1f}h")

        # ── Plan evasion burn ─────────────────────────────────────────────
        evasion_result = self._plan_evasion_burn(sat, cdm, current_time)
        if not evasion_result:
            print(f"[AUTONOMY] No valid evasion burn for {sat_id}")
            return None

        # ── Plan recovery burn ────────────────────────────────────────────
        recovery_result = self._plan_recovery_burn(
            evasion_result['deltaV_ECI'],
            sat.get('currentMass', 500.0) if isinstance(sat, dict) else getattr(sat, 'currentMass', 500.0)
        )

        # ── Update status ─────────────────────────────────────────────────
        if isinstance(sat, dict):
            sat['status'] = SatelliteStatus.EVADING
        else:
            sat.status = SatelliteStatus.EVADING
        self._cooldown_tracker[sat_id] = current_time

        # ── Build action record ───────────────────────────────────────────
        action = {
            'type': 'EVASION',
            'satellite_id': sat_id,
            'debris_id': cdm.get('debrisId') if isinstance(cdm, dict) else getattr(cdm, 'debrisId', None),
            'severity': CDMSeverity.CRITICAL,
            'miss_distance_km': miss_km,
            'evasion': evasion_result,
            'recovery': recovery_result,
            'timestamp': current_time.isoformat(),
        }

        dv_ms = evasion_result.get('dvMagnitude_ms', 0)
        fuel_kg = evasion_result.get('fuelCostKg', 0)
        strategy = evasion_result.get('strategy', 'UNKNOWN')
        print(f"[AUTONOMY] Evasion: {strategy} | ΔV={dv_ms:.1f} m/s | "
              f"fuel={fuel_kg:.3f} kg")

        return action

    # ── Evasion Planning ──────────────────────────────────────────────────

    def _plan_evasion_burn(self, satellite: Dict, cdm: Dict,
                            current_time: datetime) -> Optional[Dict]:
        """
        Plan evasion burn. Uses C++ engine if available, otherwise
        falls back to Python RTN calculation.
        """
        # Try C++ engine first
        if self.engine and hasattr(self.engine, 'plan_evasion'):
            debris = cdm.get('_debris_state') if isinstance(cdm, dict) else getattr(cdm, '_debris_state', None)
            if debris:
                result = self.engine.plan_evasion(satellite, debris)
                if result:
                    return result

        # ── Python fallback: RTN-frame evasion ────────────────────────────
        if isinstance(satellite, dict):
            r = satellite.get('r', {})
            v = satellite.get('v', {})
            fuel_kg = satellite.get('fuelKg', satellite.get('fuel_kg', 50.0))
            mass_kg = satellite.get('currentMass', 500.0)
        else:
            r = satellite.r if hasattr(satellite, 'r') else {}
            v = satellite.v if hasattr(satellite, 'v') else {}
            fuel_kg = satellite.fuel_kg if hasattr(satellite, 'fuel_kg') else 50.0
            mass_kg = 500.0 + fuel_kg

        if not r or not v:
            return None

        # Compute RTN frame
        r_vec = (r.get('x', 0), r.get('y', 0), r.get('z', 0))
        v_vec = (v.get('x', 0), v.get('y', 0), v.get('z', 0))

        r_mag = math.sqrt(sum(c**2 for c in r_vec))
        if r_mag < 1e-10:
            return None

        # R̂ = radial
        R_hat = tuple(c / r_mag for c in r_vec)

        # N̂ = orbit normal = r × v
        N_raw = (
            r_vec[1]*v_vec[2] - r_vec[2]*v_vec[1],
            r_vec[2]*v_vec[0] - r_vec[0]*v_vec[2],
            r_vec[0]*v_vec[1] - r_vec[1]*v_vec[0],
        )
        N_mag = math.sqrt(sum(c**2 for c in N_raw))
        if N_mag < 1e-10:
            return None
        N_hat = tuple(c / N_mag for c in N_raw)

        # T̂ = along-track = N × R
        T_hat = (
            N_hat[1]*R_hat[2] - N_hat[2]*R_hat[1],
            N_hat[2]*R_hat[0] - N_hat[0]*R_hat[2],
            N_hat[0]*R_hat[1] - N_hat[1]*R_hat[0],
        )

        # Try prograde first (cheapest), then retrograde, radial, normal
        strategies = [
            ('PROGRADE',   T_hat,  +1),
            ('RETROGRADE', T_hat,  -1),
            ('RADIAL_OUT', R_hat,  +1),
            ('RADIAL_IN',  R_hat,  -1),
            ('NORMAL_POS', N_hat,  +1),
            ('NORMAL_NEG', N_hat,  -1),
        ]

        # Default ΔV: 10 m/s = 0.010 km/s
        dv_kms = 0.010
        dv_ms = dv_kms * 1000.0

        for name, direction, sign in strategies:
            fuel_cost = compute_fuel_consumed(mass_kg, dv_ms)
            if fuel_cost > fuel_kg:
                continue

            dv_eci = {
                'x': sign * dv_kms * direction[0],
                'y': sign * dv_kms * direction[1],
                'z': sign * dv_kms * direction[2],
            }

            return {
                'deltaV_ECI': dv_eci,
                'dvMagnitude_ms': dv_ms,
                'fuelCostKg': fuel_cost,
                'strategy': name,
            }

        return None

    # ── Recovery Planning ─────────────────────────────────────────────────

    def _plan_recovery_burn(self, evasion_dv: Dict, mass_kg: float) -> Dict:
        """
        Plan recovery burn: ~0.95× reversal of evasion ΔV.
        The 0.95 scale accounts for orbital drift during evasion.
        """
        SCALE = 0.95
        recovery_dv = {
            'x': -evasion_dv.get('x', 0) * SCALE,
            'y': -evasion_dv.get('y', 0) * SCALE,
            'z': -evasion_dv.get('z', 0) * SCALE,
        }
        dv_kms = math.sqrt(sum(v**2 for v in recovery_dv.values()))
        dv_ms = dv_kms * 1000.0
        fuel_cost = compute_fuel_consumed(mass_kg, dv_ms)

        return {
            'deltaV_ECI': recovery_dv,
            'dvMagnitude_ms': dv_ms,
            'fuelCostKg': fuel_cost,
            'strategy': 'RECOVERY_REVERSAL',
        }

    # ── Step 3: EOL Check ─────────────────────────────────────────────────

    def _check_eol_satellites(self, satellites: Dict[str, Dict],
                                current_time: datetime) -> List[Dict]:
        """Check for satellites below EOL fuel threshold."""
        actions = []
        for sat_id, sat in satellites.items():
            if isinstance(sat, dict):
                fuel = sat.get('fuelKg', sat.get('fuel_kg', 50.0))
                status = sat.get('status', SatelliteStatus.NOMINAL)
            else:
                fuel = getattr(sat, 'fuel_kg', 50.0)
                status = getattr(sat, 'status', SatelliteStatus.NOMINAL)

            if fuel <= EOL_FUEL_KG and status != SatelliteStatus.EOL:
                if isinstance(sat, dict):
                    sat['status'] = SatelliteStatus.EOL
                else:
                    sat.status = SatelliteStatus.EOL
                print(f"[AUTONOMY] {sat_id} fuel critical ({fuel:.3f} kg) → EOL")

                actions.append({
                    'type': 'EOL_TRANSITION',
                    'satellite_id': sat_id,
                    'remaining_fuel_kg': fuel,
                    'timestamp': current_time.isoformat(),
                })

        return actions

    # ── Step 4: Status Transitions ────────────────────────────────────────

    def _update_status_transitions(self, satellites: Dict[str, Dict],
                                     current_time: datetime) -> List[Dict]:
        """
        Manage the status state machine:
          EVADING → RECOVERING (after evasion burn executes)
          RECOVERING → NOMINAL (after recovery burn + within slot tolerance)
        """
        actions = []
        for sat_id, sat in satellites.items():
            status = sat.get('status', SatelliteStatus.NOMINAL) if isinstance(sat, dict) else getattr(sat, 'status', SatelliteStatus.NOMINAL)

            if status == SatelliteStatus.EVADING:
                # Check if evasion burn has been executed
                evasion_executed = sat.get('_evasion_executed', False) if isinstance(sat, dict) else getattr(sat, '_evasion_executed', False)
                if evasion_executed:
                    if isinstance(sat, dict):
                        sat['status'] = SatelliteStatus.RECOVERING
                    else:
                        sat.status = SatelliteStatus.RECOVERING
                    actions.append({
                        'type': 'STATUS_TRANSITION',
                        'satellite_id': sat_id,
                        'from': SatelliteStatus.EVADING,
                        'to': SatelliteStatus.RECOVERING,
                        'timestamp': current_time.isoformat(),
                    })

            elif status == SatelliteStatus.RECOVERING:
                # Check if recovery is complete (no pending burns)
                recovery_complete = sat.get('_recovery_complete', False) if isinstance(sat, dict) else getattr(sat, '_recovery_complete', False)
                if recovery_complete:
                    if isinstance(sat, dict):
                        sat['status'] = SatelliteStatus.NOMINAL
                    else:
                        sat.status = SatelliteStatus.NOMINAL
                    actions.append({
                        'type': 'STATUS_TRANSITION',
                        'satellite_id': sat_id,
                        'from': SatelliteStatus.RECOVERING,
                        'to': SatelliteStatus.NOMINAL,
                        'timestamp': current_time.isoformat(),
                    })

        return actions

    # ── Telemetry ─────────────────────────────────────────────────────────

    def get_action_summary(self) -> Dict:
        """Summary of all autonomous actions taken."""
        evasions = sum(1 for a in self.action_log if a['type'] == 'EVASION')
        eol = sum(1 for a in self.action_log if a['type'] == 'EOL_TRANSITION')
        transitions = sum(1 for a in self.action_log if a['type'] == 'STATUS_TRANSITION')

        return {
            'total_actions': len(self.action_log),
            'evasions_triggered': evasions,
            'eol_transitions': eol,
            'status_transitions': transitions,
        }
