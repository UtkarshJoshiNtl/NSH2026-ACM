/**
 * main.js — Application bootloader and orchestration loop
 */

import { state, updateState, onStateChange } from './state.js';
import { fetchSnapshot } from './api.js';
import { initEvents } from './events.js';
import { setText, getEl } from './utils/dom.js';

// Track last shown alert to avoid spam
let lastAlertId = null;

// Renderers
import { updateHeader } from './renderers/header.js';
import { renderManeuvers } from './components/maneuvers.js';

// Components
import { initMap, renderMap } from './components/map.js';

import { POLLING_INTERVALS } from './constants.js';

async function bootstrap() {
    console.log('Astrosis Physics Simulator initializing...');

    // Initialize component canvases
    initMap('map-canvas');

    // Initialize event listeners
    initEvents();

    // Set up reactive rendering
    onStateChange((s) => {
        updateHeader(s.snapshot);
        renderMap(s.snapshot);
        renderManeuvers(s.snapshot?.pending_burns || []);

        setText('sim-time', s.snapshot ? new Date(s.snapshot.timestamp * 1000).toISOString().replace('T', ' ').slice(0, 19) : '—');
        setText('h-deb-count', s.snapshot?.debris_cloud ? s.snapshot.debris_cloud.length : 0);
        setText('status-text', s.status);

        // Check for critical conjunctions and show alert
        const conjunctionAlert = getEl('conjunction-alert');
        const alertText = getEl('alert-text');
        
        if (conjunctionAlert && s.snapshot?.active_cdms) {
            const criticalCdms = s.snapshot.active_cdms.filter(cdm => 
                cdm.severity === 'CRITICAL' || cdm.distance_km < 0.1
            );
            
            if (criticalCdms.length > 0) {
                const alertId = criticalCdms.map(cdm => cdm.satellite_id + cdm.debris_id).join(',');
                if (alertId !== lastAlertId) {
                    lastAlertId = alertId;
                    alertText.textContent = `${criticalCdms.length} critical conjunction(s) detected`;
                    conjunctionAlert.classList.remove('hidden');
                }
            }
        }
    });

    // Initial fetch
    const snapshot = await fetchSnapshot();
    updateState({
        snapshot,
        status: snapshot ? 'SIMULATION ACTIVE — LIVE' : 'OFFLINE (SERVER ERROR)'
    });

    // Hide loading overlay
    const overlay = getEl('loading-overlay');
    if (overlay) overlay.classList.add('hidden');

    // Polling loops with overlap protection and stale detection
    let lastUpdate = Date.now();
    let isFetchingSnapshot = false;

    setInterval(() => {
        if (Date.now() - lastUpdate > 10000) {
            updateState({ status: 'SIMULATION DEGRADED — STALE DATA' });
        }
    }, 1000);

    setInterval(async () => {
        if (isFetchingSnapshot) return;
        isFetchingSnapshot = true;
        try {
            const snapshot = await fetchSnapshot();
            if (snapshot) {
                updateState({ snapshot });
                lastUpdate = Date.now();
            }
        } finally {
            isFetchingSnapshot = false;
        }
    }, POLLING_INTERVALS.SNAPSHOT);
}

// Start the app
bootstrap();
