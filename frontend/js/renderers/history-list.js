/**
 * history-list.js — Renderer for the event history view
 */

import { getEl } from '../utils/dom.js';

export function renderHistoryList(history) {
    const container = getEl('history-list');
    if (!container) return;

    if (!history || history.length === 0) {
        container.innerHTML = '<div class="empty-msg">NO RECENT EVENTS — SIMULATION START</div>';
        return;
    }

    container.innerHTML = history.slice(0, 50).map(h => `
        <div class="hist-item ${h.type || ''}">
            <div class="hist-header">
                <span class="hist-sat">${h.satellite_id.slice(-6)}</span>
                <span class="hist-fuel">-${h.fuel_spent_kg?.toFixed(2) || '0.00'} kg</span>
            </div>
            <div class="hist-sub">${h.message || h.type} @ ${new Date(h.timestamp * 1000).toISOString().slice(11, 19)}</div>
        </div>
    `).join('');
}
