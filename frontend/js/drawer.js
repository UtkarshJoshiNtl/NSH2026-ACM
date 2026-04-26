/* =============================================================================
   SATELLITE DETAIL DRAWER — frontend/js/drawer.js
   Full-telemetry slide-in panel for selected satellite.
   ============================================================================= */

(function () {
  'use strict';

  const Drawer = window.Drawer = {};

  let _currentSat = null;

  // ── Init ───────────────────────────────────────────────────────────────────
  Drawer.init = function () {
    const close = document.getElementById('drawer-close');
    if (close) close.addEventListener('click', Drawer.close);

    // Close on outside click (overlay is behind drawer)
    document.getElementById('drawer-overlay')?.addEventListener('click', Drawer.close);

    // Keyboard escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') Drawer.close();
    });
  };

  // ── Open with satellite data ───────────────────────────────────────────────
  Drawer.open = function (sat, cdms, maneuvers) {
    _currentSat = sat;
    _render(sat, cdms || [], maneuvers || []);

    const drawer  = document.getElementById('sat-drawer');
    const overlay = document.getElementById('drawer-overlay');
    if (!drawer) return;

    drawer.classList.add('open');
    if (overlay) overlay.classList.add('visible');

    if (window.gsap) {
      gsap.fromTo(drawer,
        { x: 420, opacity: 0 },
        { x: 0,   opacity: 1, duration: 0.45, ease: 'power3.out' }
      );
    }
  };

  Drawer.close = function () {
    const drawer  = document.getElementById('sat-drawer');
    const overlay = document.getElementById('drawer-overlay');
    if (!drawer) return;

    if (window.gsap) {
      gsap.to(drawer, {
        x: 420, opacity: 0, duration: 0.3, ease: 'power2.in',
        onComplete: () => {
          drawer.classList.remove('open');
          if (overlay) overlay.classList.remove('visible');
        }
      });
    } else {
      drawer.classList.remove('open');
      if (overlay) overlay.classList.remove('visible');
    }
    _currentSat = null;
  };

  // ── Update live data while open ────────────────────────────────────────────
  Drawer.update = function (satellites, cdms, maneuvers) {
    if (!_currentSat) return;
    const sat = satellites.find(s => s.id === _currentSat.id);
    if (sat) { _currentSat = sat; _render(sat, cdms, maneuvers); }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  function _render(sat, cdms, maneuvers) {
    const body = document.getElementById('drawer-body');
    if (!body) return;

    const fuelPct    = ((sat.fuel_kg || sat.fuelKg || 0) / 50 * 100).toFixed(1);
    const fuel_kg    = (sat.fuel_kg || sat.fuelKg || 0).toFixed(2);
    const statusClass = {
      NOMINAL:    'badge-nominal',
      EVADING:    'badge-evading',
      RECOVERING: 'badge-recovering',
      EOL:        'badge-eol',
    }[sat.status] || 'badge-nominal';

    const satCDMs = cdms.filter(c => c.satelliteId === sat.id);
    const satBurns = maneuvers.filter(m =>
      m.satelliteId === sat.id && m.status === 'PENDING'
    ).slice(0, 5);

    const fuelColor = fuelPct > 60 ? 'var(--green)' : fuelPct > 30 ? 'var(--amber)' : 'var(--red)';

    body.innerHTML = `
      <!-- Header -->
      <div class="drawer-sat-id">${sat.id}</div>
      <div class="drawer-badge-row">
        <span class="orbital-badge ${statusClass}">${sat.status}</span>
        ${sat.status === 'EVADING' ? '<span class="drawer-pulse-badge">ACTIVE MANEUVER</span>' : ''}
      </div>

      <!-- Orbital State -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <i data-lucide="map-pin"></i> ORBITAL POSITION
        </div>
        <div class="drawer-grid-2">
          <div class="drawer-kv"><span class="label">LAT</span><span class="value">${(sat.lat || 0).toFixed(3)}°</span></div>
          <div class="drawer-kv"><span class="label">LON</span><span class="value">${(sat.lon || 0).toFixed(3)}°</span></div>
        </div>
      </div>

      <!-- Fuel -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <i data-lucide="fuel"></i> PROPELLANT
        </div>
        <div class="drawer-fuel-bar-wrap">
          <div class="drawer-fuel-bar" style="width: ${Math.max(0, Math.min(100, fuelPct))}%; background: ${fuelColor}"></div>
        </div>
        <div class="drawer-grid-2" style="margin-top:6px">
          <div class="drawer-kv"><span class="label">REMAINING</span><span class="value" style="color:${fuelColor}">${fuel_kg} kg</span></div>
          <div class="drawer-kv"><span class="label">FRACTION</span><span class="value" style="color:${fuelColor}">${fuelPct}%</span></div>
        </div>
      </div>

      <!-- Active CDMs -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <i data-lucide="alert-triangle"></i> CONJUNCTION WARNINGS
        </div>
        ${satCDMs.length === 0
          ? '<div class="drawer-empty">No active CDMs</div>'
          : satCDMs.map(c => {
              const dist_m = (c.missDistance * 1000).toFixed(0);
              const severity = c.missDistance < 0.1 ? 'badge-eol' : c.missDistance < 1 ? 'badge-evading' : 'badge-recovering';
              return `
                <div class="drawer-cdm-row">
                  <span class="orbital-badge ${severity}">${dist_m} m</span>
                  <span class="drawer-cdm-id">${c.debrisId}</span>
                  <span class="drawer-cdm-prob">${(c.probability * 100).toFixed(3)}%</span>
                </div>`;
            }).join('')
        }
      </div>

      <!-- Scheduled Maneuvers -->
      <div class="drawer-section">
        <div class="drawer-section-title">
          <i data-lucide="calendar-clock"></i> QUEUED BURNS
        </div>
        ${satBurns.length === 0
          ? '<div class="drawer-empty">No pending burns</div>'
          : satBurns.map(b => {
              const type = b.burnId.includes('AUTO_EVA_') ? '⬛ EVA' :
                           b.burnId.includes('AUTO_REC_') ? '🔵 REC' :
                           b.burnId.includes('AUTO_EOL_') ? '⚫ EOL' : '🟡 MAN';
              const t = b.burnTime ? new Date(b.burnTime).toISOString().slice(11,19) : '—';
              return `<div class="drawer-burn-row">
                <span class="drawer-burn-type">${type}</span>
                <span class="drawer-burn-id">${b.burnId.slice(-12)}</span>
                <span class="drawer-burn-time">${t}Z</span>
              </div>`;
            }).join('')
        }
      </div>

      <!-- Actions -->
      <div class="drawer-section">
        <div class="drawer-section-title"><i data-lucide="rocket"></i> ACTIONS</div>
        <div class="drawer-actions">
          <button class="drawer-action-btn" onclick="Globe.flyToSatelliteById('${sat.id}')">
            <i data-lucide="crosshair"></i> Track Camera
          </button>
          <button class="drawer-action-btn" onclick="AppState.selectSatellite('${sat.id}')">
            <i data-lucide="radar"></i> Focus Bullseye
          </button>
        </div>
      </div>
    `;

    // Re-init Lucide icons in the drawer
    if (window.lucide) lucide.createIcons({ nodes: [body] });
  }

})();
