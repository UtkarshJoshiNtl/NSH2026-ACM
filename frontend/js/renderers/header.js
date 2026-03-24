/**
 * header.js — Renderer for top-bar statistics
 */

import { setText, toggleClass } from '../utils/dom.js';

export function updateHeader(data) {
    if (!data) return;

    setText('h-sat-count', data.satellites ? data.satellites.length : 0);

    const activeCdms = data.active_cdms || [];
    const criticalCount = activeCdms.filter(c => c.severity === 'CRITICAL').length;
    const warningCount = activeCdms.filter(c => c.severity === 'WARNING').length;

    setText('h-cdm-count', criticalCount + warningCount); // Total CDMs for summary

    toggleClass('h-cdm-count', 'danger', criticalCount > 0);
}
