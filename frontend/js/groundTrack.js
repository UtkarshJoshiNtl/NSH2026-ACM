/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — 2D Mercator Ground Track Map (D3.js + Canvas overlay)
   Section 6.2 — Ground Track Map (Mercator Projection)
   • Real GeoJSON world atlas (TopoJSON)
   • Canvas overlay for 10,000+ debris objects at 60 FPS
   • Historical trail (last 90 min) + dashed predicted trajectory (next 90 min)
   • Terminator Line (day/night boundary) with correct winding
   • EVADING satellite pulsing marker
   ═══════════════════════════════════════════════════════════════════════════ */

const GroundTrack = (() => {
  let svg = null;
  let g = null;
  let canvas = null;
  let ctx = null;
  let width = 0;
  let height = 0;
  let isInitialized = false;
  let worldLoaded = false;
  let rafId = null;

  // Current debris snapshot for canvas render loop
  let _debrisData = [];

  // D3 Mercator projection
  const projection = d3.geoMercator();

  // ── Initialize ────────────────────────────────────────────────────────────
  function init() {
    if (isInitialized) return;
    isInitialized = true;

    const container = document.getElementById('groundtrack-svg-container');
    if (!container) return;

    _measure(container);

    // Canvas layer (underneath    // Canvas for debris rendering
    canvas = document.getElementById('debris-canvas');
    if (canvas) {
      canvas.width = width;
      canvas.height = height;
      ctx = canvas.getContext('2d');
      console.log('[Canvas] Canvas initialized:', width, 'x', height);
      console.log('[Canvas] Canvas element:', canvas);
      console.log('[Canvas] Canvas style:', canvas.style.cssText);
    } else {
      console.error('[Canvas] Debris canvas element not found!');
    }

    // SVG setup
    svg = d3.select('#groundtrack-svg')
      .attr('width', width)
      .attr('height', height)
      .style('position', 'absolute')
      .style('top', '0')
      .style('left', '0');

    g = svg.append('g');

    _drawBackground();
    _drawGraticule();
    _loadWorld();     // async — draws countries when ready
    _drawStaticLines();
  }

  function _measure(container) {
    const rect = container.getBoundingClientRect();
    width  = Math.max(rect.width,  200);
    height = Math.max(rect.height, 100);
    projection
      .scale(width / 2 / Math.PI)
      .translate([width / 2, height / 2])
      .clipExtent([[0, 0], [width, height]]);
  }

  // ── World Atlas (TopoJSON) ────────────────────────────────────────────────
  async function _loadWorld() {
    try {
      const topoData = await fetch(
        'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'
      ).then(r => r.json());

      const countries = window.topojson
        ? topojson.feature(topoData, topoData.objects.countries)
        : null;

      if (!countries) {
        _drawFallbackContinents();
        return;
      }

      const path = d3.geoPath().projection(projection);

      // Ocean background
      g.append('path')
        .datum({ type: 'Sphere' })
        .attr('d', path)
        .attr('fill', '#0d1117')
        .attr('stroke', 'none');

      // Country fills
      g.append('path')
        .datum(countries)
        .attr('d', path)
        .attr('fill', '#161b22')
        .attr('stroke', '#30363d')
        .attr('stroke-width', 1)
        .attr('opacity', 0.9);

      // Country borders
      const borders = topojson.mesh(topoData, topoData.objects.countries, (a, b) => a !== b);
      g.append('path')
        .datum(borders)
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', '#30363d')
        .attr('stroke-width', 0.8);

      worldLoaded = true;

      // Terminator placeholder must be above land
      _ensureTerminatorElement();
    } catch (e) {
      console.warn('[GroundTrack] TopoJSON load failed, using fallback:', e.message);
      _drawFallbackContinents();
    }
  }

  function _drawBackground() {
    // No background fill - let debris canvas show through
    // g.append('rect')
    //   .attr('width', width)
    //   .attr('height', height)
    //   .attr('fill', '#0d1117');
  }

  function _drawGraticule() {
    const graticule = d3.geoGraticule().step([30, 30]);
    const path = d3.geoPath().projection(projection);
    g.append('path')
      .datum(graticule())
      .attr('class', 'graticule')
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', '#21262d')
      .attr('stroke-width', 0.8)
      .attr('opacity', 0.6);
  }

  function _drawStaticLines() {
    const path = d3.geoPath().projection(projection);

    // Equator
    g.append('path')
      .datum({ type: 'LineString', coordinates: [[-180, 0], [0, 0], [180, 0]] })
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', '#58a6ff')
      .attr('stroke-width', 1.2)
      .attr('opacity', 0.5);

    // Prime Meridian
    g.append('path')
      .datum({ type: 'LineString', coordinates: [[0, -85], [0, 85]] })
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', '#58a6ff')
      .attr('stroke-width', 1.2)
      .attr('opacity', 0.5);

    // Terminator placeholder (above land, below satellite markers)
    _ensureTerminatorElement();
  }

  function _ensureTerminatorElement() {
    if (!g.select('#terminator-night').empty()) return;
    g.append('path').attr('id', 'terminator-night');
    g.append('path').attr('id', 'terminator-edge');
  }

  // Fallback if TopoJSON CDN unreachable
  function _drawFallbackContinents() {
    const path = d3.geoPath().projection(projection);
    const continents = [
      [[-168,71],[-130,71],[-55,47],[-54,24],[-80,8],[-78,-4],[-60,-4],[-35,-6],[-38,-55],[-68,-55],[-80,-10],[-82,8],[-85,15],[-90,16],[-92,19],[-88,16],[-83,10],[-77,8],[-77,9],[-79,8],[-77,4],[-75,0],[-70,-5],[-80,0],[-80,8],[-77,4],[-75,0],[-68,-4],[-52,4],[-50,5],[-30,5],[-15,10],[0,5],[15,5],[30,8],[42,11],[50,12],[55,23],[58,22],[60,22],[77,35],[90,23],[100,5],[103,-1],[110,-5],[115,-8],[130,-14],[135,-18],[145,-20],[155,-25],[150,-40],[145,-38],[138,-35],[114,-30],[115,-25],[112,-20],[110,-5],[100,-2],[98,5],[95,20],[88,22],[80,28],[74,34],[62,23],[56,22],[55,25],[51,24],[44,12],[44,9],[42,12],[42,16],[37,21],[37,22],[32,30],[32,31],[35,33],[36,36],[38,37],[36,37],[28,41],[26,41],[24,38],[22,37],[18,38],[14,36],[10,37],[5,37],[-5,35],[-10,36],[-15,33],[-17,20],[-17,15],[-15,10],[-15,11],[-12,15],[-16,22],[-17,28],[-13,28],[-8,25],[0,20],[10,22],[12,15],[14,8],[14,4],[10,0],[10,-5],[15,-10],[18,-18],[20,-20],[28,-30],[30,-30],[32,-28],[38,-20],[40,-10],[42,-2],[44,8],[44,12]],
    ];
    // Only draw the world as a single simplified sphere outline
    g.append('path')
      .datum({ type: 'Sphere' })
      .attr('d', d3.geoPath().projection(projection))
      .attr('fill', '#161b22')
      .attr('stroke', '#30363d')
      .attr('stroke-width', 1);

    worldLoaded = true;
    _ensureTerminatorElement();
  }

  // ── Terminator Line (Day/Night Boundary) ─────────────────────────────────
  function _updateTerminator(simTime) {
    const terminatorNight = g.select('#terminator-night');
    const terminatorEdge  = g.select('#terminator-edge');
    if (terminatorNight.empty()) return;

    const now = simTime ? new Date(simTime) : new Date();
    const path = d3.geoPath().projection(projection);

    // Solar declination (degrees)
    const startOfYear = new Date(Date.UTC(now.getUTCFullYear(), 0, 1));
    const dayOfYear = (now - startOfYear) / 86400000;
    const decl = 23.4397 * Math.sin((2 * Math.PI / 365.25) * (dayOfYear - 80));

    // Sun's sub-solar longitude
    const utcFrac = (now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600) / 24;
    const sunLon  = (180 - utcFrac * 360 + 360) % 360 - 180;

    // Build terminator polygon — closed on night pole
    const termPts = [];
    for (let lon = -180; lon <= 180; lon += 1) {
      const dLon = (lon - sunLon) * Math.PI / 180;
      const sinDecl = Math.sin(decl * Math.PI / 180);
      const cosDecl = Math.cos(decl * Math.PI / 180);
      // latitude where it transitions from day to night
      let tLat = Math.atan(-Math.cos(dLon) / Math.tan(decl * Math.PI / 180)) * 180 / Math.PI;
      tLat = Math.max(-89, Math.min(89, tLat));
      termPts.push([lon, tLat]);
    }

    // Close by sweeping to the dark pole
    const darkPole = decl >= 0 ? -90 : 90;
    const nightSide = [
      ...termPts,
      [180, darkPole],
      [-180, darkPole],
      termPts[0],
    ];

    terminatorNight
      .datum({ type: 'Polygon', coordinates: [nightSide] })
      .attr('d', path)
      .attr('fill', '#000000')
      .attr('fill-opacity', 0.5)
      .attr('stroke', 'none');

    // Glowing edge line
    terminatorEdge
      .datum({ type: 'LineString', coordinates: termPts })
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', '#d29922')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '6,3');
  }

  // ── Satellite Markers + Trails ────────────────────────────────────────────
  function update(satellites, simTime) {
    if (!g) return;

    const path = d3.geoPath().projection(projection);

    // Remove previous dynamic elements
    g.selectAll('.sat-trail').remove();
    g.selectAll('.sat-predicted').remove();
    g.selectAll('.sat-pulse').remove();
    g.selectAll('.sat-click-target').remove();
    g.selectAll('.sat-marker').remove();
    g.selectAll('.sat-label').remove();

    const selectedId = AppState?.state?.selectedSatelliteId;

    satellites.forEach(sat => {
      const isSelected = sat.id === selectedId;
      const isEvading  = sat.status === 'EVADING';

      // ── Historical trail (90 min) — ONLY for selected satellite ──
      if (isSelected) {
        const histFeature = _orbitTrail(sat.lon, sat.lat, -90);
        g.append('path')
          .attr('class', 'sat-trail')
          .datum(histFeature)
          .attr('d', path)
          .attr('fill', 'none')
          .attr('stroke', '#58a6ff')
          .attr('stroke-opacity', 0.8)
          .attr('stroke-width', 2)
          .attr('opacity', 0.8);

        // ── Predicted trajectory (90 min) — dashed — ONLY for selected satellite ──
        const predFeature = _orbitTrail(sat.lon, sat.lat, 90);
        g.append('path')
          .attr('class', 'sat-predicted')
          .datum(predFeature)
          .attr('d', path)
          .attr('fill', 'none')
          .attr('stroke', '#d29922')
          .attr('stroke-opacity', 0.85)
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '5,3')
          .attr('opacity', 0.85);
      }

      // ── EVADING pulse ring ──
      if (isEvading || isSelected) {
        const [cx, cy] = projection([sat.lon, sat.lat]) || [0, 0];
        g.append('circle')
          .attr('class', 'sat-pulse')
          .attr('cx', cx)
          .attr('cy', cy)
          .attr('r', isSelected ? 16 : 12)
          .attr('fill', 'none')
          .attr('stroke', isEvading ? '#f85149' : '#58a6ff')
          .attr('stroke-width', 1.5)
          .attr('opacity', 0.5);
      }

      // ── Marker ──
      const [mx, my] = projection([sat.lon, sat.lat]) || [0, 0];
      // Color by status: green (NOMINAL), purple (EVADING), orange (RECOVERING), gray (EOL), white (selected)
      const markerColor = sat.status === 'EOL'      ? '#6e7681'
                        : sat.status === 'EVADING'  ? '#9b59b6'
                        : sat.status === 'RECOVERING' ? '#f39c12'
                        : isSelected               ? '#ffffff'
                        : '#2ecc71';

      // Invisible larger click target for easier clicking
      g.append('circle')
        .attr('class', 'sat-click-target')
        .attr('cx', mx)
        .attr('cy', my)
        .attr('r', 15)
        .attr('fill', 'transparent')
        .style('cursor', 'pointer')
        .on('click', (event) => {
          event.stopPropagation();
          console.log('[Click] Satellite clicked:', sat.id);
          if (typeof AppState !== 'undefined') {
            AppState.selectSatellite(sat.id);
            console.log('[Click] Selected satellite:', sat.id);
          }
          if (typeof Globe !== 'undefined')    Globe.flyToSatelliteById(sat.id);
        });

      // Visible marker
      g.append('circle')
        .attr('class', 'sat-marker')
        .attr('cx', mx)
        .attr('cy', my)
        .attr('r', isSelected ? 5 : 4)
        .attr('fill', markerColor)
        .attr('stroke', isSelected ? '#58a6ff' : '#0d1117')
        .attr('stroke-width', isSelected ? 2 : 1)
        .style('cursor', 'pointer')
        .on('click', (event) => {
          event.stopPropagation();
          if (typeof AppState !== 'undefined') AppState.selectSatellite(sat.id);
          if (typeof Globe !== 'undefined')    Globe.flyToSatelliteById(sat.id);
        })
        .append('title')
        .text(`${sat.id}\nStatus: ${sat.status}\nFuel: ${sat.fuel_kg?.toFixed(1)} kg\nLat: ${sat.lat?.toFixed(2)}° Lon: ${sat.lon?.toFixed(2)}°`);

      // ── Label for selected satellite ──
      if (isSelected) {
        g.append('text')
          .attr('class', 'sat-label')
          .attr('x', mx + 10)
          .attr('y', my - 8)
          .attr('fill', '#58a6ff')
          .attr('font-size', '12px')
          .attr('font-family', 'JetBrains Mono, monospace')
          .text(sat.id.replace('SAT-', ''));
      }
    });

    // Update terminator
    _updateTerminator(simTime || AppState?.state?.simTime);
  }

  // ── SVG Debris Rendering (more reliable than canvas) ─────────────────────
  let debrisGroup = null;
  
  function updateDebris(debrisCloud) {
    if (!g) return;
    
    // Remove old debris
    if (debrisGroup) {
      debrisGroup.remove();
    }
    
    // Create new debris group
    debrisGroup = g.append('g').attr('class', 'debris-group');
    
    // Get selected satellite for distance-based subsampling
    const selectedId = AppState?.state?.selectedSatelliteId;
    const satellites = AppState?.state?.satellites || [];
    const selectedSat = satellites.find(s => s.id === selectedId);
    
    let displayDebris = [];
    
    if (selectedSat && selectedSat.lat !== undefined && selectedSat.lon !== undefined) {
      // Calculate distances from selected satellite to all debris
      const satLat = selectedSat.lat;
      const satLon = selectedSat.lon;
      
      // Calculate distance using Haversine formula approximation
      const debrisWithDistance = debrisCloud.map(deb => {
        const debLat = deb[1];
        const debLon = deb[2];
        
        // Simple distance approximation (good enough for sorting)
        const dLat = (debLat - satLat) * Math.PI / 180;
        const dLon = (debLon - satLon) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(satLat * Math.PI / 180) * Math.cos(debLat * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const distance = 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); // km
        
        return { debris: deb, distance };
      });
      
      // Sort by distance and take 2000 closest
      debrisWithDistance.sort((a, b) => a.distance - b.distance);
      const CLOSEST_COUNT = 2000;
      displayDebris = debrisWithDistance.slice(0, CLOSEST_COUNT).map(d => d.debris);
      
      console.log('[Debris] Showing', displayDebris.length, 'closest debris to', selectedId);
    } else {
      // No satellite selected - subsample uniformly for performance
      const SUBSAMPLE = 50;
      for (let i = 0; i < debrisCloud.length; i += SUBSAMPLE) {
        displayDebris.push(debrisCloud[i]);
      }
      
      console.log('[Debris] Drawing', displayDebris.length, 'debris particles (subsampled from', debrisCloud.length, ')');
    }
    
    // Draw debris as circles on SVG
    const path = d3.geoPath().projection(projection);
    
    debrisGroup.selectAll('circle')
      .data(displayDebris)
      .enter()
      .append('circle')
      .attr('cx', d => {
        const pt = projection([d[2], d[1]]);
        return pt ? pt[0] : 0;
      })
      .attr('cy', d => {
        const pt = projection([d[2], d[1]]);
        return pt ? pt[1] : 0;
      })
      .attr('r', 3)
      .attr('fill', '#ff0033')
      .attr('opacity', 0.8);
  }

  // ── Orbit Trail Generator ─────────────────────────────────────────────────
  function _orbitTrail(baseLon, baseLat, minutes) {
    const numPts   = 60;
    const period   = 95.0;      // minutes — typical LEO
    const inc      = 53.0;      // degrees inclination
    const direction = minutes < 0 ? -1 : 1;
    const spanSecs  = Math.abs(minutes) * 60;
    const points    = [];

    const currentPhase = baseLat / inc >= 1 ? Math.PI / 2
                       : baseLat / inc <= -1 ? -Math.PI / 2
                       : Math.asin(baseLat / inc);

    for (let i = 0; i <= numPts; i++) {
      const dt    = (i / numPts) * spanSecs * direction;
      const phase = (dt / (period * 60)) * 2 * Math.PI;
      const lat   = inc * Math.sin(currentPhase + phase);
      const earthRotation = (-360.0 / 86400.0) * dt;
      const orbitAdv      = (dt / (period * 60)) * 360.0;
      let   lon = baseLon + orbitAdv + earthRotation;
      lon = ((lon + 180) % 360 + 360) % 360 - 180;
      points.push([lon, Math.max(-85, Math.min(85, lat))]);
    }

    // Split at antimeridian to prevent horizontal wrap artifacts
    const segments = [];
    let seg = [points[0]];
    for (let i = 1; i < points.length; i++) {
      if (Math.abs(points[i][0] - points[i-1][0]) > 180) {
        segments.push(seg);
        seg = [points[i]];
      } else {
        seg.push(points[i]);
      }
    }
    segments.push(seg);

    return { type: 'MultiLineString', coordinates: segments };
  }

  // ── Resize ────────────────────────────────────────────────────────────────
  function resize() {
    const container = document.getElementById('groundtrack-svg-container');
    if (!container) return;

    _measure(container);

    if (svg) svg.attr('width', width).attr('height', height);
    if (canvas) { canvas.width = width; canvas.height = height; }

    if (g) {
      g.selectAll('*').remove();
      _drawBackground();
      _drawGraticule();
      _loadWorld();
      _drawStaticLines();
    }
  }

  return { init, update, updateDebris, resize };
})();
