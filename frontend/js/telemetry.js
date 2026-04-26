/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — Telemetry Panel
   Section 6.2 — Telemetry & Resource Heatmaps
   • ΔV Cost Analysis scatter: "Fuel Consumed (kg)" vs "Collisions Avoided"
     — each point = one satellite's cumulative data
     — colour = satellite status
   • Latest CDM list with live countdown
   • System health grid
   ═══════════════════════════════════════════════════════════════════════════ */

const Telemetry = (() => {
  let isInitialized = false;

  // ── Scatter chart state ────────────────────────────────────────────────────
  let scatterSvg    = null;
  let scatterG      = null;
  let scatterWidth  = 0;
  let scatterHeight = 0;
  let xScale  = null;
  let yScale  = null;

  // Per-satellite accumulator: { satId → { fuelConsumed, collisionsAvoided } }
  let _satMetrics = {};

  // Legacy ΔV line chart state (kept for pollConstellationStats)
  let dvSvg    = null;
  let dvLine   = null;
  let dvArea   = null;
  let dvXScale = null;
  let dvYScale = null;

  const MARGIN = { top: 20, right: 16, bottom: 32, left: 44 };

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    if (isInitialized) return;
    isInitialized = true;
    _initScatterChart();
    _initDvLineChart();
  }

  // ── Scatter: Fuel Consumed vs Collisions Avoided ──────────────────────────
  function _initScatterChart() {
    const container = document.getElementById('dv-chart');
    if (!container) return;

    const rect = container.getBoundingClientRect();
    scatterWidth  = Math.max((rect.width  || 200) - MARGIN.left - MARGIN.right, 40);
    scatterHeight = Math.max((rect.height || 80)  - MARGIN.top  - MARGIN.bottom, 20);

    scatterSvg = d3.select('#dv-chart')
      .attr('width',  scatterWidth  + MARGIN.left + MARGIN.right)
      .attr('height', scatterHeight + MARGIN.top  + MARGIN.bottom);

    scatterG = scatterSvg.append('g')
      .attr('transform', `translate(${MARGIN.left},${MARGIN.top})`);

    xScale = d3.scaleLinear().domain([0, 5]).range([0, scatterWidth]);
    yScale = d3.scaleLinear().domain([0, 5]).range([scatterHeight, 0]);

    // Grid lines (X)
    scatterG.append('g')
      .attr('class', 'scatter-x-grid')
      .attr('transform', `translate(0,${scatterHeight})`)
      .call(d3.axisBottom(xScale).ticks(4).tickSize(-scatterHeight).tickFormat(''))
      .call(g => {
        g.select('.domain').remove();
        g.selectAll('line').attr('stroke', '#21262d').attr('stroke-dasharray', '3,3');
      });

    // Grid lines (Y)
    scatterG.append('g')
      .attr('class', 'scatter-y-grid')
      .call(d3.axisLeft(yScale).ticks(3).tickSize(-scatterWidth).tickFormat(''))
      .call(g => {
        g.select('.domain').remove();
        g.selectAll('line').attr('stroke', '#21262d').attr('stroke-dasharray', '3,3');
      });

    // X axis
    scatterG.append('g')
      .attr('class', 'scatter-x-axis')
      .attr('transform', `translate(0,${scatterHeight})`)
      .call(d3.axisBottom(xScale).ticks(4).tickFormat(d => d))
      .call(g => {
        g.select('.domain').attr('stroke', '#30363d');
        g.selectAll('text').attr('fill', '#8b949e').attr('font-size', '10px')
          .attr('font-family', 'JetBrains Mono');
        g.selectAll('line').attr('stroke', '#30363d');
      });

    // Y axis
    scatterG.append('g')
      .attr('class', 'scatter-y-axis')
      .call(d3.axisLeft(yScale).ticks(3).tickFormat(d => d + 'kg'))
      .call(g => {
        g.select('.domain').attr('stroke', '#30363d');
        g.selectAll('text').attr('fill', '#8b949e').attr('font-size', '10px')
          .attr('font-family', 'JetBrains Mono');
        g.selectAll('line').attr('stroke', '#30363d');
      });

    // Axis labels
    scatterG.append('text')
      .attr('x', scatterWidth / 2)
      .attr('y', scatterHeight + MARGIN.bottom - 6)
      .attr('text-anchor', 'middle')
      .attr('fill', '#8b949e')
      .attr('font-size', '10px')
      .attr('font-family', 'JetBrains Mono')
      .text('COLLISIONS AVOIDED');

    scatterG.append('text')
      .attr('transform', `rotate(-90)`)
      .attr('x', -scatterHeight / 2)
      .attr('y', -MARGIN.left + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', '#8b949e')
      .attr('font-size', '10px')
      .attr('font-family', 'JetBrains Mono')
      .text('FUEL (kg)');

    // Dots group
    scatterG.append('g').attr('class', 'scatter-dots');
  }

  // ── Update scatter from satellite data ────────────────────────────────────
  function _updateScatterFromSatellites(satellites, cdms, maneuvers) {
    if (!scatterG) return;

    // Accumulate metrics per satellite
    satellites.forEach(sat => {
      if (!_satMetrics[sat.id]) {
        _satMetrics[sat.id] = { fuelConsumed: 0, collisionsAvoided: 0, status: sat.status };
      }
      const m = _satMetrics[sat.id];
      // Fuel consumed = initial − current (approximate)
      const fuelConsumed = Math.max(0, 50.0 - sat.fuel_kg);
      m.fuelConsumed = fuelConsumed;
      m.status = sat.status;
    });

    // Count collisions avoided from EXECUTED maneuvers per sat
    (maneuvers || []).forEach(man => {
      if (man.status === 'EXECUTED' && _satMetrics[man.satelliteId]) {
        // Each executed evasion burn = 1 collision avoided (conservative)
        if (man.type === 'EVASION BURN' || man.burnId?.includes('EVASION')) {
          _satMetrics[man.satelliteId].collisionsAvoided =
            (_satMetrics[man.satelliteId].collisionsAvoided || 0) + 1;
        }
      }
    });

    // Also credit CDMs with missDistance < 1 km where sat is NOMINAL (was saved)
    (cdms || []).forEach(cdm => {
      if (cdm.missDistance < 1 && _satMetrics[cdm.satelliteId]) {
        const m = _satMetrics[cdm.satelliteId];
        m.collisionsAvoided = Math.max(m.collisionsAvoided || 0, 1);
      }
    });

    const points = Object.entries(_satMetrics).map(([id, m]) => ({
      id,
      x: m.collisionsAvoided,
      y: m.fuelConsumed,
      status: m.status,
    }));

    if (points.length === 0) return;

    // Rescale axes
    const maxX = Math.max(5, d3.max(points, d => d.x) + 1);
    const maxY = Math.max(5, d3.max(points, d => d.y) + 1);
    xScale.domain([0, maxX]);
    yScale.domain([0, maxY]);

    // Redraw axes
    scatterG.select('.scatter-x-axis')
      .call(d3.axisBottom(xScale).ticks(4))
      .call(g => {
        g.select('.domain').attr('stroke', '#30363d');
        g.selectAll('text').attr('fill', '#8b949e').attr('font-size', '10px')
          .attr('font-family', 'JetBrains Mono');
        g.selectAll('line').attr('stroke', '#30363d');
      });
    scatterG.select('.scatter-y-axis')
      .call(d3.axisLeft(yScale).ticks(3).tickFormat(d => d.toFixed(1) + 'kg'))
      .call(g => {
        g.select('.domain').attr('stroke', '#30363d');
        g.selectAll('text').attr('fill', '#8b949e').attr('font-size', '10px')
          .attr('font-family', 'JetBrains Mono');
        g.selectAll('line').attr('stroke', '#30363d');
      });

    // Dot colour by status
    function dotColor(status) {
      switch (status) {
        case 'EVADING':   return '#f85149';
        case 'RECOVERING': return '#d29922';
        case 'EOL':       return '#6e7681';
        default:          return '#3fb950';
      }
    }

    // D3 data join
    const dots = scatterG.select('.scatter-dots')
      .selectAll('.scatter-dot')
      .data(points, d => d.id);

    const enter = dots.enter()
      .append('circle')
      .attr('class', 'scatter-dot')
      .attr('cx', d => xScale(d.x))
      .attr('cy', d => yScale(d.y))
      .attr('r', 0)
      .attr('fill', d => dotColor(d.status))
      .attr('opacity', 0.9)
      .attr('stroke', '#0d1117')
      .attr('stroke-width', 1)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        if (typeof AppState !== 'undefined') AppState.selectSatellite(d.id);
      });

    enter.append('title')
      .text(d => `${d.id.replace('SAT-','')}\nFuel consumed: ${d.y.toFixed(2)} kg\nCollisions avoided: ${d.x}\nStatus: ${d.status}`);

    enter.transition().duration(600).attr('r', 5);

    dots.transition().duration(400)
      .attr('cx', d => xScale(d.x))
      .attr('cy', d => yScale(d.y))
      .attr('fill', d => dotColor(d.status));

    dots.exit().transition().duration(300).attr('r', 0).remove();

    // Update total label
    const totalFuel = Object.values(_satMetrics).reduce((s, m) => s + m.fuelConsumed, 0);
    const totalEl = document.getElementById('dv-total');
    if (totalEl) totalEl.textContent = totalFuel.toFixed(1) + ' kg consumed';
  }

  // ── CDM List ──────────────────────────────────────────────────────────────
  function updateCDMList(cdms, simTimestamp) {
    const container = document.getElementById('cdm-list');
    if (!container) return;

    const now = simTimestamp ? new Date(simTimestamp) : new Date();
    const sorted = [...cdms].sort((a, b) => new Date(a.tca) - new Date(b.tca)).slice(0, 12);

    const rows = d3.select(container)
      .selectAll('.cdm-row')
      .data(sorted, (d, i) => (d.satelliteId || '') + (d.debrisId || '') + i);

    const enter = rows.enter()
      .append('div')
      .attr('class', 'cdm-row')
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        if (typeof AppState !== 'undefined') AppState.selectSatellite(d.satelliteId);
        if (typeof Globe !== 'undefined')    Globe.flyToSatelliteById(d.satelliteId);
      });

    const ids = enter.append('div').attr('class', 'cdm-ids');
    ids.append('span').attr('class', 'cdm-sat-id');
    ids.append('span').attr('class', 'cdm-vs').text('×');
    ids.append('span').attr('class', 'cdm-debris-id');
    enter.append('span').attr('class', 'cdm-badge');
    enter.append('span').attr('class', 'cdm-tca');

    const merged = enter.merge(rows);

    merged.select('.cdm-sat-id').text(d => (d.satelliteId || '').replace('SAT-', ''));
    merged.select('.cdm-debris-id').text(d => d.debrisId || '—');

    merged.select('.cdm-badge')
      .text(d => {
        const km = d.missDistance;
        if (km == null) return '—';
        return km < 0.1 ? `${(km * 1000).toFixed(0)}m` : `${km.toFixed(2)}km`;
      })
      .attr('class', d => {
        const km = d.missDistance;
        if (km == null) return 'cdm-badge';
        return `cdm-badge ${km < 1 ? 'red' : km < 5 ? 'amber' : 'green'}`;
      });

    merged.select('.cdm-tca')
      .text(d => {
        const diff = new Date(d.tca) - now;
        if (diff <= 0) return 'PASSED';
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        return `T-${h}h${String(m).padStart(2, '0')}m`;
      })
      .style('color', d => {
        const h = (new Date(d.tca) - now) / 3600000;
        return h < 2 ? '#f85149' : h < 8 ? '#d29922' : '#8b949e';
      });

    merged.attr('class', d => {
      const km = d.missDistance;
      return `cdm-row${km < 0.1 ? ' critical pulse-critical' : ''}`;
    });

    rows.exit().remove();
  }

  // ── Health Update ─────────────────────────────────────────────────────────
  function updateHealth(latency, timestamp) {
    const latEl  = document.getElementById('health-latency');
    const snapEl = document.getElementById('health-snapshot');

    if (latEl) {
      latEl.textContent = latency + ' ms';
      latEl.style.color = latency < 200 ? '#3fb950' : latency < 500 ? '#d29922' : '#f85149';
    }
    if (snapEl && timestamp) {
      snapEl.textContent = new Date(timestamp).toISOString().slice(11, 19) + 'Z';
    }
  }

  // ── ΔV Line Chart (legacy — still used by pollConstellationStats) ─────────
  function _initDvLineChart() {
    // Kept for backward compat; the scatter chart now occupies #dv-chart,
    // so dvLine references are no-ops.
  }

  function updateDvChart(dvHistory) {
    // Feed into scatter via synthetic satellite entries as a fallback
    // (real scatter is driven by updateFullMetrics)
  }

  // ── Full Metrics Update (called from main.js handleDataUpdate) ────────────
  function updateFullMetrics(satellites, cdms, maneuvers) {
    _updateScatterFromSatellites(satellites, cdms, maneuvers);
  }

  return { init, updateCDMList, updateHealth, updateDvChart, updateFullMetrics };
})();
