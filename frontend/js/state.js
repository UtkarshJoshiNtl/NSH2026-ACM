/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — Shared Application State
   ═══════════════════════════════════════════════════════════════════════════ */

const AppState = (() => {
  // ── State ────────────────────────────────────────────────────────────────
  const state = {
    timestamp: null,
    simTime: null,       // alias — same as timestamp
    satellites: [],
    debrisCloud: [],
    cdms: [],
    maneuvers: [],
    selectedSatelliteId: null,
    dvHistory: [],          // last 20 total ΔV values
    totalDeltaV: 0,
    apiLatency: 0,
    isConnected: false,
    lastSnapshotTime: null,
  };

  // ── Event System ─────────────────────────────────────────────────────────
  const listeners = {};

  function on(event, fn) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(fn);
  }

  function emit(event, data) {
    if (listeners[event]) {
      listeners[event].forEach(fn => fn(data));
    }
  }

  // ── Mutators ─────────────────────────────────────────────────────────────
  function updateSnapshot(data) {
    state.timestamp = data.timestamp;
    state.simTime   = data.timestamp;   // alias used by GroundTrack/Bullseye
    state.satellites = data.satellites || [];
    state.debrisCloud = data.debris_cloud || [];
    state.lastSnapshotTime = new Date();
    state.isConnected = true;
    emit('snapshot', state);
  }

  function updateCDMs(cdms) {
    state.cdms = cdms || [];
    emit('cdms', state.cdms);
  }

  function updateManeuvers(maneuvers) {
    state.maneuvers = maneuvers || [];
    emit('maneuvers', state.maneuvers);
  }

  function selectSatellite(satId) {
    state.selectedSatelliteId = satId;
    emit('satellite-selected', satId);
  }

  function addDvDataPoint(totalDv) {
    state.totalDeltaV = totalDv;
    state.dvHistory.push(totalDv);
    if (state.dvHistory.length > 20) state.dvHistory.shift();
    emit('dv-updated', state.dvHistory);
  }

  function setApiLatency(ms) {
    state.apiLatency = ms;
  }

  function setDisconnected() {
    state.isConnected = false;
    emit('disconnected');
  }

  // ── Getters ──────────────────────────────────────────────────────────────
  function getState() { return state; }
  function getSelectedSatellite() {
    return state.satellites.find(s => s.id === state.selectedSatelliteId) || null;
  }
  function getCDMsForSatellite(satId) {
    return state.cdms.filter(c => c.satelliteId === satId);
  }

  return {
    state, on, emit,
    updateSnapshot, updateCDMs, updateManeuvers,
    selectSatellite, addDvDataPoint, setApiLatency, setDisconnected,
    getState, getSelectedSatellite, getCDMsForSatellite,
  };
})();
