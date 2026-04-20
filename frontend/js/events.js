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

    // ── Auth Modal ───────────────────────────────────────────────────────────────
    const authModal = getEl('auth-modal');
    const tabSignin = getEl('tab-signin');
    const tabSignup = getEl('tab-signup');
    const signinForm = getEl('signin-form');
    const signupForm = getEl('signup-form');
    const authModalTitle = getEl('auth-modal-title');
    const btnAuthSubmit = getEl('btn-auth-submit');
    const btnAuthCancel = getEl('btn-auth-cancel');
    const authError = getEl('auth-error');

    // Add auth button to header
    const headerControls = document.querySelector('.header-controls');
    if (headerControls) {
        const btnAuth = document.createElement('button');
        btnAuth.id = 'btn-auth';
        btnAuth.className = 'ctrl-btn';
        btnAuth.textContent = '👤 Sign In';
        btnAuth.addEventListener('click', () => {
            authModal.classList.remove('hidden');
        });
        headerControls.insertBefore(btnAuth, headerControls.firstChild);
    }

    if (tabSignin && tabSignup) {
        tabSignin.addEventListener('click', () => {
            tabSignin.classList.add('active');
            tabSignup.classList.remove('active');
            signinForm.classList.remove('hidden');
            signupForm.classList.add('hidden');
            authModalTitle.textContent = 'Sign In';
            btnAuthSubmit.textContent = 'Sign In';
            authError.classList.add('hidden');
        });

        tabSignup.addEventListener('click', () => {
            tabSignup.classList.add('active');
            tabSignin.classList.remove('active');
            signupForm.classList.remove('hidden');
            signinForm.classList.add('hidden');
            authModalTitle.textContent = 'Register';
            btnAuthSubmit.textContent = 'Register';
            authError.classList.add('hidden');
        });
    }

    if (btnAuthSubmit) {
        btnAuthSubmit.addEventListener('click', async () => {
            const isSignin = tabSignin.classList.contains('active');
            
            try {
                if (isSignin) {
                    // Sign in
                    const email = getEl('signin-email').value;
                    const password = getEl('signin-password').value;
                    
                    const response = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        setApiKey(data.access_token);
                        authModal.classList.add('hidden');
                        updateState({ status: 'SIGNED IN' });
                        btnAuth.textContent = '👤 Signed In';
                    } else {
                        throw new Error('Invalid credentials');
                    }
                } else {
                    // Register
                    const email = getEl('signup-email').value;
                    const password = getEl('signup-password').value;
                    const confirmPassword = getEl('signup-confirm-password').value;
                    
                    if (password !== confirmPassword) {
                        throw new Error('Passwords do not match');
                    }
                    
                    const response = await fetch('/api/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });
                    
                    if (response.ok) {
                        // Switch to sign in tab
                        tabSignin.click();
                        updateState({ status: 'REGISTRATION SUCCESSFUL - PLEASE SIGN IN' });
                    } else {
                        throw new Error('Registration failed');
                    }
                }
            } catch (e) {
                authError.textContent = e.message;
                authError.classList.remove('hidden');
            }
        });
    }

    if (btnAuthCancel) {
        btnAuthCancel.addEventListener('click', () => {
            authModal.classList.add('hidden');
            authError.classList.add('hidden');
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
