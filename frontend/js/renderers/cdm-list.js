/**
 * cdm-list.js — Renderer for the CDM scrolling list
 */

import { getEl } from '../utils/dom.js';

export function renderCdmList(cdms) {
    const container = getEl('cdm-list');
    if (!container) return;

    if (!cdms || cdms.length === 0) {
        container.innerHTML = '<div class="empty-msg">NO ACTIVE CONJUNCTIONS — ALL CLEAR</div>';
        return;
    }

    container.innerHTML = cdms.map(cdm => `
        <div class="cdm-item ${cdm.severity}">
            <div class="cdm-header">
                <span class="cdm-sat">${cdm.sat_id.slice(-6)}</span>
                <span class="cdm-dist">${cdm.distance_km.toFixed(3)} km</span>
            </div>
            <div class="cdm-sub">Threat: ${cdm.debris_id.slice(-6)} | TCA: ${new Date(cdm.tca_s * 1000).toISOString().slice(11, 19)}</div>
        </div>
    `).join('');
}
