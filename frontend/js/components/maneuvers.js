/**
 * maneuvers.js — Maneuver Queue Renderer
=========================================
Renders the queue of scheduled maneuvers.
*/

import { getEl } from '../utils/dom.js';

export function renderManeuvers(maneuvers) {
    const container = getEl('maneuver-list');
    const countBadge = getEl('maneuver-count');
    
    if (!container || !countBadge) return;
    
    // Update count badge
    countBadge.textContent = `${maneuvers.length} pending`;
    
    // Clear container
    container.innerHTML = '';
    
    if (maneuvers.length === 0) {
        container.innerHTML = '<div class="empty-state">No pending maneuvers</div>';
        return;
    }
    
    // Render each maneuver
    maneuvers.forEach(maneuver => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `
            <div class="item-header">
                <span class="item-title">${maneuver.satellite_id}</span>
                <span class="item-badge badge-${maneuver.burn_type === 'evasion' ? 'red' : 'blue'}">${maneuver.burn_type}</span>
            </div>
            <div class="item-details">
                <span class="item-detail">ID: ${maneuver.burn_id}</span>
                <span class="item-detail">T+${Math.round(maneuver.burn_time)}s</span>
            </div>
        `;
        container.appendChild(item);
    });
}
