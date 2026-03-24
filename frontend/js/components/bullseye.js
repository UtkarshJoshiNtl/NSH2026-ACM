/**
 * bullseye.js — Polar conjunction risk plot for a selected satellite
 */

import { getEl } from '../utils/dom.js';

let bullseyeCanvas, bCtx;

export function initBullseye(canvasId) {
    bullseyeCanvas = getEl(canvasId);
    if (!bullseyeCanvas) return;
    bCtx = bullseyeCanvas.getContext('2d');
}

export function renderBullseye(data, selectedSatId) {
    if (!bullseyeCanvas || !bCtx) return;

    const W = bullseyeCanvas.width = bullseyeCanvas.clientWidth;
    const H = bullseyeCanvas.height = bullseyeCanvas.clientHeight;
    const cx = W / 2, cy = H / 2;
    const maxR = Math.min(cx, cy) - 30;

    // Background
    bCtx.fillStyle = '#050b14';
    bCtx.fillRect(0, 0, W, H);

    // Risk rings
    const rings = [
        { r: maxR * 0.33, color: '#f85149', label: '< 100m CRITICAL' },
        { r: maxR * 0.66, color: '#e3b341', label: '< 1km WARNING' },
        { r: maxR, color: '#58a6ff', label: '< 5km WATCH' },
    ];
    rings.forEach(ring => {
        bCtx.strokeStyle = ring.color + '44';
        bCtx.lineWidth = 1;
        bCtx.beginPath(); bCtx.arc(cx, cy, ring.r, 0, Math.PI * 2); bCtx.stroke();
        bCtx.fillStyle = ring.color + '66';
        bCtx.font = '8px JetBrains Mono';
        bCtx.fillText(ring.label, cx + 5, cy - ring.r + 12);
    });

    // Cross-hairs
    bCtx.strokeStyle = '#1e2730'; bCtx.lineWidth = 1;
    bCtx.beginPath(); bCtx.moveTo(cx, cy - maxR - 5); bCtx.lineTo(cx, cy + maxR + 5); bCtx.stroke();
    bCtx.beginPath(); bCtx.moveTo(cx - maxR - 5, cy); bCtx.lineTo(cx + maxR + 5, cy); bCtx.stroke();

    // Centre satellite dot
    bCtx.fillStyle = '#f0a500';
    bCtx.beginPath(); bCtx.arc(cx, cy, 7, 0, Math.PI * 2); bCtx.fill();
    if (selectedSatId) {
        bCtx.fillStyle = '#cdd9e5'; bCtx.font = '9px JetBrains Mono';
        bCtx.fillText(selectedSatId, cx + 10, cy - 5);
    }

    if (!selectedSatId || !data) return;

    // Plot CDMs for selected satellite
    const myCdms = (data.active_cdms || []).filter(c => c.sat_id === selectedSatId);
    const simNow = data.timestamp;
    const horizon = 86400; // 24h

    myCdms.forEach((cdm, i) => {
        const angle = i * 2.399963 - Math.PI / 2;
        const tcaOffset = Math.max(0, (cdm.tca_s || simNow + 3600) - simNow);
        const r = Math.min(cdm.distance_km < 0.1 ? maxR * 0.2
            : cdm.distance_km < 1.0 ? maxR * 0.55
                : maxR * 0.85, maxR - 5);

        const px = cx + Math.cos(angle) * r;
        const py = cy + Math.sin(angle) * r;

        const dot = cdm.severity === 'CRITICAL' ? '#f85149'
            : cdm.severity === 'WARNING' ? '#e3b341'
                : '#58a6ff';

        const g = bCtx.createRadialGradient(px, py, 0, px, py, 12);
        g.addColorStop(0, dot + 'aa'); g.addColorStop(1, 'transparent');
        bCtx.fillStyle = g;
        bCtx.beginPath(); bCtx.arc(px, py, 12, 0, Math.PI * 2); bCtx.fill();

        bCtx.fillStyle = dot;
        bCtx.beginPath(); bCtx.arc(px, py, 5, 0, Math.PI * 2); bCtx.fill();

        bCtx.fillStyle = '#cdd9e5'; bCtx.font = '7px JetBrains Mono';
        bCtx.fillText(`${cdm.distance_km.toFixed(3)}km`, px + 7, py + 4);
    });

    if (myCdms.length === 0) {
        bCtx.fillStyle = '#3fb950aa'; bCtx.font = '11px JetBrains Mono';
        bCtx.textAlign = 'center';
        bCtx.fillText('NO ACTIVE THREATS', cx, cy + maxR + 22);
        bCtx.textAlign = 'left';
    }
}
