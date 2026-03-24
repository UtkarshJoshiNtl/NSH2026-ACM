/**
 * state.js — Centralized application state management
 */

export const state = {
    snapshot: null,
    history: [],
    selectedSat: null,
    status: 'SYSTEM OFFLINE',
};

// Simple event-based state update mechanism
const listeners = [];

export function onStateChange(callback) {
    listeners.push(callback);
}

export function updateState(newState) {
    Object.assign(state, newState);
    listeners.forEach(cb => cb(state));
}
