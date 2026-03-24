/**
 * events.js — Centralized event delegation and user interaction handlers
 */

import { updateState, state } from './state.js';
import { stepSim, runCola } from './api.js';
import { getEl } from './utils/dom.js';

export function initEvents() {
    // ── Tab Switching ─────────────────────────────────────────────────────────────
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const panel = btn.closest('.panel');
            const tabId = btn.dataset.tab;

            // Update buttons
            panel.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content visibility
            panel.querySelectorAll('.tab-content').forEach(c => {
                c.classList.toggle('active', c.id === `tab-${tabId}`);
            });
        });
    });

    // ── Satellite Selection ───────────────────────────────────────────────────────
    const satSelect = getEl('sat-select');
    if (satSelect) {
        satSelect.addEventListener('change', () => {
            updateState({ selectedSat: satSelect.value || null });
        });
    }

    // ── Simulation Controls ───────────────────────────────────────────────────────
    const btnStep = getEl('btn-step');
    if (btnStep) {
        btnStep.addEventListener('click', async () => {
            const ok = await stepSim(1);
            if (ok) updateState({ status: 'SIMULATION STEP +1H SUCCESS' });
        });
    }

    const btnStep10 = getEl('btn-step-10');
    if (btnStep10) {
        btnStep10.addEventListener('click', async () => {
            const ok = await stepSim(10);
            if (ok) updateState({ status: 'SIMULATION STEP +10H SUCCESS' });
        });
    }

    const btnCola = getEl('btn-cola');
    if (btnCola) {
        btnCola.addEventListener('click', async () => {
            updateState({ status: 'RUNNING COLA ALGORITHM...' });
            const ok = await runCola();
            if (ok) updateState({ status: 'COLA MANEUVERS PLANNED' });
        });
    }
}

export function populateSatSelect(satellites) {
    const satSelect = getEl('sat-select');
    if (!satSelect || !satellites) return;

    const current = satSelect.value;
    satSelect.innerHTML = '<option value="">— choose —</option>' +
        satellites.map(s => `<option value="${s.id}" ${s.id === current ? 'selected' : ''}>${s.id}</option>`).join('');
}
