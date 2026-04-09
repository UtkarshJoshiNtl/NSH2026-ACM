/**
 * events.js — Centralized event delegation and user interaction handlers
 */

import { updateState, state } from './state.js';
import { stepSim } from './api.js';
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
}
