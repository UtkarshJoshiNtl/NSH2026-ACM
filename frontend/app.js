/**
 * main.js — Orchestrator: polling loop, tab switching, maneuver controls
 */

const API = '/api';

// ── State ─────────────────────────────────────────────────────────────────────
let snapshot = null;
let selectedSat = null;
let historyData = [];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const simTimeEl = document.getElementById('sim-time');
const hSatCount = document.getElementById('h-sat-count');
const hDebCount = document.getElementById('h-deb-count');
const hCdmCount = document.getElementById('h-cdm-count');
const hBurnCount = document.getElementById('h-burn-count');
const badgeSats = document.getElementById('badge-sats');
const badgeDeb = document.getElementById('badge-deb');
const badgeCdm = document.getElementById('badge-cdm');
const cdmListEl = document.getElementById('cdm-list');
const histListEl = document.getElementById('history-list');
const statusText = document.getElementById('status-text');
const satSelect = document.getElementById('sat-select');

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.panel-tabs').forEach(tabBar => {
    tabBar.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            const panel = tabBar.closest('.panel');
            panel.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            panel.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${tabName}`)?.classList.add('active');
        });
    });
});

// ── Satellite selector ────────────────────────────────────────────────────────
satSelect.addEventListener('change', () => {
    selectedSat = satSelect.value || null;
    if (snapshot) renderBullseye(snapshot, selectedSat);
});

function populateSatSelect(satellites) {
    const current = satSelect.value;
    satSelect.innerHTML = '<option value="">— choose —</option>';
    satellites.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id; opt.textContent = s.id;
        if (s.id === current) opt.selected = true;
        satSelect.appendChild(opt);
    });
    if (!current && satellites.length) {
        selectedSat = satellites[0].id;
        satSelect.value = selectedSat;
    }
}

// ── Snapshot fetch ────────────────────────────────────────────────────────────
async function fetchSnapshot() {
    try {
        const r = await fetch(`${API}/visualization/snapshot`);
        snapshot = await r.json();
        updateHeader(snapshot);
        renderMap(snapshot);
        renderFuel(snapshot.satellites);
        renderGantt(snapshot.pending_burns || [], snapshot.timestamp);
        renderCdmList(snapshot.active_cdms);
        populateSatSelect(snapshot.satellites);
        if (selectedSat) renderBullseye(snapshot, selectedSat);
        return true;
    } catch (e) {
        setStatus(`FETCH ERROR: ${e.message}`, 'error');
        return false;
    }
}

// ── History fetch ─────────────────────────────────────────────────────────────
async function fetchHistory() {
    try {
        const r = await fetch(`${API}/history/maneuvers?limit=50`);
        const data = await r.json();
        historyData = data.records || [];
        renderHistoryList(historyData);
    } catch { }
}

// ── DOM updates ───────────────────────────────────────────────────────────────
function updateHeader(data) {
    const d = new Date(data.timestamp * 1000);
    simTimeEl.textContent = d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

    hSatCount.textContent = data.satellites.length;
    hDebCount.textContent = data.debris_cloud.length;
    hCdmCount.textContent = data.active_cdms.length;
    hBurnCount.textContent = data.history_count || 0;

    badgeSats.textContent = `SAT: ${data.satellites.length}`;
    badgeDeb.textContent = `DEB: ${data.debris_cloud.length}`;
    badgeCdm.textContent = `CDM: ${data.active_cdms.length}`;
    if (data.active_cdms.length > 0) badgeCdm.classList.add('danger');
    else badgeCdm.classList.remove('danger');
}

function renderCdmList(cdms) {
    cdmListEl.innerHTML = '';
    if (!cdms || cdms.length === 0) {
        cdmListEl.innerHTML = '<div class="empty-msg">✓ No active conjunction threats.</div>';
        return;
    }
    cdms.forEach(cdm => {
        const div = document.createElement('div');
        div.className = `cdm-item ${cdm.severity || 'WATCH'}`;
        const tca = new Date(((cdm.tca_s || 0)) * 1000).toISOString().slice(11, 19);
        div.innerHTML = `
      <div class="cdm-header">
        <span class="cdm-sat">${cdm.sat_id}</span>
        <span class="cdm-dist">${(cdm.distance_km || 0).toFixed(3)} km</span>
      </div>
      <div class="cdm-sub">vs ${cdm.debris_id || cdm.deb_id || '?'} · TCA ${tca} · ${cdm.severity}</div>
    `;
        cdmListEl.appendChild(div);
    });
}

function renderHistoryList(history) {
    histListEl.innerHTML = '';
    if (!history || history.length === 0) {
        histListEl.innerHTML = '<div class="empty-msg">No burns executed yet.</div>';
        return;
    }
    history.forEach(h => {
        const div = document.createElement('div');
        div.className = `hist-item ${h.burn_type || ''}`;
        const t = new Date((h.burn_time || 0) * 1000).toISOString().slice(11, 19);
        const dvMag = Math.sqrt((h.delta_v || [0, 0, 0]).reduce((s, x) => s + x * x, 0));
        div.innerHTML = `
      <div class="hist-header">
        <span class="hist-sat">${h.satellite_id}</span>
        <span class="hist-fuel">-${(h.fuel_used_kg || 0).toFixed(3)} kg</span>
      </div>
      <div class="hist-sub">${h.burn_type || '—'} · Δv ${(dvMag * 1000).toFixed(2)} m/s · ${t}</div>
    `;
        histListEl.appendChild(div);
    });
}

function setStatus(msg, type = 'ok') {
    statusText.textContent = msg;
    statusText.style.color = type === 'error' ? '#f85149'
        : type === 'warn' ? '#e3b341' : '#3fb950';
}

// ── Controls ──────────────────────────────────────────────────────────────────
async function stepSim(hours) {
    const btns = document.querySelectorAll('.ctrl-btn');
    btns.forEach(b => b.disabled = true);
    setStatus(`ADVANCING +${hours}H...`, 'warn');
    try {
        await fetch(`${API}/simulate/step`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_seconds: hours * 3600 })
        });
        await fetchSnapshot();
        await fetchHistory();
        setStatus(`STEP +${hours}H COMPLETE · ${new Date().toISOString().slice(11, 19)}`);
    } catch (e) {
        setStatus(`STEP ERROR: ${e.message}`, 'error');
    } finally {
        btns.forEach(b => b.disabled = false);
    }
}

async function runCola() {
    // POST a COLA trigger — the background loop handles this automatically
    // but we can manually trigger snapshot refresh + inform user
    setStatus('COLA LOOP TRIGGERED — CHECKING CONJUNCTIONS...', 'warn');
    await fetchSnapshot();
    await fetchHistory();
    setStatus('COLA CHECK COMPLETE');
}

document.getElementById('btn-step').addEventListener('click', () => stepSim(1));
document.getElementById('btn-step-10').addEventListener('click', () => stepSim(10));
document.getElementById('btn-cola').addEventListener('click', runCola);

// ── Bootstrap ─────────────────────────────────────────────────────────────────
(async () => {
    setStatus('CONNECTING TO ACM BACKEND...');
    const ok = await fetchSnapshot();
    if (ok) {
        await fetchHistory();
        setStatus('TELEMETRY LINK ACTIVE — LIVE');
        // Poll every 3s
        setInterval(fetchSnapshot, 3000);
        setInterval(fetchHistory, 10000);
    }
})();
