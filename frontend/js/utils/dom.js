/**
 * dom.js — Helper functions for DOM manipulation
 */

export function getEl(id) {
    return document.getElementById(id);
}

export function setHtml(id, html) {
    const el = getEl(id);
    if (el) el.innerHTML = html;
}

export function setText(id, text) {
    const el = getEl(id);
    if (el) el.textContent = text;
}

export function toggleClass(id, className, force) {
    const el = getEl(id);
    if (el) el.classList.toggle(className, force);
}
