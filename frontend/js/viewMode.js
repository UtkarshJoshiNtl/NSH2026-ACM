/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — View Mode Switcher
   Handles switching between Projection and Charts modes
   ═══════════════════════════════════════════════════════════════════════════ */

const ViewMode = (() => {
  let currentMode = 'projection';
  
  function init() {
    const projectionBtn = document.getElementById('mode-projection');
    const chartsBtn = document.getElementById('mode-charts');
    
    if (projectionBtn) {
      projectionBtn.addEventListener('click', () => switchMode('projection'));
    }
    
    if (chartsBtn) {
      chartsBtn.addEventListener('click', () => switchMode('charts'));
    }
    
    // Initialize lucide icons
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }
  }
  
  function switchMode(mode) {
    if (mode === currentMode) return;
    
    const projectionView = document.getElementById('projection-view');
    const chartsView = document.getElementById('charts-view');
    const projectionBtn = document.getElementById('mode-projection');
    const chartsBtn = document.getElementById('mode-charts');
    const modeDisplay = document.getElementById('current-mode-display');
    
    // Update view visibility
    if (mode === 'projection') {
      projectionView.classList.add('active');
      chartsView.classList.remove('active');
      projectionBtn.classList.add('active');
      chartsBtn.classList.remove('active');
    } else {
      projectionView.classList.remove('active');
      chartsView.classList.add('active');
      projectionBtn.classList.remove('active');
      chartsBtn.classList.add('active');
    }
    
    // Update mode display
    if (modeDisplay) {
      modeDisplay.textContent = mode.toUpperCase();
    }
    
    // Trigger resize events for charts
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
      
      // Trigger specific chart resizes
      if (mode === 'charts' && typeof Bullseye !== 'undefined') {
        Bullseye.resize();
      }
      if (typeof Gantt !== 'undefined') {
        Gantt.resize();
      }
      if (typeof Telemetry !== 'undefined') {
        Telemetry.init();
      }
      if (typeof Fuel !== 'undefined') {
        Fuel.init();
      }
    }, 100);
    
    currentMode = mode;
    
    // Emit event for other modules
    if (typeof emit !== 'undefined') {
      emit('view-mode-changed', mode);
    }
  }
  
  function getCurrentMode() {
    return currentMode;
  }
  
  return { init, switchMode, getCurrentMode };
})();
