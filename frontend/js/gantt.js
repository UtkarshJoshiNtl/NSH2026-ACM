/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — Maneuver Timeline Gantt (D3.js)
   Migrated from AutoCM for hackathon-compliant maneuver visualization
   • Burn Start / Burn End blocks with distinct colours
   • 600s cooldown blocks with diagonal-stripe pattern
   • Conflict detection: overlapping burns on same satellite → red hatched flag
   • Blackout zone: burn scheduled inside cooldown window → ⚠ icon
   • NOW line tracking sim time
   • Row hover highlight
   • Zoom/pan on X axis
   ═══════════════════════════════════════════════════════════════════════════ */

const Gantt = (() => {
  let svg = null;
  let g = null;
  let xScale = null;
  let xAxis  = null;
  let xAxisGroup = null;
  let nowLine = null;
  let width   = 0;
  let height  = 0;
  let tooltipEl = null;
  let isInitialized = false;
  let zoom = null;
  let _currentXScale = null; // tracks zoomed scale

  const MARGIN     = { top: 24, right: 16, bottom: 8, left: 80 };
  const ROW_HEIGHT = 30;

  const BLOCK_COLORS = {
    'EVASION BURN':   { fill: '#0d2a5a', stroke: '#58a6ff', label: 'EVA' },
    'COOLDOWN':       { fill: 'url(#cooldown-pattern)', stroke: '#d29922', label: 'COOL' },
    'RECOVERY BURN':  { fill: '#0a2a1a', stroke: '#3fb950', label: 'REC' },
    'GRAVEYARD BURN': { fill: '#2a0808', stroke: '#f85149', label: 'EOL' },
  };

  const CONFLICT_FILL   = 'url(#conflict-pattern)';
  const COOLDOWN_SEC    = 600;

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    if (isInitialized) return;
    isInitialized = true;

    const container = document.getElementById('gantt-svg-container');
    if (!container) return;

    const rect = container.getBoundingClientRect();
    width  = Math.max(0, rect.width  - MARGIN.left - MARGIN.right);
    height = Math.max(0, rect.height - MARGIN.top  - MARGIN.bottom);

    tooltipEl = document.getElementById('gantt-tooltip');

    svg = d3.select('#gantt-svg')
      .attr('width',  rect.width)
      .attr('height', rect.height);

    _buildDefs(svg);

    // Clip path
    svg.append('defs').append('clipPath')
      .attr('id', 'gantt-clip')
      .append('rect')
      .attr('width', width)
      .attr('height', height + ROW_HEIGHT); // slight overflow

    g = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

    // Time scale (±4h around now)
    const now = new Date();
    xScale = d3.scaleTime()
      .domain([new Date(now.getTime() - 4 * 3600000), new Date(now.getTime() + 4 * 3600000)])
      .range([0, width]);
    _currentXScale = xScale;

    xAxis = d3.axisTop(xScale)
      .ticks(d3.timeMinute.every(30))
      .tickFormat(d3.timeFormat('%H:%M'))
      .tickSize(-height);

    xAxisGroup = g.append('g').attr('class', 'gantt-axis').call(xAxis);
    _styleAxis(xAxisGroup);

    // NOW line
    nowLine = g.append('line')
      .attr('class', 'now-line')
      .attr('y1', 0).attr('y2', height)
      .attr('stroke', '#f85149')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4,2');

    g.append('text')
      .attr('class', 'now-label')
      .attr('fill', '#f85149')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('text-anchor', 'middle')
      .attr('y', -8)
      .text('NOW');

    // Groups
    g.append('g').attr('class', 'gantt-rows');     // row highlight bands
    g.append('g').attr('class', 'gantt-blocks').attr('clip-path', 'url(#gantt-clip)');
    g.append('g').attr('class', 'gantt-labels');

    // Zoom (X only)
    zoom = d3.zoom()
      .scaleExtent([0.4, 6])
      .on('zoom', event => {
        const newX = event.transform.rescaleX(xScale);
        _currentXScale = newX;
        xAxisGroup.call(xAxis.scale(newX));
        _styleAxis(xAxisGroup);
        _repositionBlocks(newX);
        // Reposition NOW line
        const nowX = newX(new Date(nowLine.datum() || Date.now()));
        nowLine.attr('x1', nowX).attr('x2', nowX);
        g.select('.now-label').attr('x', nowX);
      });

    svg.call(zoom);
  }

  function _buildDefs(svg) {
    const defs = svg.select('defs').empty()
      ? svg.append('defs')
      : svg.select('defs');

    // Cooldown diagonal stripes
    const cdPat = defs.append('pattern')
      .attr('id', 'cooldown-pattern')
      .attr('patternUnits', 'userSpaceOnUse')
      .attr('width', 8).attr('height', 8)
      .attr('patternTransform', 'rotate(45)');
    cdPat.append('rect').attr('width', 4).attr('height', 8).attr('fill', '#1a0e02');
    cdPat.append('rect').attr('x', 4).attr('width', 4).attr('height', 8)
      .attr('fill', '#d29922');

    // Conflict red hatching
    const cfPat = defs.append('pattern')
      .attr('id', 'conflict-pattern')
      .attr('patternUnits', 'userSpaceOnUse')
      .attr('width', 6).attr('height', 6)
      .attr('patternTransform', 'rotate(-45)');
    cfPat.append('rect').attr('width', 3).attr('height', 6).attr('fill', '#f85149');
    cfPat.append('rect').attr('x', 3).attr('width', 3).attr('height', 6)
      .attr('fill', '#a02020');
  }

  function _styleAxis(axG) {
    axG.selectAll('text')
      .attr('fill', '#8b949e')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace');
    axG.selectAll('line').attr('stroke', '#30363d').attr('stroke-width', 1);
    axG.select('.domain').attr('stroke', '#30363d');
  }

  // ── Conflict & Blackout Detection ─────────────────────────────────────────
  function _detectConflicts(satBurns) {
    // Returns set of burnIds that have a scheduling conflict
    const conflicted = new Set();
    const burnBlocks = satBurns.filter(b => b.type !== 'COOLDOWN');

    burnBlocks.forEach((a, i) => {
      const aStart = new Date(a.burnTime).getTime();
      const aEnd   = aStart + (a.duration || 180) * 1000;

      burnBlocks.forEach((b, j) => {
        if (i >= j) return;
        const bStart = new Date(b.burnTime).getTime();
        const bEnd   = bStart + (b.duration || 180) * 1000;
        // Overlapping intervals
        if (aStart < bEnd && bStart < aEnd) {
          conflicted.add(a.burnId);
          conflicted.add(b.burnId);
        }
      });
    });

    return conflicted;
  }

  function _detectBlackouts(satBurns) {
    // Returns set of burnIds that fire during a cooldown window
    const blackedOut = new Set();
    const cooldowns  = satBurns.filter(b => b.type === 'COOLDOWN');
    const burns      = satBurns.filter(b => b.type !== 'COOLDOWN');

    burns.forEach(burn => {
      const bt = new Date(burn.burnTime).getTime();
      cooldowns.forEach(cd => {
        const cdStart = new Date(cd.burnTime).getTime();
        const cdEnd   = cdStart + COOLDOWN_SEC * 1000;
        if (bt >= cdStart && bt < cdEnd) {
          blackedOut.add(burn.burnId);
        }
      });
    });
    return blackedOut;
  }

  // ── Update ────────────────────────────────────────────────────────────────
  function update(maneuvers, simTimestamp) {
    if (!g || !xScale) return;

    const now = new Date(simTimestamp);
    nowLine.datum(now.getTime()); // store for zoom handler

    // Update time domain centred on now
    xScale.domain([
      new Date(now.getTime() - 4 * 3600000),
      new Date(now.getTime() + 4 * 3600000),
    ]);
    _currentXScale = xScale;

    xAxisGroup.call(xAxis.scale(xScale));
    _styleAxis(xAxisGroup);

    const nowX = xScale(now);
    nowLine.attr('x1', nowX).attr('x2', nowX);
    g.select('.now-label').attr('x', nowX);

    // ── Build satellite map with synthesised cooldown blocks ──────────────
    const satMap = {};
    maneuvers.forEach(m => {
      if (!satMap[m.satelliteId]) satMap[m.satelliteId] = [];
      const burnType = m.type ||
        (m.burnId?.includes('RECOVERY') ? 'RECOVERY BURN' : 'EVASION BURN');
      satMap[m.satelliteId].push({ ...m, type: burnType });

      // Synthesise 600s cooldown block
      const burnEnd = new Date(new Date(m.burnTime).getTime() + (m.duration || 180) * 1000);
      satMap[m.satelliteId].push({
        burnId:      `COOL-${m.burnId}`,
        satelliteId: m.satelliteId,
        burnTime:    burnEnd.toISOString(),
        duration:    COOLDOWN_SEC,
        type:        'COOLDOWN',
        status:      m.status === 'EXECUTED' ? 'EXECUTED' : 'PENDING',
      });
    });

    const satIds = Object.keys(satMap).sort();

    // ── Row highlight bands ───────────────────────────────────────────────
    const bands = g.select('.gantt-rows')
      .selectAll('.gantt-row-band')
      .data(satIds, d => d);

    bands.enter().append('rect')
      .attr('class', 'gantt-row-band')
      .merge(bands)
      .attr('x', 0).attr('width', width)
      .attr('y', (d, i) => i * ROW_HEIGHT)
      .attr('height', ROW_HEIGHT - 2)
      .attr('fill', (d, i) => i % 2 === 0 ? '#161b22' : 'transparent')
      .attr('opacity', 0.7);

    bands.exit().remove();

    // ── Row labels ────────────────────────────────────────────────────────
    const labels = g.select('.gantt-labels')
      .selectAll('.gantt-row-label')
      .data(satIds, d => d);

    labels.enter().append('text')
      .attr('class', 'gantt-row-label')
      .merge(labels)
      .attr('x', -8)
      .attr('y', (d, i) => i * ROW_HEIGHT + ROW_HEIGHT / 2)
      .attr('fill', '#8b949e')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'central')
      .text(d => d.replace('SAT-', '').slice(0, 12));

    labels.exit().remove();

    // ── Blocks ────────────────────────────────────────────────────────────
    const allBlocks = [];
    satIds.forEach((satId, rowIdx) => {
      const burns = satMap[satId];
      const conflicted = _detectConflicts(burns);
      const blackedOut = _detectBlackouts(burns);

      burns.forEach(m => {
        allBlocks.push({
          ...m,
          rowIdx,
          isConflict:  conflicted.has(m.burnId),
          isBlackout:  blackedOut.has(m.burnId),
        });
      });
    });

    const blocks = g.select('.gantt-blocks')
      .selectAll('.gantt-block')
      .data(allBlocks, d => d.burnId);

    // Enter
    const enter = blocks.enter()
      .append('g')
      .attr('class', 'gantt-block');

    enter.append('rect').attr('class', 'gantt-block-bg').attr('height', ROW_HEIGHT - 8).attr('rx', 3);
    enter.append('text').attr('class', 'gantt-block-label')
      .attr('dominant-baseline', 'central')
      .attr('font-size', '11px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .attr('fill', '#e6edf3')
      .attr('text-anchor', 'middle');

    // Conflict/blackout warning icon
    enter.append('text').attr('class', 'gantt-warn-icon')
      .attr('font-size', '12px')
      .attr('dominant-baseline', 'central')
      .attr('text-anchor', 'middle')
      .attr('fill', '#f85149');

    const merged = enter.merge(blocks);

    merged.each(function(d) {
      const grp       = d3.select(this);
      const burnStart = new Date(d.burnTime);
      const duration  = d.duration || 180;
      const burnEndT  = new Date(burnStart.getTime() + duration * 1000);
      const colors    = BLOCK_COLORS[d.type] || BLOCK_COLORS['EVASION BURN'];

      const x = (_currentXScale || xScale)(burnStart);
      const w = Math.max(8, (_currentXScale || xScale)(burnEndT) - x);
      const y = d.rowIdx * ROW_HEIGHT + 2;
      const h = ROW_HEIGHT - 5;

      const fillColor = d.isConflict ? CONFLICT_FILL
                      : d.isBlackout  ? '#f85149'
                      : colors.fill;

      const strokeColor = d.isConflict ? '#ff2020'
                        : d.isBlackout  ? '#ff6020'
                        : colors.stroke;

      grp.select('.gantt-block-bg')
        .attr('x', x).attr('y', y)
        .attr('width', w)
        .attr('fill', fillColor)
        .attr('stroke', strokeColor)
        .attr('stroke-width', d.isConflict || d.isBlackout ? 2 : 1.5)
        .attr('opacity', d.status === 'EXECUTED' ? 0.5 : 1);

      grp.select('.gantt-block-label')
        .attr('x', x + w / 2)
        .attr('y', y + h / 2)
        .text(w > 30 ? colors.label : '');

      grp.select('.gantt-warn-icon')
        .attr('x', x + w / 2)
        .attr('y', y - 5)
        .attr('opacity', d.isConflict || d.isBlackout ? 1 : 0)
        .text(d.isConflict ? '⚠' : d.isBlackout ? '🚫' : '');
    });

    // Tooltip
    merged
      .on('mouseenter', function(event, d) {
        if (!tooltipEl) return;
        const burnStart = new Date(d.burnTime);
        const dvMag = d.deltaV
          ? Math.sqrt((d.deltaV.x || 0) ** 2 + (d.deltaV.y || 0) ** 2 + (d.deltaV.z || 0) ** 2) * 1000
          : 0;
        const flagStr = d.isConflict ? ' ⚠ CONFLICT' : d.isBlackout ? ' 🚫 BLACKOUT' : '';
        tooltipEl.innerHTML = `
          <div style="color:#58a6ff;font-weight:600;margin-bottom:4px">${d.burnId}${flagStr}</div>
          <div><span style="color:#8b949e">TYPE</span>   ${d.type}</div>
          <div><span style="color:#8b949e">START</span>  ${burnStart.toISOString().slice(11,19)}Z</div>
          <div><span style="color:#8b949e">DUR</span>    ${d.duration || 180}s</div>
          <div><span style="color:#8b949e">ΔV</span>     ${dvMag.toFixed(2)} m/s</div>
          <div><span style="color:#8b949e">FUEL</span>   ${d.fuelCost?.toFixed(3) || '—'} kg</div>
          <div><span style="color:#8b949e">STATUS</span> ${d.status}</div>
        `;
        tooltipEl.style.left = (event.offsetX + 12) + 'px';
        tooltipEl.style.top  = Math.max(0, event.offsetY - 100) + 'px';
        tooltipEl.classList.add('visible');
      })
      .on('mouseleave', () => tooltipEl && tooltipEl.classList.remove('visible'));

    blocks.exit().remove();
  }

  function _repositionBlocks(newXScale) {
    g.select('.gantt-blocks').selectAll('.gantt-block').each(function(d) {
      const grp      = d3.select(this);
      const burnStart = new Date(d.burnTime);
      const duration  = d.duration || 180;
      const burnEndT  = new Date(burnStart.getTime() + duration * 1000);
      const x = newXScale(burnStart);
      const w = Math.max(8, newXScale(burnEndT) - x);
      const h = ROW_HEIGHT - 5;

      grp.select('.gantt-block-bg').attr('x', x).attr('width', w);
      grp.select('.gantt-block-label').attr('x', x + w / 2).text(w > 30
        ? (BLOCK_COLORS[d.type] || BLOCK_COLORS['EVASION BURN']).label : '');
      grp.select('.gantt-warn-icon').attr('x', x + w / 2);
    });
  }

  function resize() {
    isInitialized = false;
    if (svg) svg.selectAll('*').remove();
    svg = null; g = null; xScale = null; nowLine = null;
    init();
  }

  return { init, update, resize };
})();
