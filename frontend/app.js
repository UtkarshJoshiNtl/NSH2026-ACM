/**
 * frontend/app.js — ACM Dashboard Logic
 */

const canvas = document.getElementById('viz-canvas');
const ctx = canvas.getContext('2d');
const simTimeEl = document.getElementById('sim-time');
const objCountEl = document.getElementById('obj-count');
const satCountEl = document.getElementById('sat-count-overlay');
const debCountEl = document.getElementById('deb-count-overlay');
const cdmListEl = document.getElementById('cdm-list');
const satListEl = document.getElementById('sat-list');
const stepBtn = document.getElementById('step-btn');
const statusTextEl = document.getElementById('status-text');

let lastData = null;

// ── Initialize Canvas ────────────────────────────────────────────────────────

function resizeCanvas() {
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;
    render();
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// ── Data Fetching ────────────────────────────────────────────────────────────

async function fetchSnapshot() {
    try {
        const response = await fetch('/api/visualization/snapshot');
        const data = await response.json();
        lastData = data;
        updateUI(data);
        render();
    } catch (err) {
        console.error('Fetch error:', err);
        statusTextEl.innerText = 'FETCH ERROR';
        statusTextEl.style.color = '#f44336';
    }
}

async function stepSim() {
    stepBtn.disabled = true;
    stepBtn.innerText = 'STEPPING...';
    try {
        await fetch('/api/simulate/step', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_seconds: 3600 }) // 1 hour step
        });
        await fetchSnapshot();
        statusTextEl.innerText = 'SIMULATION STEP COMPLETE';
        statusTextEl.style.color = '#4caf50';
    } catch (err) {
        console.error('Step error:', err);
    } finally {
        stepBtn.disabled = false;
        stepBtn.innerText = 'ADVANCE +1H';
    }
}

stepBtn.addEventListener('click', stepSim);

// ── UI Updates ────────────────────────────────────────────────────────────────

function updateUI(data) {
    // Simulation Time
    const date = new Date(data.timestamp * 1000);
    simTimeEl.innerText = date.toISOString().replace('T', ' ').slice(0, 19);

    // Object Counts
    const satCount = data.satellites.length;
    const debCount = data.debris_cloud.length;
    objCountEl.innerText = satCount + debCount;
    satCountEl.innerText = `SATELLITES: ${satCount}`;
    debCountEl.innerText = `DEBRIS: ${debCount}`;

    // CDM List
    cdmListEl.innerHTML = '';
    if (data.active_cdms.length === 0) {
        cdmListEl.innerHTML = '<div class="empty-msg">No active critical conjunctions.</div>';
    } else {
        data.active_cdms.forEach(cdm => {
            const item = document.createElement('div');
            item.className = `cdm-item ${cdm.severity}`;
            item.innerHTML = `
                <div class="cdm-header">
                    <span class="cdm-sat">${cdm.satellite_id}</span>
                    <span class="cdm-dist">${cdm.distance_km.toFixed(3)} km</span>
                </div>
                <div class="cdm-body">
                    vs ${cdm.object_id} (${cdm.severity})
                </div>
            `;
            cdmListEl.appendChild(item);
        });
    }

    // Sat List
    satListEl.innerHTML = '';
    data.satellites.slice(0, 50).forEach(sat => {
        const item = document.createElement('div');
        item.className = 'sat-item';
        item.innerHTML = `
            <span class="sat-id">${sat.id}</span>
            <span class="sat-fuel">${sat.fuel_kg.toFixed(1)}kg</span>
            <span class="sat-status ${sat.status}">${sat.status}</span>
        `;
        satListEl.appendChild(item);
    });
}

// ── Rendering ────────────────────────────────────────────────────────────────

function lonToX(lon) {
    return (lon + 180) * (canvas.width / 360);
}

function latToY(lat) {
    return (90 - lat) * (canvas.height / 180);
}

function render() {
    if (!lastData) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw Grid
    ctx.strokeStyle = '#222';
    ctx.lineWidth = 1;
    for (let x = 0; x <= canvas.width; x += canvas.width / 12) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }
    for (let y = 0; y <= canvas.height; y += canvas.height / 6) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    }

    // Draw Ground Stations (Green crosses)
    if (lastData.ground_stations) {
        ctx.strokeStyle = '#4caf50';
        ctx.lineWidth = 2;
        lastData.ground_stations.forEach(gs => {
            const x = lonToX(gs.lon_deg);
            const y = latToY(gs.lat_deg);
            ctx.beginPath();
            ctx.moveTo(x - 5, y); ctx.lineTo(x + 5, y);
            ctx.moveTo(x, y - 5); ctx.lineTo(x, y + 5);
            ctx.stroke();
        });
    }

    // Draw Debris (Grey points)
    ctx.fillStyle = '#555';
    lastData.debris_cloud.forEach(deb => {
        const [id, lat, lon, alt] = deb;
        ctx.fillRect(lonToX(lon), latToY(lat), 1, 1);
    });

    // Draw Satellites (Colored circles)
    lastData.satellites.forEach(sat => {
        const x = lonToX(sat.lon);
        const y = latToY(sat.lat);

        ctx.fillStyle = sat.status === 'CRITICAL' ? '#f44336' : (sat.status === 'WARNING' ? '#ffeb3b' : '#ff9800');
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();

        if (sat.status === 'CRITICAL' || sat.status === 'WARNING') {
            ctx.strokeStyle = ctx.fillStyle;
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.stroke();
        }
    });
}

// Initial fetch and start interval
fetchSnapshot();
setInterval(fetchSnapshot, 10000);
statusTextEl.innerText = 'TELEMETRY LINK ACTIVE';
