/**
 * api.js — Network layer for simulation and telemetry
 */

import { API_BASE } from './constants.js';

/**
 * Get API key from localStorage
 */
function getApiKey() {
    return localStorage.getItem('astrosis_api_key');
}

/**
 * Set API key in localStorage
 */
function setApiKey(key) {
    localStorage.setItem('astrosis_api_key', key);
}

/**
 * apiFetch — Common fetch wrapper with error handling
 */
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const apiKey = getApiKey();
    
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    
    if (apiKey) {
        headers['X-API-Key'] = apiKey;
    }
    
    try {
        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const errorBody = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorBody || response.statusText}`);
        }

        return await response.json();
    } catch (e) {
        console.error(`API Fetch Error [${url}]:`, e);
        throw e;
    }
}

export async function fetchSnapshot() {
    try {
        return await apiFetch('/visualization/snapshot');
    } catch (e) {
        return null;
    }
}

export async function stepSim(hours) {
    try {
        await apiFetch('/simulate/step', {
            method: 'POST',
            body: JSON.stringify({ step_seconds: hours * 3600 })
        });
        return true;
    } catch (e) {
        return false;
    }
}

export { setApiKey, getApiKey };
