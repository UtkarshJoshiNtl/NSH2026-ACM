/**
 * fuel-grid.js — Fuel gauge heatmap for all satellites
 */

import { getEl } from '../utils/dom.js';
import { INITIAL_FUEL } from '../constants.js';

export function renderFuel(satellites) {
    const container = getEl('fuel-list');
    if (!container) return;

    container.innerHTML = '';

    const sorted = [...(satellites || [])].sort((a, b) => a.fuel_kg - b.fuel_kg);

    sorted.forEach(sat => {
        const pct = Math.max(0, Math.min(100, (sat.fuel_kg / INITIAL_FUEL) * 100));
        const color = pct > 30 ? '#3fb950'
            : pct > 10 ? '#e3b341'
                : '#f85149';

        const row = document.createElement('div');
        row.className = 'fuel-row';
        row.innerHTML = `
            <span class="fuel-id" title="${sat.id}">${sat.id.slice(-6)}</span>
            <div class="fuel-bar-bg">
                <div class="fuel-bar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div>
            </div>
            <span class="fuel-val" style="color:${color}">${sat.fuel_kg.toFixed(1)}kg</span>
        `;
        container.appendChild(row);
    });
}
