/**
 * gantt.js — Maneuver timeline showing pending burns relative to sim time
 */

import { getEl } from '../utils/dom.js';

let ganttCanvas, gCtx;

const WINDOW_S = 7200; // show ±2h
const BURN_TYPE_COLORS = {
    EVASION: '#f85149',
    RECOVERY: '#58a6ff',
    GRAVEYARD: '#e3b341',
    STATION_KEEP: '#3fb950',
    DEFAULT: '#8b949e',
};

export function initGantt(canvasId) {
    ganttCanvas = getEl(canvasId);
    if (!ganttCanvas) return;
    gCtx = ganttCanvas.getContext('2d');
}

let frameRequested = false;
let lastArgs = null;

export function renderGantt(pendingBurns, simTime) {
    if (!ganttCanvas || !gCtx) return;
    lastArgs = { pendingBurns, simTime };

    if (frameRequested) return;
    frameRequested = true;

    requestAnimationFrame(() => {
        _drawGantt(lastArgs.pendingBurns, lastArgs.simTime);
        frameRequested = false;
    });
}

function _drawGantt(pendingBurns, simTime) {
    const W = ganttCanvas.width = ganttCanvas.clientWidth;
    const H = ganttCanvas.height = ganttCanvas.clientHeight;

    gCtx.fillStyle = '#050b14';
    gCtx.fillRect(0, 0, W, H);

    if (!pendingBurns || pendingBurns.length === 0) {
        gCtx.fillStyle = '#6e7f94'; gCtx.font = '10px JetBrains Mono';
        gCtx.fillText('NO MANEUVERS SCHEDULED', 20, H / 2 + 4);
        return;
    }

    const tickIntervals = [600, 1800, 3600];
    const tickSec = tickIntervals.find(t => WINDOW_S / t <= 12) || 3600;
    const timeToX = t => ((t - simTime) / WINDOW_S + 0.5) * W;

    gCtx.strokeStyle = '#1e2730'; gCtx.lineWidth = 1;
    for (let t = simTime - WINDOW_S / 2; t <= simTime + WINDOW_S / 2; t += tickSec) {
        const x = timeToX(t);
        gCtx.beginPath(); gCtx.moveTo(x, 0); gCtx.lineTo(x, H); gCtx.stroke();
        const label = new Date(t * 1000).toISOString().slice(11, 16);
        gCtx.fillStyle = '#3a4a5a'; gCtx.font = '8px JetBrains Mono';
        gCtx.fillText(label, x + 2, H - 2);
    }

    const nowX = timeToX(simTime);
    gCtx.strokeStyle = '#f0a500'; gCtx.lineWidth = 1.5;
    gCtx.setLineDash([4, 3]);
    gCtx.beginPath(); gCtx.moveTo(nowX, 0); gCtx.lineTo(nowX, H - 12); gCtx.stroke();
    gCtx.setLineDash([]);
    gCtx.fillStyle = '#f0a500'; gCtx.font = '8px JetBrains Mono';
    gCtx.fillText('NOW', nowX + 3, 10);

    const satRows = {};
    pendingBurns.forEach(b => {
        if (!(b.satellite_id in satRows)) satRows[b.satellite_id] = Object.keys(satRows).length;
    });

    const rowH = Math.min(22, (H - 20) / Math.max(Object.keys(satRows).length, 1));

    pendingBurns.forEach(burn => {
        const x = timeToX(burn.burn_time);
        const row = satRows[burn.satellite_id];
        const y = 2 + row * rowH;
        const color = BURN_TYPE_COLORS[burn.burn_type] || BURN_TYPE_COLORS.DEFAULT;

        gCtx.fillStyle = color;
        gCtx.fillRect(x - 1, y, 12, rowH - 3);

        const cooldownW = (600 / WINDOW_S) * W;
        gCtx.fillStyle = color + '33';
        gCtx.fillRect(x + 11, y, cooldownW, rowH - 3);

        gCtx.fillStyle = '#cdd9e5'; gCtx.font = '7px JetBrains Mono';
        gCtx.fillText(burn.satellite_id.slice(-5) + ' ' + (burn.burn_type || '').slice(0, 4), x + 14, y + rowH - 6);
    });
}
