/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — CesiumJS 3D Globe Module (Performance + UX Overhaul)
   ═══════════════════════════════════════════════════════════════════════════ */

const Globe = (() => {
  let viewer = null;
  let satPointCollection = null;
  let debrisPointCollection = null;
  let orbitLines = null;
  let conjunctionLines = null;
  let groundStationEntities = [];
  let satIdMap = {};
  let tooltipEl = null;
  let autoRotateHandler = null;
  let isInitialized = false;
  let userInteracting = false;
  let interactionTimeout = null;

  // ── Constants ────────────────────────────────────────────────────────────
  const MIN_ZOOM_DISTANCE = 2_000_000;     // 2,000 km — LEO is ~400km, stay well above
  const MAX_ZOOM_DISTANCE = 80_000_000;    // 80,000 km — full globe + lots of room
  const DEFAULT_ZOOM      = 25_000_000;    // 25,000 km — comfortable overview
  const SAT_ALTITUDE      = 500_000;       // 500 km — LEO altitude in meters

  const GROUND_STATIONS = [
    { id: 'GS-001', name: 'ISTRAC Bengaluru', lat: 13.0333, lon: 77.5167 },
    { id: 'GS-002', name: 'Svalbard',         lat: 78.2297, lon: 15.4077 },
    { id: 'GS-003', name: 'Goldstone',        lat: 35.4266, lon: -116.8900 },
    { id: 'GS-004', name: 'Punta Arenas',     lat: -53.1500, lon: -70.9167 },
    { id: 'GS-005', name: 'IIT Delhi',        lat: 28.5450, lon: 77.1926 },
    { id: 'GS-006', name: 'McMurdo',          lat: -77.8463, lon: 166.6682 },
  ];

  const STATUS_COLORS = {
    NOMINAL:    Cesium.Color.fromCssColorString('#2ecc71'),  // Green
    EVADING:    Cesium.Color.fromCssColorString('#9b59b6'),  // Purple
    RECOVERING: Cesium.Color.fromCssColorString('#f39c12'),  // Orange
    EOL:        Cesium.Color.fromCssColorString('#6e7681'),  // Gray
  };

  const STATUS_PIXEL_SIZE = {
    NOMINAL: 12, EVADING: 16, RECOVERING: 14, EOL: 10,
  };

  // ── Initialize ───────────────────────────────────────────────────────────
  function init() {
    if (isInitialized) return;
    isInitialized = true;

    Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI3ZGNiNThiZC01ZDFkLTQ4NjktYjZiZi05NTljMmYyMGExZWQiLCJpZCI6MjU5LCJpYXQiOjE3MjYxNTI4NjB9.Fljnrm4MFkEFCmGLO0LMnGajRwSBnxCERqfMzGnWIgk';

    tooltipEl = document.getElementById('globe-tooltip');

    viewer = new Cesium.Viewer('cesium-container', {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      navigationHelpButton: false,
      imageryProvider: new Cesium.ArcGisMapServerImageryProvider({
        url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
      }),
      navigationInstructionsInitiallyVisible: false,
      creditContainer: document.createElement('div'),
      skyBox: new Cesium.SkyBox({
        sources: {
          positiveX: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_px.jpg',
          negativeX: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_mx.jpg',
          positiveY: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_py.jpg',
          negativeY: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_my.jpg',
          positiveZ: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_pz.jpg',
          negativeZ: 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Assets/Textures/SkyBox/tycho2t3_80_mz.jpg',
        },
      }),
      skyAtmosphere: new Cesium.SkyAtmosphere(),
      scene3DOnly: true,
      shadows: false,
      requestRenderMode: false,
    });

    const scene = viewer.scene;

    // ── Dark Globe Appearance ────────────────────────────────────────────
    scene.backgroundColor = Cesium.Color.fromCssColorString('#030508');
    scene.globe.enableLighting = true;
    scene.globe.baseColor = Cesium.Color.fromCssColorString('#0a0e18');
    scene.fog.enabled = false;
    scene.globe.showGroundAtmosphere = true;

    // Subtle darkening
    try {
      const brightness = Cesium.PostProcessStageLibrary.createBrightnessStage();
      brightness.uniforms.brightness = 0.65;
      scene.postProcessStages.add(brightness);
    } catch (e) { /* ok */ }

    // Atmosphere
    scene.skyAtmosphere.brightnessShift = -0.1;
    scene.skyAtmosphere.saturationShift = -0.2;

    // ── Camera Zoom — FIX: Allow full zoom-out range ─────────────────────
    scene.screenSpaceCameraController.minimumZoomDistance = MIN_ZOOM_DISTANCE;
    scene.screenSpaceCameraController.maximumZoomDistance = MAX_ZOOM_DISTANCE;

    // FIX: Use default zoom factor (removing the _zoomFactor override that
    // was fighting with Cesium internals and causing zoom-out to fail)
    scene.screenSpaceCameraController.zoomEventTypes = [
      Cesium.CameraEventType.WHEEL,
      Cesium.CameraEventType.PINCH
    ];

    // Smooth inertia — lower = more responsive, higher = more cinematic
    scene.screenSpaceCameraController.inertiaSpin = 0.9;
    scene.screenSpaceCameraController.inertiaTranslate = 0.9;
    scene.screenSpaceCameraController.inertiaZoom = 0.8;

    // FIX: Disable collision detection — this was causing camera to get
    // "stuck" at certain zoom levels and preventing zoom-out
    scene.screenSpaceCameraController.enableCollisionDetection = false;

    // Allow tilt
    scene.screenSpaceCameraController.enableTilt = true;

    // ── Performance Optimizations ────────────────────────────────────────
    scene.globe.tileCacheSize = 100;
    scene.globe.maximumScreenSpaceError = 2;
    scene.fxaa = true;
    scene.globe.depthTestAgainstTerrain = false;

    // Cap resolution for performance
    if (viewer.resolutionScale > 1) {
      viewer.resolutionScale = 1.0;
    }

    // ── Init Primitive Collections ───────────────────────────────────────
    satPointCollection = scene.primitives.add(new Cesium.PointPrimitiveCollection());
    debrisPointCollection = scene.primitives.add(new Cesium.PointPrimitiveCollection());
    orbitLines = scene.primitives.add(new Cesium.PolylineCollection());
    conjunctionLines = scene.primitives.add(new Cesium.PolylineCollection());

    // Ground stations
    addGroundStations();
    
    // Terminator line (day/night boundary)
    addTerminatorLine();

    // Default camera — centered on India, looking straight down
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(77.19, 20.0, DEFAULT_ZOOM),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-90),
        roll: 0,
      },
    });

    // ── Auto-rotate (pauses on interaction) ──────────────────────────────
    startAutoRotate();

    // ── Event Handlers ───────────────────────────────────────────────────
    const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);

    // Stop auto-rotate on any user interaction
    const pauseAutoRotate = () => {
      userInteracting = true;
      stopAutoRotate();
      clearTimeout(interactionTimeout);
      interactionTimeout = setTimeout(() => {
        userInteracting = false;
        startAutoRotate();
      }, 8000); // Resume after 8s of inactivity
    };

    handler.setInputAction(pauseAutoRotate, Cesium.ScreenSpaceEventType.LEFT_DOWN);
    handler.setInputAction(pauseAutoRotate, Cesium.ScreenSpaceEventType.RIGHT_DOWN);
    handler.setInputAction(pauseAutoRotate, Cesium.ScreenSpaceEventType.MIDDLE_DOWN);
    handler.setInputAction(pauseAutoRotate, Cesium.ScreenSpaceEventType.WHEEL);

    // Left click — select satellite
    handler.setInputAction((click) => {
      hideContextMenu();
      const picked = pickSatellite(click.position);
      if (picked) {
        AppState.selectSatellite(picked.id);
        flyToSatellite(picked);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Mouse move — hover tooltip
    handler.setInputAction((movement) => {
      const picked = pickSatellite(movement.endPosition);
      if (picked) {
        showTooltip(picked, movement.endPosition);
        document.getElementById('cesium-container').style.cursor = 'pointer';
      } else {
        hideTooltip();
        document.getElementById('cesium-container').style.cursor = '';
      }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

    // Right click — context menu
    handler.setInputAction((click) => {
      const picked = pickSatellite(click.position);
      if (picked) {
        AppState.selectSatellite(picked.id);
        showContextMenu(click.position, picked);
      }
    }, Cesium.ScreenSpaceEventType.RIGHT_CLICK);

    // Double-click — smooth zoom to location
    handler.setInputAction((click) => {
      pauseAutoRotate();
      const cartesian = viewer.camera.pickEllipsoid(click.position, scene.globe.ellipsoid);
      if (cartesian) {
        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        const lon = Cesium.Math.toDegrees(cartographic.longitude);
        const lat = Cesium.Math.toDegrees(cartographic.latitude);
        const currentHeight = Cesium.Cartographic.fromCartesian(viewer.camera.position).height;
        const targetHeight = Math.max(MIN_ZOOM_DISTANCE, currentHeight * 0.5);
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(lon, lat, targetHeight),
          duration: 1.0,
        });
      }
    }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  }

  // ── Ground Stations ──────────────────────────────────────────────────────
  function addGroundStations() {
    GROUND_STATIONS.forEach(gs => {
      const entity = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(gs.lon, gs.lat, 0),
        point: {
          pixelSize: 8,
          color: Cesium.Color.fromCssColorString('#C0C0C0'),  // Metallic silver
          outlineColor: Cesium.Color.fromCssColorString('#E8E8E8').withAlpha(0.6),
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
        label: {
          text: gs.name.replace(/_/g, ' '),
          font: '10px JetBrains Mono',
          fillColor: Cesium.Color.fromCssColorString('#5a7a9a'),
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          outlineColor: Cesium.Color.fromCssColorString('#030508'),
          outlineWidth: 2,
          pixelOffset: new Cesium.Cartesian2(0, -16),
          scale: 0.8,
          showBackground: true,
          backgroundColor: Cesium.Color.fromCssColorString('rgba(8,13,20,0.85)'),
          backgroundPadding: new Cesium.Cartesian2(5, 3),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 30_000_000),
        },
      });
      groundStationEntities.push(entity);
    });
  }

  // ── Terminator Line (Day/Night Boundary) ─────────────────────────────────
  function addTerminatorLine() {
    const terminator = viewer.entities.add({
      name: 'Terminator Line',
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray([
          -180, 66.5,
          -90, 66.5,
          0, 66.5,
          90, 66.5,
          180, 66.5,
          180, -66.5,
          90, -66.5,
          0, -66.5,
          -90, -66.5,
          -180, -66.5,
          -180, 66.5
        ]),
        width: 2,
        material: Cesium.Material.fromType('PolylineGlow', {
          glowPower: 0.2,
          color: Cesium.Color.fromCssColorString('rgba(255, 200, 100, 0.4)'),
        }),
        clampToGround: true,
      },
    });
    groundStationEntities.push(terminator);
  }

  // ── Update Satellites ────────────────────────────────────────────────────
  function updateSatellites(satellites) {
    if (!isInitialized) return;
    satPointCollection.removeAll();
    orbitLines.removeAll();
    satIdMap = {};

    const selectedId = AppState.state.selectedSatelliteId;

    satellites.forEach((sat, idx) => {
      const color = STATUS_COLORS[sat.status] || STATUS_COLORS.NOMINAL;
      const pos = Cesium.Cartesian3.fromDegrees(sat.lon, sat.lat, SAT_ALTITUDE);
      const isSelected = sat.id === selectedId;
      const baseSize = STATUS_PIXEL_SIZE[sat.status] || 6;

      const point = satPointCollection.add({
        position: pos,
        pixelSize: isSelected ? baseSize + 4 : baseSize,
        color: color,
        outlineColor: isSelected ? Cesium.Color.WHITE.withAlpha(0.7)
          : (sat.status === 'EVADING' ? Cesium.Color.fromCssColorString('#9b59b6').withAlpha(0.5)
          : Cesium.Color.TRANSPARENT),
        outlineWidth: isSelected ? 3 : (sat.status === 'EVADING' ? 3 : 0),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        id: sat.id,
      });

      satIdMap[sat.id] = { index: idx, sat, position: pos, point };

      // Orbit trails — ONLY for selected satellite
      if (sat.id === selectedId) {
        addOrbitTrail(sat);
      }
    });
  }

  // ── Orbit Trail ──────────────────────────────────────────────────────────
  function addOrbitTrail(sat) {
    const points = [];
    const numPoints = 48;
    const baseLon = sat.lon;
    const inclination = 30 + (sat.id.charCodeAt(4) % 60);

    for (let i = 0; i <= numPoints; i++) {
      const angle = (i / numPoints) * 360;
      const lonOffset = angle - 180;
      const latOffset = inclination * Math.sin(angle * Math.PI / 180) * 0.7;
      const adjustedLon = ((baseLon + lonOffset + 180) % 360) - 180;
      const adjustedLat = Math.max(-85, Math.min(85, latOffset));
      points.push(Cesium.Cartesian3.fromDegrees(adjustedLon, adjustedLat, SAT_ALTITUDE));
    }

    const color = STATUS_COLORS[sat.status] || STATUS_COLORS.NOMINAL;
    orbitLines.add({
      positions: points,
      width: 1.0,
      material: Cesium.Material.fromType('Color', {
        color: color.withAlpha(0.12),
      }),
    });
  }

  // ── Update Debris Cloud — PERFORMANCE FIX ────────────────────────────────
  // Only show a subset of debris (1 in 3) to reduce GPU load
  function updateDebris(debrisCloud) {
    if (!isInitialized) return;
    const SUBSAMPLE = 3; // show every 3rd debris particle (increased visibility)
    const displayLen = Math.ceil(debrisCloud.length / SUBSAMPLE);

    // Fast path: if counts match, update in place
    if (debrisPointCollection.length === displayLen) {
      for (let i = 0; i < displayLen; i++) {
        const deb = debrisCloud[i * SUBSAMPLE];
        const p = debrisPointCollection.get(i);
        p.position = Cesium.Cartesian3.fromDegrees(deb[2], deb[1], deb[3] * 1000);
        p.color = Cesium.Color.fromCssColorString('rgba(255, 51, 51, 1.0)');  // Bright red
        p.outlineColor = Cesium.Color.fromCssColorString('rgba(255, 0, 0, 0.8)');
      }
      return;
    }

    // Slow path: rebuild
    debrisPointCollection.removeAll();
    for (let i = 0; i < debrisCloud.length; i += SUBSAMPLE) {
      const deb = debrisCloud[i];
      debrisPointCollection.add({
        position: Cesium.Cartesian3.fromDegrees(deb[2], deb[1], deb[3] * 1000),
        pixelSize: 4.0,
        color: Cesium.Color.fromCssColorString('rgba(255, 51, 51, 1.0)'),  // Bright red
        outlineColor: Cesium.Color.fromCssColorString('rgba(255, 0, 0, 0.8)'),
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      });
    }
  }

  // ── Update Conjunction Lines ─────────────────────────────────────────────
  function updateConjunctions(cdms) {
    if (!isInitialized) return;
    conjunctionLines.removeAll();

    // Only draw lines for top 10 most critical CDMs
    const critical = [...cdms]
      .sort((a, b) => a.missDistance - b.missDistance)
      .slice(0, 10);

    critical.forEach(cdm => {
      const satData = satIdMap[cdm.satelliteId];
      if (!satData) return;

      const sat = satData.sat;
      const debLon = sat.lon + (Math.random() - 0.5) * 20;
      const debLat = sat.lat + (Math.random() - 0.5) * 15;
      const debPos = Cesium.Cartesian3.fromDegrees(debLon, debLat, SAT_ALTITUDE + (Math.random() - 0.5) * 200_000);

      const isCritical = cdm.missDistance < 0.1;
      const color = isCritical
        ? Cesium.Color.fromCssColorString('#e74c3c').withAlpha(0.8)
        : Cesium.Color.fromCssColorString('#f39c12').withAlpha(0.5);

      conjunctionLines.add({
        positions: [satData.position, debPos],
        width: isCritical ? 2.5 : 1.5,
        material: Cesium.Material.fromType('PolylineDash', {
          color: color,
          dashLength: isCritical ? 12 : 20,
          dashPattern: 255,
        }),
      });
    });
  }

  // ── Pick Satellite ───────────────────────────────────────────────────────
  function pickSatellite(windowPosition) {
    if (!viewer) return null;

    const picked = viewer.scene.pick(windowPosition);
    if (picked && picked.primitive && picked.primitive.id) {
      const id = picked.primitive.id;
      if (typeof id === 'string' && id.startsWith('SAT-')) {
        return satIdMap[id]?.sat || null;
      }
    }
    return null;
  }

  // ── Tooltip ──────────────────────────────────────────────────────────────
  function showTooltip(sat, position) {
    if (!tooltipEl) return;
    tooltipEl.querySelector('.sat-id').textContent = sat.id;
    const fields = tooltipEl.querySelectorAll('.sat-field .value');

    const statusColors = { NOMINAL: '#2ecc71', EVADING: '#9b59b6', EOL: '#e74c3c', RECOVERING: '#1abc9c' };

    fields[0].textContent = sat.status;
    fields[0].style.color = statusColors[sat.status] || '#c8dff0';
    fields[1].textContent = `${sat.fuel_kg.toFixed(1)} kg (${((sat.fuel_kg / 50) * 100).toFixed(0)}%)`;
    fields[2].textContent = '—';

    const container = document.getElementById('globe-panel');
    const bounds = container?.getBoundingClientRect() || { width: 800, height: 600 };
    let x = position.x + 20;
    let y = position.y - 40;
    if (x + 220 > bounds.width) x = position.x - 230;
    if (y < 0) y = position.y + 20;

    tooltipEl.style.left = x + 'px';
    tooltipEl.style.top = y + 'px';
    tooltipEl.classList.add('visible');
  }

  function hideTooltip() {
    if (tooltipEl) tooltipEl.classList.remove('visible');
  }

  // ── Context Menu ─────────────────────────────────────────────────────────
  function showContextMenu(position, sat) {
    const menu = document.getElementById('context-menu');
    if (!menu) return;

    const container = document.getElementById('map-panel');
    const bounds = container?.getBoundingClientRect() || { left: 0, top: 0 };

    menu.style.left = (bounds.left + position.x) + 'px';
    menu.style.top = (bounds.top + position.y) + 'px';
    menu.classList.add('visible');
    menu._targetSat = sat;
  }

  function hideContextMenu() {
    const menu = document.getElementById('context-menu');
    if (menu) menu.classList.remove('visible');
  }

  // ── FIX: Fly To Satellite — Center satellite in viewport ───────────────
  function flyToSatellite(sat) {
    if (!viewer) return;
    stopAutoRotate();
    userInteracting = true;

    // FIX: Camera positioned directly above the satellite at a comfortable
    // distance with a steep look-down angle centered on the satellite.
    // The satellite is placed at CENTER of the view (pitch -85° near-vertical)
    const viewDistance = 4_000_000; // 4,000 km above satellite
    const dest = Cesium.Cartesian3.fromDegrees(sat.lon, sat.lat, SAT_ALTITUDE + viewDistance);

    viewer.camera.flyTo({
      destination: dest,
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-85), // near-vertical look-down — satellite at center
        roll: 0,
      },
      duration: 1.5,
      easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT,
      complete: () => {
        clearTimeout(interactionTimeout);
        interactionTimeout = setTimeout(() => {
          userInteracting = false;
          startAutoRotate();
        }, 10000); // 10s before auto-rotate resumes
      },
    });
  }

  function flyToSatelliteById(satId) {
    const data = satIdMap[satId];
    if (data) flyToSatellite(data.sat);
  }

  // ── Auto Rotate — PERFORMANCE FIX ──────────────────────────────────────
  function startAutoRotate() {
    if (autoRotateHandler || userInteracting) return;
    autoRotateHandler = viewer.clock.onTick.addEventListener(() => {
      if (!userInteracting) {
        // Simple constant-speed rotation — avoid delta-time jitter
        viewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, Cesium.Math.toRadians(0.008));
      }
    });
  }

  function stopAutoRotate() {
    if (autoRotateHandler) {
      autoRotateHandler();
      autoRotateHandler = null;
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────
  return {
    init,
    updateSatellites,
    updateDebris,
    updateConjunctions,
    flyToSatelliteById,
    hideContextMenu,
  };
})();
