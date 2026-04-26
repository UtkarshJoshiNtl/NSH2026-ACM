/* =============================================================================
   SPEED CONTROL BAR — frontend/js/speedControl.js
   Auto-simulation controller with real-time speed multiplier.
   ============================================================================= */

(function () {
  'use strict';

  const SpeedControl = window.SpeedControl = {};

  // ── State ──────────────────────────────────────────────────────────────────
  let _running      = false;
  let _speed        = 60;     // step_seconds per real-second tick
  let _intervalMs   = 1000;   // real interval
  let _latestAfterId= 0;

  const SPEED_PRESETS = [
    { label: '1×',    step: 60,    interval: 1000 },
    { label: '10×',   step: 600,   interval: 1000 },
    { label: '100×',  step: 3600,  interval: 1000 },
    { label: '1000×', step: 36000, interval: 1000 },
  ];

  // ── Init ───────────────────────────────────────────────────────────────────
  SpeedControl.init = function () {
    _buildDOM();
    _bindEvents();
    _syncStatus().then(() => {
      // Auto-start if not running natively
      if (!_running) {
        _togglePlay();
      }
    });
  };

  // ── DOM Construction ───────────────────────────────────────────────────────
  function _buildDOM() {
    const bar = document.getElementById('speed-bar');
    if (!bar) return;

    bar.innerHTML = `
      <div class="sc-group">
        <button class="sc-btn sc-play" id="sc-play" title="Play / Pause (Space)">
          <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
            <polygon points="5,3 19,12 5,21" id="sc-play-icon"/>
          </svg>
        </button>
        <button class="sc-btn sc-stop" id="sc-reset" title="Stop Simulation">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <rect x="4" y="4" width="16" height="16" rx="2"/>
          </svg>
        </button>
        <button class="sc-btn sc-step" id="sc-step" title="Step Once (+)">
          <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
            <polygon points="5,3 15,12 5,21"/>
            <rect x="17" y="3" width="3" height="18" rx="1"/>
          </svg>
        </button>
      </div>

      <div class="sc-divider"></div>

      <div class="sc-group sc-speeds" id="sc-speeds">
        ${SPEED_PRESETS.map((p, i) =>
          `<button class="sc-btn sc-speed ${i === 0 ? 'active' : ''}" data-idx="${i}" title="${p.step}s/tick">${p.label}</button>`
        ).join('')}
      </div>

      <div class="sc-divider"></div>

      <div class="sc-status-group">
        <div class="sc-pulse-dot" id="sc-dot"></div>
        <span class="sc-label" id="sc-status-label">PAUSED</span>
        <span class="sc-sep">|</span>
        <span class="sc-label" id="sc-speed-label">${SPEED_PRESETS[0].label} · ${SPEED_PRESETS[0].step}s/tick</span>
      </div>
    `;
  }

  // ── Event Binding ──────────────────────────────────────────────────────────
  function _bindEvents() {
    document.getElementById('sc-play')?.addEventListener('click', _togglePlay);
    document.getElementById('sc-reset')?.addEventListener('click', _doReset);
    document.getElementById('sc-step')?.addEventListener('click', _doSingleStep);

    document.querySelectorAll('.sc-speed').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.idx, 10);
        _selectSpeed(idx);
      });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.code === 'Space') { e.preventDefault(); _togglePlay(); }
      if (e.key === '+' || e.key === '=') _doSingleStep();
    });
  }

  // ── Actions ────────────────────────────────────────────────────────────────
  async function _togglePlay() {
    if (_running) {
      // PAUSE
      await API.stopAutoSim();
      _running = false;
      _showAlert('⏸ Simulation paused', 'info');
    } else {
      // PLAY
      const preset = SPEED_PRESETS.find(p => p.step === _speed) || SPEED_PRESETS[0];
      await API.startAutoSim(preset.step, preset.interval);
      _running = true;
      _showAlert(`▶ Auto-sim started → ${preset.label} · ${preset.step}s/tick`, 'info');
    }
    _updateUI();
  }

  async function _doSingleStep() {
    const preset = SPEED_PRESETS.find(p => p.step === _speed) || SPEED_PRESETS[0];
    try {
      await API.simulateStep(preset.step);
      document.dispatchEvent(new CustomEvent('sim-step'));
      _showAlert(`⏭ Stepped +${preset.step}s`, 'info');
    } catch (e) {
      console.error('[SpeedControl] step failed:', e);
      _showAlert('⚠ Step failed', 'warn');
    }
  }

  async function _doReset() {
    if (_running) {
      await API.stopAutoSim();
      _running = false;
    }
    _showAlert('⏹ Simulation stopped', 'warn');
    _updateUI();
  }

  function _selectSpeed(idx) {
    const preset = SPEED_PRESETS[idx];
    if (!preset) return;
    _speed       = preset.step;
    _intervalMs  = preset.interval;

    document.querySelectorAll('.sc-speed').forEach((b, i) => {
      b.classList.toggle('active', i === idx);
    });
    const lbl = document.getElementById('sc-speed-label');
    if (lbl) lbl.textContent = `${preset.label} · ${preset.step}s/tick`;

    // If running, restart with new speed
    if (_running) {
      API.stopAutoSim().then(() => API.startAutoSim(_speed, _intervalMs));
      _showAlert(`⚡ Speed changed → ${preset.label}`, 'info');
    }
  }

  function _updateUI() {
    const dot      = document.getElementById('sc-dot');
    const lbl      = document.getElementById('sc-status-label');
    const playBtn  = document.getElementById('sc-play');

    if (lbl) lbl.textContent = _running ? 'SIMULATING' : 'PAUSED';
    if (dot) dot.classList.toggle('active', _running);

    // Toggle play/pause icon
    if (playBtn) {
      const svg = playBtn.querySelector('svg');
      if (svg) {
        if (_running) {
          // Show PAUSE bars
          svg.innerHTML = `<g id="sc-play-icon">
            <rect x="5" y="3" width="4" height="18" rx="1"/>
            <rect x="15" y="3" width="4" height="18" rx="1"/>
          </g>`;
          playBtn.title = 'Pause Simulation (Space)';
          playBtn.classList.add('sc-playing');
        } else {
          // Show PLAY triangle
          svg.innerHTML = `<polygon points="5,3 19,12 5,21" id="sc-play-icon"/>`;
          playBtn.title = 'Resume Simulation (Space)';
          playBtn.classList.remove('sc-playing');
        }
      }
    }

    // Highlight/dim step button based on running state
    const stepBtn = document.getElementById('sc-step');
    if (stepBtn) {
      stepBtn.style.opacity = _running ? '0.4' : '1';
      stepBtn.title = _running ? 'Pause first, then step' : 'Step Once (+)';
    }
  }

  // ── Alert Banner — Shows temporary status messages in the alerts panel ────
  function _showAlert(message, level = 'info') {
    const list = document.getElementById('alert-list');
    if (!list) return;

    const now = new Date();
    const time = now.toISOString().slice(11, 19);
    const severityChar = level === 'warn' ? 'W' : 'I';
    const severityClass = level === 'warn' ? 'amber' : 'info';

    const el = document.createElement('div');
    el.className = `alert-item alert-${severityClass}`;
    el.innerHTML = `
      <span class="alert-badge badge-${severityClass}">${severityChar}</span>
      <span class="alert-msg">${message}</span>
      <span class="alert-time">${time}Z</span>
    `;

    list.insertBefore(el, list.firstChild);

    // Animate in
    if (window.gsap) {
      gsap.from(el, { x: -20, opacity: 0, duration: 0.3, ease: 'power2.out' });
    }

    // Trim old entries
    while (list.children.length > 100) {
      list.removeChild(list.lastChild);
    }

    // Update badge count
    const badge = document.getElementById('alert-count-badge');
    if (badge) {
      const count = parseInt(badge.textContent || '0', 10) + 1;
      badge.textContent = count;
      badge.style.display = 'inline-flex';
    }
  }

  async function _syncStatus() {
    try {
      const status = await API.getSimStatus();
      if (status?.running) { _running = true; _updateUI(); }
    } catch (_) {}
  }

  // Called from outside to update status
  SpeedControl.setRunning = function(v) { _running = v; _updateUI(); };

})();
