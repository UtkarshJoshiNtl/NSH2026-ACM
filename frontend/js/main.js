/**
 * main.js — Application bootloader and orchestration loop
 */

import { state, updateState, onStateChange } from './state.js';
import { fetchSnapshot, fetchHistory } from './api.js';
import { initEvents, populateSatSelect } from './events.js';
import { setText } from './utils/dom.js';

// Renderers
import { updateHeader } from './renderers/header.js';
import { renderCdmList } from './renderers/cdm-list.js';
import { renderHistoryList } from './renderers/history-list.js';

// Components
import { initMap, renderMap } from './components/map.js';
import { initBullseye, renderBullseye } from './components/bullseye.js';
import { renderFuel } from './components/fuel-grid.js';
import { initGantt, renderGantt } from './components/gantt.js';

import { POLLING_INTERVALS } from './constants.js';

async function bootstrap() {
    console.log('ACM Orbit Insight initializing...');

    // Initialize component canvases
    initMap('map-canvas');
    initBullseye('bullseye-canvas');
    initGantt('gantt-canvas');

    // Initialize event listeners
    initEvents();

    // Set up reactive rendering
    onStateChange((s) => {
        updateHeader(s.snapshot);
        renderCdmList(s.snapshot?.active_cdms);
        renderHistoryList(s.history);

        renderMap(s.snapshot);
        renderBullseye(s.snapshot, s.selectedSat);
        renderFuel(s.snapshot?.satellites);
        renderGantt(s.snapshot?.pending_burns, s.snapshot?.timestamp);

        populateSatSelect(s.snapshot?.satellites);

        setText('sim-time', s.snapshot ? new Date(s.snapshot.timestamp * 1000).toISOString().replace('T', ' ').slice(0, 19) : '—');
        setText('h-deb-count', s.snapshot?.debris_cloud ? s.snapshot.debris_cloud.length : 0);
        setText('h-burn-count', s.snapshot?.pending_burns ? s.snapshot.pending_burns.length : 0);
        setText('status-text', s.status);
    });

    // Initial fetch
    const [snapshot, history] = await Promise.all([fetchSnapshot(), fetchHistory()]);
    updateState({
        snapshot,
        history,
        status: snapshot ? 'TELEMETRY LINK ACTIVE — LIVE' : 'OFFLINE (SERVER ERROR)'
    });

    // Polling loops with overlap protection
    let isFetchingSnapshot = false;
    setInterval(async () => {
        if (isFetchingSnapshot) return;
        isFetchingSnapshot = true;
        try {
            const snapshot = await fetchSnapshot();
            if (snapshot) updateState({ snapshot });
        } finally {
            isFetchingSnapshot = false;
        }
    }, POLLING_INTERVALS.SNAPSHOT);

    let isFetchingHistory = false;
    setInterval(async () => {
        if (isFetchingHistory) return;
        isFetchingHistory = true;
        try {
            const history = await fetchHistory();
            updateState({ history });
        } finally {
            isFetchingHistory = false;
        }
    }, POLLING_INTERVALS.HISTORY);
}

// Start the app
bootstrap();
