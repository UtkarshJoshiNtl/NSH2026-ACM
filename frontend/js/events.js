/**
 * events.js — Centralized event delegation and user interaction handlers
 */

import { updateState, state } from './state.js';
import { stepSim, setApiKey, getApiKey } from './api.js';
import { getEl } from './utils/dom.js';

export function initEvents() {
    // ── API Key Modal ────────────────────────────────────────────────────────────
    const btnApiKey = getEl('btn-api-key');
    const modal = getEl('api-key-modal');
    const apiKeyInput = getEl('api-key-input');
    const btnSaveApiKey = getEl('btn-save-api-key');
    const btnCancelApiKey = getEl('btn-cancel-api-key');

    if (btnApiKey && modal) {
        btnApiKey.addEventListener('click', () => {
            apiKeyInput.value = getApiKey() || '';
            modal.classList.remove('hidden');
        });
    }

    if (btnSaveApiKey && modal) {
        btnSaveApiKey.addEventListener('click', () => {
            const key = apiKeyInput.value.trim();
            if (key) {
                setApiKey(key);
                updateState({ status: 'API KEY SAVED' });
            }
            modal.classList.add('hidden');
        });
    }

    if (btnCancelApiKey && modal) {
        btnCancelApiKey.addEventListener('click', () => {
            modal.classList.add('hidden');
        });
    }

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
