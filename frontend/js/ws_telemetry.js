/* ═══════════════════════════════════════════════════════════════════════════
   ORBITAL INSIGHT — WebSocket Telemetry Client
   Real-time data streaming from FastAPI backend.
   ═══════════════════════════════════════════════════════════════════════════ */

const WSTelemetry = (() => {
  let ws = null;
  let reconnectTimer = null;
  let reconnectAttempts = 0;
  const MAX_RECONNECT_DELAY = 10000;
  const BASE_RECONNECT_DELAY = 1000;
  let isConnected = false;
  let onSnapshotCallback = null;
  let onAlertCallback = null;

  // ── Connect ───────────────────────────────────────────────────────────
  function connect(options = {}) {
    const host = options.host || window.location.host;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${host}/ws/telemetry`;

    console.log(`[WS] Connecting to ${url}...`);

    try {
      ws = new WebSocket(url);
    } catch (e) {
      console.warn('[WS] WebSocket creation failed:', e.message);
      _scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      isConnected = true;
      reconnectAttempts = 0;
      console.log('[WS] Connected to telemetry stream');

      // Update connection indicator
      const indicator = document.getElementById('live-indicator');
      if (indicator) {
        indicator.classList.add('connected');
        indicator.title = 'WebSocket: Connected';
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        _handleMessage(msg);
      } catch (e) {
        console.error('[WS] Message parse error:', e);
      }
    };

    ws.onclose = () => {
      isConnected = false;
      console.log('[WS] Disconnected - reconnecting in 2s...');
      // Auto-reconnect after 2 seconds
      setTimeout(connect, 2000);
    };

    ws.onerror = (error) => {
      console.warn('[WS] Connection error — will retry');
    };
  }

  // ── Message Handler ───────────────────────────────────────────────────
  function _handleMessage(msg) {
    switch (msg.type) {
      case 'snapshot':
        if (onSnapshotCallback && msg.data) {
          onSnapshotCallback(msg.data);
        }
        break;

      case 'alert':
        if (onAlertCallback && msg.data) {
          onAlertCallback(msg.data);
        }
        break;

      case 'heartbeat':
        // Connection alive
        break;

      case 'step_complete':
        console.log(`[WS] Sim step complete: ${msg.sim_time}`);
        break;

      case 'maneuver_result':
        console.log('[WS] Maneuver result:', msg.data);
        break;

      case 'threat_injected':
        console.log(`[WS] Threat injected for ${msg.satellite_id}`);
        break;

      default:
        console.log('[WS] Unknown message type:', msg.type);
    }
  }

  // ── Reconnection ──────────────────────────────────────────────────────
  function _scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectAttempts++;
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(1.5, reconnectAttempts),
      MAX_RECONNECT_DELAY
    );
    console.log(`[WS] Reconnecting in ${(delay/1000).toFixed(1)}s (attempt ${reconnectAttempts})`);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  // ── Send Commands ─────────────────────────────────────────────────────
  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }

  function simulateStep(stepSeconds = 60) {
    return send({ type: 'simulate_step', step_seconds: stepSeconds });
  }

  function injectThreat(satelliteId) {
    return send({ type: 'inject_threat', satellite_id: satelliteId });
  }

  function commandManeuver(satelliteId, deltaV) {
    return send({
      type: 'command_maneuver',
      satellite_id: satelliteId,
      delta_v: deltaV,
    });
  }

  // ── Event Handlers ────────────────────────────────────────────────────
  function onSnapshot(callback) {
    onSnapshotCallback = callback;
  }

  function onAlert(callback) {
    onAlertCallback = callback;
  }

  // ── Disconnect ────────────────────────────────────────────────────────
  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    isConnected = false;
  }

  return {
    connect,
    disconnect,
    send,
    simulateStep,
    injectThreat,
    commandManeuver,
    onSnapshot,
    onAlert,
    get connected() { return isConnected; },
  };
})();
