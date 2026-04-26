/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — Conjunction Bullseye Chart (D3.js)
   Section 6.2 — Conjunction "Bullseye" Plot (Polar Chart)
   • Centre = selected satellite (origin)
   • Radial distance = Time to Closest Approach (TCA) in hours
   • Angle = real approach bearing from satellite lat/lon to debris lat/lon
   • Risk colour coding — Green ≥5 km, Yellow <5 km, Red <1 km (spec §6.2)
   • Animated radar sweep
   • Legend overlay
   ═══════════════════════════════════════════════════════════════════════════ */

const Bullseye = (() => {
  let svg = null;
  let g = null;
  let width = 0;
  let height = 0;
  let radius = 0;
  let isInitialized = false;
  // Keep a satellite position lookup for bearing calculation
  let _satPositions = {};

  const MAX_HOURS = 24;

  // ── Initialize ────────────────────────────────────────────────────────────
  function init() {
    if (isInitialized) return;
    isInitialized = true;

    const container = document.getElementById('bullseye-svg-container');
    if (!container) return;

    _measure(container);

    svg = d3.select('#bullseye-svg')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('width', '100%')
      .style('height', '100%');

    _buildDefs();
    g = svg.append('g').attr('transform', `translate(${width / 2},${height / 2})`);
    _drawStaticElements();
  }

  function _measure(container) {
    container = container || document.getElementById('bullseye-svg-container');
    if (!container) return;
    const rect = container.getBoundingClientRect();
    width  = Math.max(rect.width,  200);
    height = Math.max(rect.height, 200);
    radius = Math.min(width, height) / 2 - 30;
  }

  // ── SVG Defs (filters removed for performance) ─────────────────────────────
  function _buildDefs() {
    // No filters for performance
  }

  // ── Static Elements (rings, radials, legend) ─────────────────────────────
  function _drawStaticElements() {
    // Background circle
    g.append('circle')
      .attr('r', radius)
      .attr('fill', '#0d1117')
      .attr('stroke', '#30363d')
      .attr('stroke-width', 2);

    // Concentric rings: 8h, 16h, 24h
    const ringDefs = [
      { hours: 8,  r: radius * (8  / MAX_HOURS) },
      { hours: 16, r: radius * (16 / MAX_HOURS) },
      { hours: 24, r: radius },
    ];
    ringDefs.forEach(({ hours, r }) => {
      g.append('circle')
        .attr('r', r)
        .attr('fill', 'none')
        .attr('stroke', '#30363d')
        .attr('stroke-width', hours === 24 ? 2 : 1.5)
        .attr('stroke-dasharray', hours === 24 ? 'none' : '4,4');

      // Hour label at 3 o'clock
      g.append('text')
        .attr('x', r + 6)
        .attr('y', 4)
        .attr('fill', '#8b949e')
        .attr('font-size', '12px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(`${hours}h`);
    });

    // Critical zone — inner 2h red ring
    const critR = radius * (2 / MAX_HOURS);
    g.append('circle')
      .attr('class', 'crit-ring')
      .attr('r', critR)
      .attr('fill', '#f85149')
      .attr('fill-opacity', 0.15)
      .attr('stroke', '#f85149')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '6,4');

    // Radial spokes (8)
    for (let i = 0; i < 8; i++) {
      const angle = (i * 45 - 90) * Math.PI / 180;
      g.append('line')
        .attr('x1', 0).attr('y1', 0)
        .attr('x2', Math.cos(angle) * radius)
        .attr('y2', Math.sin(angle) * radius)
        .attr('stroke', '#0d1f33')
        .attr('stroke-width', 0.5);
    }

    // Cardinal direction labels
    [['N', 0, -1], ['E', 1, 0], ['S', 0, 1], ['W', -1, 0]].forEach(([label, dx, dy]) => {
      g.append('text')
        .attr('x', dx * (radius + 16))
        .attr('y', dy * (radius + 18))
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('fill', '#8b949e')
        .attr('font-size', '13px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(label);
    });

    // Radar sweep animation
    const sweepLine = g.append('line')
      .attr('x1', 0).attr('y1', 0)
      .attr('x2', 0).attr('y2', -radius)
      .attr('stroke', '#58a6ff')
      .attr('stroke-opacity', 0.5)
      .attr('stroke-width', 2);

    (function animateSweep() {
      sweepLine.transition()
        .duration(5000)
        .ease(d3.easeLinear)
        .attrTween('transform', () => d3.interpolateString('rotate(0)', 'rotate(360)'))
        .on('end', animateSweep);
    })();

    // Centre satellite dot
    g.append('circle')
      .attr('r', 6)
      .attr('fill', '#58a6ff');

    // Legend
    _drawLegend();

    // Debris dots group (drawn above everything)
    g.append('g').attr('class', 'debris-group');
  }

  function _drawLegend() {
    const lx = -radius;
    const ly =  radius - 6;
    const legend = g.append('g').attr('transform', `translate(${lx},${ly})`);

    const CONFIG = {
      radius: 180,
      innerRadius: 50,
      maxMissDistance: 10.0,
    };

    const items = [
      { color: '#3fb950', label: '≥5 km — Safe' },
      { color: '#d29922', label: '<5 km — Warning' },
      { color: '#f85149', label: '<1 km — Critical' },
    ];

    items.forEach(({ color, label }, i) => {
      const row = legend.append('g').attr('transform', `translate(0,${-i * 16})`);
      row.append('circle').attr('r', 4).attr('fill', color).attr('cy', -1);
      row.append('text')
        .attr('x', 7)
        .attr('y', 1)
        .attr('fill', '#8b949e')
        .attr('font-size', '8px')
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(label);
    });
  }

  // ── Satellite Position Cache ──────────────────────────────────────────────
  function setSatellitePositions(satellites) {
    _satPositions = {};
    (satellites || []).forEach(s => {
      _satPositions[s.id] = { lat: s.lat, lon: s.lon };
    });
  }

  // ── Bearing Calculation ──────────────────────────────────────────────────
  // Returns bearing in degrees [0, 360) from (lat1,lon1) to (lat2,lon2)
  function _bearing(lat1, lon1, lat2, lon2) {
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;
    const y  = Math.sin(Δλ) * Math.cos(φ2);
    const x  = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  // ── Risk Colour (spec §6.2) ───────────────────────────────────────────────
  function _riskColor(missKm) {
    if (missKm < 1) return '#f85149';   // Red — Critical < 1 km
    if (missKm < 5) return '#d29922';   // Yellow — Warning < 5 km
    return '#3fb950';                   // Green — Safe ≥ 5 km
  }

  // ── Update with CDM Data ─────────────────────────────────────────────────
  function update(cdms, simTimestamp) {
    if (!g) return;

    const now = simTimestamp ? new Date(simTimestamp) : new Date();
    const selectedId = AppState?.state?.selectedSatelliteId;

    // Determine CDMs to show
    const relevantCDMs = selectedId
      ? cdms.filter(c => c.satelliteId === selectedId)
      : cdms.slice(0, 20);

    // Update subtitle
    const satIdEl = document.getElementById('bullseye-sat-id');
    if (satIdEl) satIdEl.textContent = selectedId || 'ALL SATELLITES';

    // Map CDMs → polar coordinates using real bearing from sat → debris
    const satPos = selectedId ? _satPositions[selectedId] : null;

    const dots = relevantCDMs.map((cdm, i) => {
      const tcaDate    = new Date(cdm.tca);
      const hoursToTCA = Math.max(0, (tcaDate - now) / 3600000);
      const r = Math.min(hoursToTCA / MAX_HOURS, 1) * radius;

      // Bearing: use real sat → debris position if available
      let angleDeg;
      if (satPos && cdm.debrisLat !== undefined && cdm.debrisLon !== undefined) {
        angleDeg = _bearing(satPos.lat, satPos.lon, cdm.debrisLat, cdm.debrisLon);
      } else if (cdm.approachAngle !== undefined) {
        angleDeg = cdm.approachAngle;
      } else {
        // Deterministic fallback — hash satellite+debris ID
        let hash = 0;
        const key = (cdm.debrisId || '') + (cdm.satelliteId || '') + i;
        for (let k = 0; k < key.length; k++) hash = (hash * 31 + key.charCodeAt(k)) & 0xfffff;
        angleDeg = (hash % 360 + 360) % 360;
      }

      const angleRad = (angleDeg - 90) * Math.PI / 180;
      const color    = _riskColor(cdm.missDistance);
      const size     = cdm.missDistance < 1 ? 9
                     : cdm.missDistance < 5 ? 7
                     : 5;

      return {
        x: Math.cos(angleRad) * r,
        y: Math.sin(angleRad) * r,
        color,
        size,
        cdm,
        hoursToTCA,
        angleDeg,
      };
    });

    // D3 data join
    const debrisGroup = g.select('.debris-group');
    const circles = debrisGroup.selectAll('.debris-dot')
      .data(dots, (d, i) => (d.cdm.debrisId || '') + '-' + i);

    // Enter
    const enter = circles.enter()
      .append('circle')
      .attr('class', 'debris-dot')
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', 0)
      .attr('fill', d => d.color)
      .attr('opacity', 0.9)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        if (typeof AppState !== 'undefined') AppState.selectSatellite(d.cdm.satelliteId);
      });

    enter.append('title')
      .text(d => `${d.cdm.debrisId || 'Unknown'}\nMiss: ${d.cdm.missDistance?.toFixed(3)} km\nTCA: T-${d.hoursToTCA.toFixed(1)}h\nBearing: ${d.angleDeg.toFixed(0)}°\nP(coll): ${((d.cdm.probability || 0) * 100).toFixed(4)}%`);

    enter.transition().duration(500).attr('r', d => d.size);

    // Update
    circles.transition().duration(400)
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => d.size)
      .attr('fill', d => d.color);

    circles.select('title')
      .text(d => `${d.cdm.debrisId || 'Unknown'}\nMiss: ${d.cdm.missDistance?.toFixed(3)} km\nTCA: T-${d.hoursToTCA.toFixed(1)}h\nBearing: ${d.angleDeg.toFixed(0)}°\nP(coll): ${((d.cdm.probability || 0) * 100).toFixed(4)}%`);

    // Exit
    circles.exit().transition().duration(300).attr('r', 0).remove();
  }

  // ── Update Debris ─────────────────────────────────────────────────────────────
  function updateDebris(debrisCloud) {
    if (!debrisCloud || !debrisCloud.length) {
      g.selectAll('.debris-dot').remove();
      return;
    }

    // Subsample debris for performance (1 in 2 - show more for better visibility)
    const SUBSAMPLE = 1;
    const displayDebris = [];
    for (let i = 0; i < debrisCloud.length; i += SUBSAMPLE) {
      displayDebris.push(debrisCloud[i]);
    }

    // D3 data join
    const debrisGroup = g.select('.debris-group');
    const circles = debrisGroup.selectAll('.debris-dot')
      .data(displayDebris, (d, i) => (d.debrisId || '') + '-' + i);

    // Enter
    const enter = circles.enter()
      .append('circle')
      .attr('class', 'debris-dot')
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', 0)
      .attr('fill', d => d.color)
      .attr('opacity', 0.9)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        if (typeof AppState !== 'undefined') AppState.selectSatellite(d.satelliteId);
      });

    enter.append('title')
      .text(d => `${d.debrisId || 'Unknown'}\nMiss: ${d.missDistance?.toFixed(3)} km\nTCA: T-${d.hoursToTCA.toFixed(1)}h\nBearing: ${d.angleDeg.toFixed(0)}°\nP(coll): ${((d.probability || 0) * 100).toFixed(4)}%`);

    enter.transition().duration(500).attr('r', d => d.size);

    // Update
    circles.transition().duration(400)
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => d.size)
      .attr('fill', d => d.color);

    circles.select('title')
      .text(d => `${d.debrisId || 'Unknown'}\nMiss: ${d.missDistance?.toFixed(3)} km\nTCA: T-${d.hoursToTCA.toFixed(1)}h\nBearing: ${d.angleDeg.toFixed(0)}°\nP(coll): ${((d.probability || 0) * 100).toFixed(4)}%`);

    // Exit
    circles.exit().transition().duration(300).attr('r', 0).remove();
  }

  // ── Resize ────────────────────────────────────────────────────────────────
  function resize() {
    isInitialized = false;
    if (svg) svg.selectAll('*').remove();
    svg = null;
    g = null;
    init();
  }

  return { init, update, resize, setSatellitePositions, updateDebris };
})();
