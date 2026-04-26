/* =============================================================================
   MISSION ALERTS FEED — frontend/js/alerts.js
   Live mission event log with severity badges and toast notifications.
   ============================================================================= */

(function () {
  'use strict';

  const Alerts = window.Alerts = {};

  let _latestId   = 0;
  let _pollTimer  = null;
  const POLL_MS   = 3000;

  // ── Init ───────────────────────────────────────────────────────────────────
  Alerts.init = function () {
    _startPolling();
  };

  // ── Polling ────────────────────────────────────────────────────────────────
  function _startPolling() {
    _poll();
    _pollTimer = setInterval(_poll, POLL_MS);
  }

  async function _poll() {
    try {
      const data = await API.fetchAlerts(_latestId);
      if (!data || !data.alerts || data.alerts.length === 0) return;

      _latestId = data.latest_id;
      _renderAlerts(data.alerts);

      // Toast for CRITICAL alerts
      data.alerts
        .filter(a => a.severity === 'CRITICAL')
        .slice(0, 2)  // max 2 toasts at once
        .forEach(a => _showToast(a));

    } catch (_) {}
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  function _renderAlerts(alerts) {
    const list = document.getElementById('alert-list');
    const miniList = document.getElementById('alert-list-mini');
    
    if (!list && !miniList) return;

    alerts.forEach(alert => {
      // Render to main list
      if (list) {
        _renderAlertToList(list, alert, false);
      }
      
      // Render to mini list (projection mode)
      if (miniList) {
        _renderAlertToList(miniList, alert, true);
      }
    });

    // Trim old entries beyond 100
    if (list && list.children.length > 100) {
      while (list.children.length > 100) {
        list.removeChild(list.lastChild);
      }
    }
    
    // Trim mini list to 10 entries
    if (miniList && miniList.children.length > 10) {
      while (miniList.children.length > 10) {
        miniList.removeChild(miniList.lastChild);
      }
    }
  }
  
  function _renderAlertToList(list, alert, isMini) {
    const el = document.createElement('div');
    el.className = `alert-item alert-${alert.severity.toLowerCase()}`;
    el.dataset.id = alert.id;

    const time = new Date(alert.timestamp).toISOString().slice(11, 19);
    el.innerHTML = `
      <span class="alert-badge badge-${alert.severity.toLowerCase()}">${alert.severity[0]}</span>
      <span class="alert-msg">${alert.message}</span>
      <span class="alert-time">${time}Z</span>
    `;

    // Prepend newest on top with animation
    list.insertBefore(el, list.firstChild);
    if (window.gsap && !isMini) {
      gsap.from(el, { x: -20, opacity: 0, duration: 0.3, ease: 'power2.out' });
    }
  }

  // ── Toast Notifications ────────────────────────────────────────────────────
  function _showToast(alert) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${alert.severity.toLowerCase()}`;
    toast.innerHTML = `
      <div class="toast-icon">⚠</div>
      <div class="toast-body">
        <div class="toast-title">${alert.severity}</div>
        <div class="toast-msg">${alert.message}</div>
      </div>
      <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;
    container.appendChild(toast);

    if (window.gsap) {
      gsap.from(toast, { x: 120, opacity: 0, duration: 0.4, ease: 'back.out(1.5)' });
    }

    // Auto-dismiss after 6 seconds
    setTimeout(() => {
      if (!toast.parentElement) return;
      if (window.gsap) {
        gsap.to(toast, {
          x: 120, opacity: 0, duration: 0.3,
          onComplete: () => toast.remove()
        });
      } else {
        toast.remove();
      }
    }, 6000);
  }

  Alerts.stop = function () {
    clearInterval(_pollTimer);
  };

})();
