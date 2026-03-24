/**
 * api.js — Network layer for simulation and telemetry
 */

import { API_BASE } from './constants.js';

export async function fetchSnapshot() {
    try {
        const r = await fetch(`${API_BASE}/simulate/snapshot`);
        return await r.json();
    } catch (e) {
        console.error('Snapshot fetch failed:', e);
        return null;
    }
}

export async function fetchHistory() {
    try {
        const r = await fetch(`${API_BASE}/history`);
        return await r.json();
    } catch (e) {
        console.error('History fetch failed:', e);
        return [];
    }
}

export async function stepSim(hours) {
    try {
        const r = await fetch(`${API_BASE}/simulate/step?hours=${hours}`, { method: 'POST' });
        return r.ok;
    } catch (e) {
        console.error('Sim step failed:', e);
        return false;
    }
}

export async function runCola() {
    try {
        const r = await fetch(`${API_BASE}/simulate/cola`, { method: 'POST' });
        return r.ok;
    } catch (e) {
        console.error('COLA run failed:', e);
        return false;
    }
}
