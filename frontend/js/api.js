/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — API Layer (Live Backend Only)
   All data comes from the FastAPI backend at localhost:8000.
   No demo mode, no synthetic fallback data.
   ═══════════════════════════════════════════════════════════════════════════ */

const API = (() => {
  const BASE = '';

  // ── Fetch helper with timeout ─────────────────────────────────────────────
  async function _fetch(path, opts = {}, timeoutMs = 8000) {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(BASE + path, { signal: controller.signal, ...opts });
      clearTimeout(tid);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (e) {
      clearTimeout(tid);
      throw e;
    }
  }

  // ── Public API ────────────────────────────────────────────────────────────

  async function fetchSnapshot() {
    return await _fetch('/api/visualization/snapshot');
  }

  async function fetchAlerts(afterId = 0) {
    try {
      return await _fetch(`/api/alerts?after=${afterId}`);
    } catch (_) { return { alerts: [], latest_id: afterId }; }
  }

  async function fetchConstellationStats() {
    try {
      return await _fetch('/api/constellation/stats');
    } catch (_) { return null; }
  }

  async function simulateStep(stepSeconds = 10) {
    try {
      return await _fetch('/api/simulate/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step_seconds: stepSeconds }),
      });
    } catch (_) { return null; }
  }

  async function startAutoSim(stepSeconds = 10, intervalMs = 1000) {
    try {
      return await _fetch('/api/simulate/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step_seconds: stepSeconds, real_interval_ms: intervalMs }),
      });
    } catch (_) {}
  }

  async function stopAutoSim() {
    try {
      return await _fetch('/api/simulate/stop', { method: 'POST' });
    } catch (_) {}
  }

  async function getSimStatus() {
    try { return await _fetch('/api/simulate/status'); }
    catch (_) { return { running: false }; }
  }

  async function fetchHealth() {
    try { return await _fetch('/health'); }
    catch (_) { return { status: 'OFFLINE' }; }
  }

  // Legacy stubs kept so callers don't throw if referenced
  function isDemo()    { return false; }
  function setDemo()   {}
  function getDemoTime() { return new Date(); }
  function getDemoCDMs() { return []; }
  function getDemoManeuvers() { return []; }

  return {
    fetchSnapshot, fetchAlerts, fetchConstellationStats,
    simulateStep, startAutoSim, stopAutoSim, getSimStatus,
    fetchHealth,
    isDemo, setDemo, getDemoTime, getDemoCDMs, getDemoManeuvers,
  };
})();
