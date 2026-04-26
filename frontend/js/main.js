/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — Main Application Entry Point
   Glassmorphism Edition: Particles, GSAP Choreography, Split.js Resize
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  const SNAPSHOT_INTERVAL = 5000;
  const STATS_INTERVAL    = 10000;
  const CLOCK_INTERVAL    = 2000;

  let simTimestamp = new Date().toISOString();
  let cdmCache = [];
  let maneuverCache = [];
  let prevStatValues = [];

  // ══════════════════════════════════════════════════════════════════════════
  // INIT
  // ══════════════════════════════════════════════════════════════════════════
  document.addEventListener('DOMContentLoaded', () => {
    // Init Lucide icons
    if (window.lucide) lucide.createIcons();

    // Setup resizable panels with Split.js
    initSplitPanels();

// Particle field removed for performance

    // ── View Toggle Logic ───────────────────────────────────────────────────────
  const modeProjectionBtn = document.getElementById('mode-projection');
  const modeChartsBtn = document.getElementById('mode-charts');
  const projectionView = document.getElementById('projection-view');
  const chartsView = document.getElementById('charts-view');

  modeProjectionBtn?.addEventListener('click', () => {
    modeProjectionBtn.classList.add('active');
    modeChartsBtn.classList.remove('active');
    projectionView.classList.add('active');
    chartsView.classList.remove('active');
  });

  modeChartsBtn?.addEventListener('click', () => {
    modeChartsBtn.classList.add('active');
    modeProjectionBtn.classList.remove('active');
    chartsView.classList.add('active');
    projectionView.classList.remove('active');
  });

  // ── 3D/2D Toggle Logic - DISABLED for performance ─────────────────────────────

  // Init all modules
  setTimeout(() => {
    GroundTrack.init();
    FuelPanel.init();
    Bullseye.init();
    Gantt.init();
    Telemetry.init();
    SpeedControl.init();
    Alerts.init();
    Drawer.init();
    ViewMode.init();

    // Wire up events
    setupEventListeners();

    // Start Telemetry (WebSocket preferred, with polling fallback)
    if (typeof WSTelemetry !== 'undefined') {
      WSTelemetry.onSnapshot((data) => {
        handleDataUpdate(data, 10); // Simulated ping for WS
      });
      WSTelemetry.connect();
    }
    
    // Always poll as fallback to ensure constant updates
    pollSnapshot();
    
    // Use aggressive polling to ensure updates don't stop
    setInterval(() => {
      pollSnapshot().catch(e => console.error('[Poll] Error:', e));
    }, SNAPSHOT_INTERVAL);

    // Force initial data load with retry to ensure sim shows up
    let initialLoadAttempts = 0;
    const MAX_INITIAL_ATTEMPTS = 15;
    async function forceInitialLoad() {
      try {
        const data = await API.fetchSnapshot();
        if (data && data.satellites && data.satellites.length > 0) {
          handleDataUpdate(data, 10);
          console.log('[Init] Initial data loaded successfully');
        } else if (initialLoadAttempts < MAX_INITIAL_ATTEMPTS) {
          initialLoadAttempts++;
          console.log(`[Init] Retrying initial load (${initialLoadAttempts}/${MAX_INITIAL_ATTEMPTS})...`);
          setTimeout(forceInitialLoad, 1000);
        } else {
          console.error('[Init] All retry attempts failed to load initial data');
        }
      } catch (e) {
        if (initialLoadAttempts < MAX_INITIAL_ATTEMPTS) {
          initialLoadAttempts++;
          console.log(`[Init] Initial load failed, retrying (${initialLoadAttempts}/${MAX_INITIAL_ATTEMPTS})...`);
          setTimeout(forceInitialLoad, 1000);
        } else {
          console.error('[Init] All retry attempts failed. Please ensure the backend is running and seeded.');
        }
      }
    }
    forceInitialLoad();

    // Real ΔV stats polling (uses /api/constellation/stats)
    pollConstellationStats();
    setInterval(pollConstellationStats, STATS_INTERVAL);

    // Sim clock
    setInterval(updateSimClock, CLOCK_INTERVAL);

    // GSAP Entrance Choreography
    playEntranceSequence();

    // Sim-step event fires when SpeedControl does a manual step
    document.addEventListener('sim-step', () => {
      pollSnapshot();
      pollConstellationStats();
    });

    // Resize handler
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(handleResize, 200);
    });

    // Close context menu
    document.addEventListener('click', () => {
      if (typeof Globe !== 'undefined') Globe.hideContextMenu();
    });
  }, 100);
  }); // End DOMContentLoaded

  // ══════════════════════════════════════════════════════════════════════════
  // SPLIT.JS — Resizable Panels
  // ══════════════════════════════════════════════════════════════════════════
  function initSplitPanels() {
    // Check if Split.js is available
    if (typeof Split === 'undefined') {
      console.warn('[Split] Split.js not loaded');
      return;
    }

    // Check if charts view elements exist before initializing
    const row1 = document.getElementById('chart-row-1');
    const row2 = document.getElementById('chart-row-2');
    
    if (row1 && row2) {
      // Top-level vertical split linking the two rows
      Split(['#chart-row-1', '#chart-row-2'], {
        direction: 'vertical',
        sizes: [50, 50],
        minSize: 100,
        gutterSize: 4,
        onDragEnd: handleResize
      });
    }

    // Horizontal split for row 1
    const bullseyePanel = document.getElementById('bullseye-panel');
    const fuelPanel = document.getElementById('fuel-panel');
    if (bullseyePanel && fuelPanel) {
      Split(['#bullseye-panel', '#fuel-panel'], {
        direction: 'horizontal',
        sizes: [50, 50],
        minSize: 150,
        gutterSize: 4,
        onDragEnd: handleResize
      });
    }

    // Horizontal split for row 2
    const ganttPanel = document.getElementById('gantt-panel');
    const telemetryPanel = document.getElementById('telemetry-panel');
    if (ganttPanel && telemetryPanel) {
      Split(['#gantt-panel', '#telemetry-panel'], {
        direction: 'horizontal',
        sizes: [50, 50],
        minSize: 150,
        gutterSize: 4,
        onDragEnd: handleResize
      });
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // ENTRANCE — Quick fade-in (no heavy choreography)
  // ══════════════════════════════════════════════════════════════════════════
  function playEntranceSequence() {
    // Simple fast fade — everything visible immediately
    if (!window.gsap) return;
    gsap.from('#app', { opacity: 0, duration: 0.5, ease: 'power2.out' });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PARTICLE STAR FIELD — Disabled for Mission Control aesthetics
  // ══════════════════════════════════════════════════════════════════════════
  function initParticleField() {}

  // ══════════════════════════════════════════════════════════════════════════
  // RESIZE HANDLER
  // ══════════════════════════════════════════════════════════════════════════
  function handleResize() {
    Bullseye.resize();
    Gantt.resize();
    if (cdmCache.length) {
      Globe.resize();
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CONSTELLATION STATS POLLING (Real ΔV data)
  // ══════════════════════════════════════════════════════════════════════════
  async function pollConstellationStats() {
    try {
      const stats = await API.fetchConstellationStats();
      if (!stats) {
        return;
      }

      // Real data from /api/constellation/stats
      const realDvMs = stats.maneuvers?.total_dv_ms || 0;
      AppState.addDvDataPoint(realDvMs);
      Telemetry.updateDvChart(AppState.state.dvHistory);

      const totalEl = document.getElementById('dv-total');
      if (totalEl) totalEl.textContent = realDvMs.toFixed(2) + ' m/s';

      // Also update alert count from stats
      const alertEl = document.getElementById('stat-alerts');
      if (alertEl && stats.conjunctions) {
        animateStat('stat-alerts', stats.conjunctions.total_raised);
      }

      if (stats.engine) {
        const engineEl = document.getElementById('health-physics');
        if (engineEl) {
           engineEl.textContent = stats.engine.engine_type === 'cpp' ? 'CPP_O3' : 'MOCK_PY';
           engineEl.className = stats.engine.engine_type === 'cpp' ? 'value text-green' : 'value text-amber';
        }

        const ingestionEl = document.getElementById('health-ingestion');
        if (ingestionEl) ingestionEl.textContent = (stats.engine.wrapper_avg_ms || 0).toFixed(1) + ' ms/cyc';
      }
    } catch (e) {
      console.warn('[Stats] Failed to poll constellation stats:', e.message);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // POLLING — Snapshot (Fallback)
  // ══════════════════════════════════════════════════════════════════════════
  async function pollSnapshot() {
    const start = performance.now();
    try {
      console.log('[Poll] Fetching snapshot...');
      const data = await API.fetchSnapshot();
      if (!data) {
        console.warn('[Poll] No data received');
        return;
      }
      const latency = performance.now() - start;
      handleDataUpdate(data, latency);
    } catch (e) {
      console.error('[Poll] Snapshot error:', e);
    }
  }

  function handleDataUpdate(data, latency) {
    if (!data) return;

    console.log('[Data Update] Received data at:', data.timestamp, 'with', data.satellites?.length, 'satellites');

    AppState.setApiLatency(latency);
    simTimestamp = data.timestamp;
    cdmCache = data.cdms || [];
    maneuverCache = data.maneuvers || [];

    AppState.updateSnapshot(data);
    AppState.updateCDMs(cdmCache);
    AppState.updateManeuvers(maneuverCache);

    if (typeof Globe !== 'undefined') {
      Globe.updateSatellites(data.satellites);
      Globe.updateDebris(data.debris_cloud);
      Globe.updateConjunctions(cdmCache);
    }
    if (typeof GroundTrack !== 'undefined') {
      GroundTrack.update(data.satellites, data.timestamp);
      GroundTrack.updateDebris(data.debris_cloud);
    }
    
    if (typeof FuelPanel !== 'undefined') FuelPanel.update(data.satellites);
    if (typeof Bullseye !== 'undefined' && Bullseye.setSatellitePositions) {
      Bullseye.setSatellitePositions(data.satellites);
    }
    updateTopbarStats(data);
    
    if (typeof Bullseye !== 'undefined') Bullseye.update(cdmCache, simTimestamp);
    if (typeof Gantt !== 'undefined') Gantt.update(maneuverCache, simTimestamp);
    
    if (typeof Telemetry !== 'undefined') {
      Telemetry.updateHealth(latency, data.timestamp);
      Telemetry.updateCDMList(cdmCache, simTimestamp);
      Telemetry.updateFullMetrics(data.satellites, cdmCache, maneuverCache);
    }

    // Engine status is now updated during pollConstellationStats

    // Update critical CDM count organically
    const criticalCount = cdmCache.filter(c => c.missDistance < 0.1).length;
    const cdmEl = document.getElementById('stat-cdms');
    if (cdmEl) {
      cdmEl.textContent = criticalCount;
      cdmEl.parentElement.classList.toggle('pulse-critical', criticalCount > 0);
    }

    // Auto-select most threatened satellite
    if (!AppState.state.selectedSatelliteId && data.satellites.length > 0) {
      const evading = data.satellites.find(s => s.status === 'EVADING');
      AppState.selectSatellite((evading || data.satellites[0]).id);
    }

    // Live-update the drawer if open
    if (typeof Drawer !== 'undefined') {
      Drawer.update(data.satellites, cdmCache, maneuverCache);
    }

    // Data flash animation on panels
    // Disabled for performance
  }

  // ══════════════════════════════════════════════════════════════════════════
  // DATA FLASH — Visual feedback when panels update
  // ══════════════════════════════════════════════════════════════════════════
  function flashPanels() {
    // Disabled for performance - data-flash animation removed
  }

  // ══════════════════════════════════════════════════════════════════════════
  // TOPBAR STATS (with animated number transitions)
  // ══════════════════════════════════════════════════════════════════════════
  function updateTopbarStats(data) {
    const sats = data.satellites || [];

    const activeSats = sats.filter(s => s.status !== 'EOL').length;
    animateStat('stat-sats', activeSats);

    animateStat('stat-debris', (data.debris_cloud || []).length, true);

    // Remove fleet uptime - not meaningful for demo
    const uptimeEl = document.getElementById('stat-uptime');
    if (uptimeEl) {
      uptimeEl.parentElement.style.display = 'none';
    }
  }

  function animateStat(id, newValue, formatNum = false) {
    const el = document.getElementById(id);
    if (!el) return;
    const displayValue = formatNum ? newValue.toLocaleString() : String(newValue);
    const prevValue = prevStatValues[id];

    if (prevValue !== displayValue) {
      prevStatValues[id] = displayValue;
      el.textContent = displayValue;

      // GSAP number pop animation
      if (window.gsap) {
        gsap.fromTo(el,
          { scale: 1.3, color: '#fff' },
          { scale: 1, color: el.style.color || '#4a9eff', duration: 0.4, ease: 'back.out(2)' }
        );
      }
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SIM CLOCK WITH TYPING EFFECT
  // ══════════════════════════════════════════════════════════════════════════
  function updateSimClock() {
    const clockEl = document.getElementById('sim-clock');
    if (!clockEl || !simTimestamp) return;
    const t = new Date(simTimestamp);
    clockEl.textContent = `SIM ${t.toISOString().replace('T', ' ').slice(0, 19)}Z`;
  }

  // ══════════════════════════════════════════════════════════════════════════
  // EVENT LISTENERS
  // ══════════════════════════════════════════════════════════════════════════
  function setupEventListeners() {
    AppState.on('satellite-selected', (satId) => {
      const satIdEl = document.getElementById('bullseye-sat-id');
      if (satIdEl) {
        satIdEl.textContent = satId;
        if (window.gsap) {
          gsap.from(satIdEl, { x: 20, opacity: 0, duration: 0.3, ease: 'power2.out' });
        }
      }

      const satCDMs = AppState.getCDMsForSatellite(satId);
      Bullseye.update(satCDMs.length > 0 ? satCDMs : cdmCache, simTimestamp);
      FuelPanel.update(AppState.state.satellites);
    });

    document.querySelectorAll('.context-menu-item').forEach(item => {
      item.addEventListener('click', (e) => {
        const action = e.currentTarget.dataset.action;
        const menu = document.getElementById('context-menu');
        const sat = menu?._targetSat;
        if (!sat) return;

        switch (action) {
          case 'track-camera':   Globe.flyToSatelliteById(sat.id); break;
          case 'view-telemetry': AppState.selectSatellite(sat.id); break;
          case 'open-drawer': {
            const satCDMs = AppState.getCDMsForSatellite(sat.id);
            Drawer.open(sat, satCDMs, maneuverCache);
            break;
          }
          case 'schedule-maneuver': console.log('[Action] Schedule maneuver:', sat.id); break;
        }
        Globe.hideContextMenu();
      });
    });

    // Also open drawer on fuel-panel row click
    document.getElementById('fuel-list')?.addEventListener('click', (e) => {
      const row = e.target.closest('.fuel-row');
      if (!row) return;
      const satId = row.dataset.satId;
      const sat = AppState.state.satellites?.find(s => s.id === satId);
      if (sat) {
        AppState.selectSatellite(satId);
        const satCDMs = AppState.getCDMsForSatellite(satId);
        Drawer.open(sat, satCDMs, maneuverCache);
      }
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // RESIZE HANDLER
  // ══════════════════════════════════════════════════════════════════════════
  function handleResize() {
    Bullseye.resize();
    Gantt.resize();
    if (cdmCache.length) {
      Bullseye.update(cdmCache, simTimestamp);
      Gantt.update(maneuverCache, simTimestamp);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // TIMER CLEANUP
  // ══════════════════════════════════════════════════════════════════════════
  window.addEventListener('beforeunload', () => {
    // Clear all intervals and timeouts to prevent memory leaks
    const maxId = Math.max(setInterval(() => {}, 1000), setTimeout(() => {}, 1000));
    for (let i = 1; i < maxId; i++) {
      clearInterval(i);
      clearTimeout(i);
    }
  });
})();
