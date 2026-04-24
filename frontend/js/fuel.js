/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — Fuel Status Panel
   Migrated from AutoCM for hackathon-compliant fuel visualization
   • SVG circular arc gauge per satellite (colour-coded: green/amber/red)
   • Sorted lowest-fuel first
   • Pulsing critical indicator when fuel < 20%
   • Click row → select satellite
   ═══════════════════════════════════════════════════════════════════════════ */

const FuelPanel = (() => {
  let container = null;
  let isInitialized = false;
  const INITIAL_FUEL = 50.0; // kg — nominal full tank

  // Gauge geometry
  const GAUGE_R  = 18;      // arc radius (px)
  const GAUGE_SW = 5;       // stroke-width
  const GAUGE_SIZE = (GAUGE_R + GAUGE_SW) * 2 + 2; // svg width/height
  const BG_DASH  = 2 * Math.PI * GAUGE_R;

  function init() {
    if (isInitialized) return;
    isInitialized = true;
    container = document.getElementById('fuel-list');
  }

  function update(satellites) {
    if (!container) return;

    // Sort by fuel ascending (critical first)
    const sorted = [...satellites].sort((a, b) => a.fuel_kg - b.fuel_kg);

    // ── D3 data join ──────────────────────────────────────────────────────
    const rows = d3.select(container)
      .selectAll('.fuel-row')
      .data(sorted, d => d.id);

    // ── Enter ─────────────────────────────────────────────────────────────
    const enter = rows.enter()
      .append('div')
      .attr('class', 'fuel-row')
      .attr('data-sat-id', d => d.id)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        if (typeof AppState !== 'undefined') AppState.selectSatellite(d.id);
        if (typeof Globe !== 'undefined')    Globe.flyToSatelliteById(d.id);
      });

    // Gauge SVG (arc)
    const gaugeSvg = enter.append('svg')
      .attr('class', 'fuel-arc-svg')
      .attr('width',  GAUGE_SIZE)
      .attr('height', GAUGE_SIZE)
      .attr('viewBox', `0 0 ${GAUGE_SIZE} ${GAUGE_SIZE}`);

    const cx = GAUGE_SIZE / 2;
    const cy = GAUGE_SIZE / 2;

    // Background ring
    gaugeSvg.append('circle')
      .attr('class', 'fuel-arc-bg')
      .attr('cx', cx).attr('cy', cy)
      .attr('r', GAUGE_R)
      .attr('fill', 'none')
      .attr('stroke', '#30363d')
      .attr('stroke-width', GAUGE_SW);

    // Foreground arc
    gaugeSvg.append('circle')
      .attr('class', 'fuel-arc-fill')
      .attr('cx', cx).attr('cy', cy)
      .attr('r', GAUGE_R)
      .attr('fill', 'none')
      .attr('stroke-width', GAUGE_SW)
      .attr('stroke-linecap', 'round')
      // Start at 12 o'clock
      .attr('transform', `rotate(-90, ${cx}, ${cy})`);

    // Centre text (% value)
    gaugeSvg.append('text')
      .attr('class', 'fuel-arc-text')
      .attr('x', cx).attr('y', cy + 1)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('font-size', '8px');

    // Label section
    const info = enter.append('div').attr('class', 'fuel-info');

    info.append('span').attr('class', 'fuel-sat-id');
    info.append('span').attr('class', 'fuel-status-badge');

    const barTrack = info.append('div').attr('class', 'fuel-bar-track');
    barTrack.append('div').attr('class', 'fuel-bar-fill');

    info.append('span').attr('class', 'fuel-kg');

    // ── Update (enter + existing) ─────────────────────────────────────────
    const merged = enter.merge(rows);

    merged
      .classed('selected',   d => d.id === AppState?.state?.selectedSatelliteId)
      .classed('fuel-critical', d => {
        const pct = (d.fuel_kg / INITIAL_FUEL) * 100;
        return pct < 20 && d.status !== 'EOL';
      });

    merged.each(function(d) {
      const pct   = d.status === 'EOL' ? 0 : Math.min(100, Math.max(0, (d.fuel_kg / INITIAL_FUEL) * 100));
      const color = d.status === 'EOL' ? '#6e7681'
                  : pct < 20           ? '#f85149'
                  : pct < 50           ? '#d29922'
                  : '#3fb950';

      const el = d3.select(this);

      // Arc: stroke-dasharray trick — dashoffset = (1 - pct/100) * circumference
      const circ = BG_DASH;
      const offset = circ * (1 - pct / 100);
      el.select('.fuel-arc-fill')
        .attr('stroke', color)
        .attr('stroke-dasharray', `${circ} ${circ}`)
        .transition().duration(600)
        .attr('stroke-dashoffset', offset);

      el.select('.fuel-arc-text')
        .text(d.status === 'EOL' ? 'EOL' : Math.round(pct) + '%')
        .attr('fill', color);

      el.select('.fuel-sat-id')
        .text(d.id.replace('SAT-', ''))
        .style('color', d.id === AppState?.state?.selectedSatelliteId ? '#58a6ff' : '#8b949e');

      el.select('.fuel-status-badge')
        .text(d.status)
        .attr('class', `fuel-status-badge status-${d.status.toLowerCase()}`);

      el.select('.fuel-bar-fill')
        .style('width', pct + '%')
        .style('background-color', color)
        .classed('pulse-fuel-low', pct < 20 && d.status !== 'EOL');

      el.select('.fuel-kg')
        .text(d.status === 'EOL' ? '0.0 kg' : d.fuel_kg.toFixed(1) + ' kg')
        .style('color', color);
    });

    // ── Exit ──────────────────────────────────────────────────────────────
    rows.exit()
      .transition().duration(250)
      .style('opacity', 0)
      .remove();

    // Re-sort DOM order
    merged.sort((a, b) => a.fuel_kg - b.fuel_kg);
  }

  return { init, update };
})();
