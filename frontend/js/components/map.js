/**
 * map.js — Mercator projection world map + satellite/debris rendering
 */

import { getEl } from '../utils/dom.js';

let mapCanvas, mapCtx;

export function initMap(canvasId) {
    mapCanvas = getEl(canvasId);
    if (!mapCanvas) return;
    mapCtx = mapCanvas.getContext('2d');

    const resize = () => {
        mapCanvas.width = mapCanvas.clientWidth;
        mapCanvas.height = mapCanvas.clientHeight;
    };
    window.addEventListener('resize', resize);
    resize();
}

function toXY(lat, lon, W, H) {
    return {
        x: (lon + 180) / 360 * W,
        y: (90 - lat) / 180 * H,
    };
}

export function renderMap(data) {
    if (!mapCanvas || !mapCtx || !data) return;

    const W = mapCanvas.width = mapCanvas.clientWidth;
    const H = mapCanvas.height = mapCanvas.clientHeight;
    const ctx = mapCtx;

    // Background
    ctx.fillStyle = '#050b14';
    ctx.fillRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = '#0e1822';
    ctx.lineWidth = 0.5;
    for (let lon = -180; lon <= 180; lon += 30) {
        const x = (lon + 180) / 360 * W;
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let lat = -90; lat <= 90; lat += 30) {
        const y = (90 - lat) / 180 * H;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // Equator highlight
    ctx.strokeStyle = '#1a2a3a'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke();

    // Ground stations
    if (data.ground_stations) {
        ctx.strokeStyle = '#3fb950'; ctx.lineWidth = 1.5;
        data.ground_stations.forEach(gs => {
            const { x, y } = toXY(gs.lat_deg, gs.lon_deg, W, H);
            ctx.beginPath();
            ctx.moveTo(x, y - 6); ctx.lineTo(x + 5, y);
            ctx.lineTo(x, y + 6); ctx.lineTo(x - 5, y);
            ctx.closePath(); ctx.stroke();
        });
    }

    // Debris
    const imgData = ctx.getImageData(0, 0, W, H);
    const buf = imgData.data;
    if (data.debris_cloud) {
        data.debris_cloud.forEach(([, lat, lon]) => {
            const { x, y } = toXY(lat, lon, W, H);
            const xi = Math.round(x), yi = Math.round(y);
            if (xi >= 0 && xi < W && yi >= 0 && yi < H) {
                const i = (yi * W + xi) * 4;
                buf[i] = 96; buf[i + 1] = 128; buf[i + 2] = 160; buf[i + 3] = 180;
            }
        });
    }
    ctx.putImageData(imgData, 0, 0);

    // Satellites
    if (data.satellites) {
        data.satellites.forEach(sat => {
            const { x, y } = toXY(sat.lat, sat.lon, W, H);
            const color = sat.status === 'CRITICAL' ? '#f85149'
                : sat.status === 'WARNING' ? '#e3b341'
                    : sat.status === 'EOL' ? '#f0a500'
                        : '#3fb950';

            if (sat.status === 'CRITICAL' || sat.status === 'WARNING') {
                ctx.strokeStyle = color + '55'; ctx.lineWidth = 1;
                ctx.beginPath(); ctx.arc(x, y, 10, 0, Math.PI * 2); ctx.stroke();
            }

            ctx.fillStyle = color;
            ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill();

            ctx.fillStyle = '#cdd9e5'; ctx.font = '8px JetBrains Mono';
            ctx.fillText(sat.id.slice(-4), x + 5, y + 3);
        });
    }

    // CDM lines
    if (data.active_cdms) {
        data.active_cdms.slice(0, 10).forEach(cdm => {
            const sat = data.satellites.find(s => s.id === cdm.sat_id);
            if (!sat) return;
            const { x, y } = toXY(sat.lat, sat.lon, W, H);
            const grad = ctx.createRadialGradient(x, y, 0, x, y, 20);
            grad.addColorStop(0, '#f8514966');
            grad.addColorStop(1, 'transparent');
            ctx.fillStyle = grad;
            ctx.beginPath(); ctx.arc(x, y, 20, 0, Math.PI * 2); ctx.fill();
        });
    }
}
