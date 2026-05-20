import sys
import math
import traceback
from datetime import datetime, timedelta

import numpy as np
import moderngl as mgl

from .shaders import TRAIL_VERT, TRAIL_FRAG, DOT_VERT, DOT_FRAG, SOLID_VERT, SOLID_FRAG
from .globe import SCALE

HERE = __file__
ROOT = __import__('pathlib').Path(HERE).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def jd_to_datetime(jd):
    j2000 = 2451545.0
    dt = datetime(2000, 1, 1, 12, 0, 0) + timedelta(days=jd - j2000)
    return dt


def _uv_sphere_small(radius, sectors=16, rings=8):
    verts, norms, idx = [], [], []
    for r in range(rings + 1):
        phi = r * np.pi / rings
        for s in range(sectors + 1):
            theta = s * 2.0 * np.pi / sectors
            x = radius * np.sin(phi) * np.cos(theta)
            z = radius * np.cos(phi)
            y = radius * np.sin(phi) * np.sin(theta)
            verts.extend([x, y, z])
            nx = np.sin(phi) * np.cos(theta)
            nz = np.cos(phi)
            ny = np.sin(phi) * np.sin(theta)
            norms.extend([nx, ny, nz])
    for r in range(rings):
        for s in range(sectors):
            first = r * (sectors + 1) + s
            second = first + sectors + 1
            idx.extend([first, second, first + 1])
            idx.extend([second, second + 1, first + 1])
    return verts, norms, idx


class _TrailRenderer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.prog = ctx.program(vertex_shader=TRAIL_VERT, fragment_shader=TRAIL_FRAG)
        self.dot_prog = ctx.program(vertex_shader=DOT_VERT, fragment_shader=DOT_FRAG)
        self._vbo = None
        self._vao = None
        self._dot_vbo = ctx.buffer(np.zeros(3, dtype=np.float32).tobytes())
        self._dot_vao = ctx.vertex_array(self.dot_prog, [(self._dot_vbo, '3f', 'in_position')])
        self._n = 0

    def build(self, positions_km, flip_alpha=False):
        n = len(positions_km)
        scaled = positions_km * SCALE
        data = np.zeros((n, 4), dtype=np.float32)
        data[:, :3] = scaled
        alphas = np.linspace(0.0, 1.0, n)
        if flip_alpha:
            alphas = alphas[::-1]
        data[:, 3] = alphas
        self._vbo = self.ctx.buffer(data.tobytes())
        self._vao = self.ctx.vertex_array(self.prog, [(self._vbo, '3f 1f', 'in_position', 'in_alpha')])
        self._n = n

    def render(self, proj, view, color):
        if self._vao is None:
            return
        mvp = (proj @ view).astype(np.float32)
        self.prog['u_mvp'].write(mvp.tobytes())
        self.prog['u_color'].write(np.array(color, dtype=np.float32).tobytes())
        self._vao.render(mgl.LINE_STRIP)

    def render_dot(self, proj, view, pos_km, color, size=10.0):
        if pos_km is None:
            return
        pos = np.array(pos_km, dtype=np.float32) * SCALE
        self._dot_vbo.write(pos.tobytes())
        mvp = (proj @ view).astype(np.float32)
        self.dot_prog['u_mvp'].write(mvp.tobytes())
        self.dot_prog['u_size'] = size
        self.dot_prog['u_color'].write(np.array(color, dtype=np.float32).tobytes())
        self._dot_vao.render(mgl.POINTS)

    def destroy(self):
        if self._vbo:
            self._vbo.release()
        if self._vao:
            self._vao.release()
        self._dot_vbo.release()
        self._dot_vao.release()
        self.prog.release()
        self.dot_prog.release()


class _SphereRenderer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.prog = ctx.program(vertex_shader=SOLID_VERT, fragment_shader=SOLID_FRAG)
        v, n, idx = _uv_sphere_small(1.0, 16, 8)
        data = []
        for i in range(len(v) // 3):
            data.extend([v[i * 3], v[i * 3 + 1], v[i * 3 + 2],
                         n[i * 3], n[i * 3 + 1], n[i * 3 + 2]])
        self._vbo = ctx.buffer(np.array(data, dtype=np.float32).tobytes())
        self._ibo = ctx.buffer(np.array(idx, dtype=np.uint32).tobytes())
        self._vao = ctx.vertex_array(self.prog, [
            (self._vbo, '3f 3f', 'in_position', 'in_normal')
        ], self._ibo)
        self._n = len(idx)
        self._light_dir = np.array([0.4, -0.2, 1.0], dtype=np.float32)
        self._light_dir /= np.linalg.norm(self._light_dir)

    def render(self, proj, view, pos_km, color, radius_scene=0.15, alpha=1.0, view_pos=None):
        if view_pos is None:
            view_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        mvp = (proj @ view).astype(np.float32)
        pos = np.array(pos_km, dtype=np.float32) * SCALE
        model = np.array([
            [radius_scene, 0, 0, pos[0]],
            [0, radius_scene, 0, pos[1]],
            [0, 0, radius_scene, pos[2]],
            [0, 0, 0, 1],
        ], dtype=np.float32)
        sp = self.prog
        full_mvp = (proj @ view @ model).astype(np.float32)
        sp['u_mvp'].write(full_mvp.tobytes())
        sp['u_model'].write(model.tobytes())
        sp['u_color'].write(np.array(color, dtype=np.float32).tobytes())
        sp['u_light_dir'].write(self._light_dir.tobytes())
        sp['u_view_pos'].write(np.array(view_pos, dtype=np.float32).tobytes())
        sp['u_alpha'] = alpha
        self._vao.render(mgl.TRIANGLES)

    def destroy(self):
        self._vbo.release()
        self._ibo.release()
        self._vao.release()
        self.prog.release()


def _propagate_sgp4(sat, n_steps, step_s):
    positions, velocities, times = [], [], []
    for i in range(n_steps + 1):
        t = i * step_s
        jd_full = (sat.jdsatepoch + sat.jdsatepochF) + t / 86400.0
        jd_i = int(jd_full)
        jd_f = jd_full - jd_i
        e, r, v = sat.sgp4(jd_i, jd_f)
        if e != 0:
            continue
        positions.append(r)
        velocities.append(v)
        times.append(t)
    return np.array(positions, dtype=np.float64), np.array(velocities, dtype=np.float64), np.array(times, dtype=np.float64)


def _fetch_tle(norad_id):
    from engine.io.data import tle_ingestor
    sats = tle_ingestor.get_satellites(str(norad_id))
    if not sats:
        raise ValueError(f"No TLE data for NORAD {norad_id}")
    return sats[0]


class TrackScene:
    def __init__(self, ctx):
        self.ctx = ctx
        self.tr = _TrailRenderer(ctx)
        self.name = "Track a Satellite"
        self.reset()

    def reset(self):
        self.positions = None
        self.velocities = None
        self.times = None
        self.epoch_dt = None
        self.anim_t = 0.0
        self.speed = 60.0
        self.paused = False
        self.sat_name = ""
        self.norad_id = 25544
        self.error_msg = ""
        self.backend = "SGP4"
        self.period_min = 0.0
        self.n_steps = 0

    def activate(self, norad_id=None):
        if norad_id is not None:
            self.norad_id = norad_id
        self.reset()
        try:
            sd = _fetch_tle(self.norad_id)
            self._from_tle_data(sd)
        except Exception as e:
            self.error_msg = f"{e}"

    def _from_tle_data(self, sd):
        self.sat_name = sd.get('satellite_name', str(self.norad_id))

        from sgp4.api import Satrec
        sat = Satrec.twoline2rv(sd['line1'], sd['line2'])
        self.epoch_dt = jd_to_datetime(sat.jdsatepoch + sat.jdsatepochF)

        line2 = sd['line2']
        mean_motion = float(line2[52:63].strip()) if len(line2) > 52 else 0
        self.period_min = 1440.0 / mean_motion if mean_motion > 0 else 0.0

        n_steps, step_s = 1440, 60
        pos, vel, t = _propagate_sgp4(sat, n_steps, step_s)
        if len(pos) < 2:
            self.error_msg = "Propagation returned no data"
            return

        self.positions = pos.astype(np.float32)
        self.velocities = vel.astype(np.float32)
        self.times = t.astype(np.float32)
        self.n_steps = len(self.positions)
        self.tr.build(self.positions, flip_alpha=False)

    def update(self, dt):
        if self.positions is None or self.paused:
            return
        self.anim_t += dt * self.speed
        if self.anim_t >= self.n_steps:
            self.anim_t = 0.0

    def render(self, proj, view, view_pos=None, elapsed=0.0):
        if self.positions is None:
            return
        self.tr.render(proj, view, (0.3, 0.6, 1.0))
        idx = min(int(self.anim_t), self.n_steps - 1)
        self.tr.render_dot(proj, view, self.positions[idx], (0.5, 0.8, 1.0), 10.0)

    def hud_lines(self):
        if self.error_msg:
            return [self.name, f"Error: {self.error_msg}",
                    "---", "Press 1/2/3 to switch scenes"]
        if self.positions is None:
            return [self.name, "Loading..."]
        idx = min(int(self.anim_t), self.n_steps - 1)
        pos = self.positions[idx]
        vel = self.velocities[idx]
        speed = float(np.linalg.norm(vel))
        t_sec = float(self.times[idx])

        dt = self.epoch_dt + timedelta(seconds=t_sec)
        from engine.geo.frames import eci_to_ecef, ecef_to_geodetic
        ecef = eci_to_ecef(np.asarray(pos), dt)
        lat, lon, alt = ecef_to_geodetic(ecef)

        return [
            self.name,
            f"Satellite: {self.sat_name}",
            f"NORAD: {self.norad_id}",
            f"Backend: {self.backend}",
            "---",
            f"Altitude: {alt:.1f} km",
            f"Lat: {lat*180/np.pi:.3f}°  Lon: {lon*180/np.pi:.3f}°",
            f"Speed: {speed:.2f} km/s",
            f"Period: {self.period_min:.1f} min",
            "---",
            f"Progress: {int(self.anim_t)} / {self.n_steps}",
        ]

    def destroy(self):
        self.tr.destroy()


class CompareScene:
    def __init__(self, ctx):
        self.ctx = ctx
        self.sgp4_tr = _TrailRenderer(ctx)
        self.full_tr = _TrailRenderer(ctx)
        self.name = "Compare Force Models"
        self.reset()

    def reset(self):
        self.sgp4_pos = None
        self.full_pos = None
        self.velocities = None
        self.times = None
        self.epoch_dt = None
        self.anim_t = 0.0
        self.speed = 60.0
        self.paused = False
        self.sat_name = ""
        self.norad_id = 25544
        self.error_msg = ""
        self.has_full = False
        self.n_steps = 0

    def activate(self, norad_id=None):
        if norad_id is not None:
            self.norad_id = norad_id
        self.reset()
        try:
            sd = _fetch_tle(self.norad_id)
            self.sat_name = sd.get('satellite_name', str(self.norad_id))

            from sgp4.api import Satrec
            sat = Satrec.twoline2rv(sd['line1'], sd['line2'])
            self.epoch_dt = jd_to_datetime(sat.jdsatepoch + sat.jdsatepochF)

            n_steps, step_s = 720, 120
            pos, vel, t = _propagate_sgp4(sat, n_steps, step_s)
            if len(pos) < 2:
                self.error_msg = "SGP4 propagation failed"
                return

            self.sgp4_pos = pos.astype(np.float32)
            self.velocities = vel.astype(np.float32)
            self.times = t.astype(np.float32)
            self.n_steps = len(self.sgp4_pos)
            self.sgp4_tr.build(self.sgp4_pos, flip_alpha=False)

            try:
                r0 = (pos[0][0], pos[0][1], pos[0][2])
                v0 = (vel[0][0], vel[0][1], vel[0][2])
                init = [r0 + v0]

                from engine.core.accelerator import propagate_batch_full_history
                hist = propagate_batch_full_history(init, step_s, n_steps)
                self.full_pos = np.array([hist[i][0][:3] for i in range(hist.shape[0])], dtype=np.float32)

                if len(self.full_pos) >= self.n_steps:
                    self.full_pos = self.full_pos[:self.n_steps]
                elif len(self.full_pos) < self.n_steps:
                    pad = np.tile(self.full_pos[-1:], (self.n_steps - len(self.full_pos), 1))
                    self.full_pos = np.concatenate([self.full_pos, pad], axis=0)

                self.full_tr.build(self.full_pos, flip_alpha=False)
                self.has_full = True
            except Exception:
                self.has_full = False

        except Exception as e:
            self.error_msg = f"{e}"

    def update(self, dt):
        if self.sgp4_pos is None or self.paused:
            return
        self.anim_t += dt * self.speed
        if self.anim_t >= self.n_steps:
            self.anim_t = 0.0

    def render(self, proj, view, view_pos=None, elapsed=0.0):
        if self.sgp4_pos is None:
            return
        self.sgp4_tr.render(proj, view, (1.0, 0.55, 0.0))
        idx = min(int(self.anim_t), self.n_steps - 1)
        self.sgp4_tr.render_dot(proj, view, self.sgp4_pos[idx], (1.0, 0.7, 0.2), 8.0)

        if self.has_full and self.full_pos is not None:
            self.full_tr.render(proj, view, (0.2, 0.8, 0.8))
            self.full_tr.render_dot(proj, view, self.full_pos[idx], (0.3, 1.0, 1.0), 8.0)

    def hud_lines(self):
        if self.error_msg:
            return [self.name, f"Error: {self.error_msg}",
                    "---", "Press 1/2/3 to switch scenes"]
        if self.sgp4_pos is None:
            return [self.name, "Loading..."]
        idx = min(int(self.anim_t), self.n_steps - 1)
        p1 = self.sgp4_pos[idx]
        p2 = self.full_pos[idx] if self.has_full and self.full_pos is not None else p1
        diff_km = float(np.linalg.norm(p1 - p2))
        t_sec = float(self.times[idx])

        dt = self.epoch_dt + timedelta(seconds=t_sec)
        from engine.geo.frames import eci_to_ecef, ecef_to_geodetic
        ecef = eci_to_ecef(np.asarray(p1), dt)
        _, _, alt = ecef_to_geodetic(ecef)

        lines = [
            self.name,
            f"Satellite: {self.sat_name}",
            f"NORAD: {self.norad_id}",
            "---",
            f"Alt: {alt:.1f} km",
            f"Divergence: {diff_km:.2f} km",
            f"Progress: {int(self.anim_t)} / {self.n_steps}",
            "---",
        ]
        if self.has_full:
            lines.append("Orange = SGP4  |  Cyan = Full Physics")
        else:
            lines.append("Orange = SGP4  (C++ engine needed for Full)")
        return lines

    def destroy(self):
        self.sgp4_tr.destroy()
        self.full_tr.destroy()


class ConjunctionScene:
    def __init__(self, ctx):
        self.ctx = ctx
        self.tr1 = _TrailRenderer(ctx)
        self.tr2 = _TrailRenderer(ctx)
        self.marker = _SphereRenderer(ctx)
        self.name = "Conjunction Scenario"
        self.reset()

    def reset(self):
        self.pos1 = None
        self.pos2 = None
        self.times = None
        self.anim_t = 0.0
        self.speed = 60.0
        self.paused = False
        self.sat1_name = ""
        self.sat2_name = ""
        self.norad1 = 25544
        self.norad2 = 48274
        self.error_msg = ""
        self.tca_idx = 0
        self.miss_dist = 0.0
        self.n_steps = 0

    def activate(self, id1=None, id2=None):
        if id1 is not None:
            self.norad1 = id1
        if id2 is not None:
            self.norad2 = id2
        self.reset()
        try:
            sd1 = _fetch_tle(self.norad1)
            sd2 = _fetch_tle(self.norad2)
            self.sat1_name = sd1.get('satellite_name', str(self.norad1))
            self.sat2_name = sd2.get('satellite_name', str(self.norad2))

            from sgp4.api import Satrec
            sat1 = Satrec.twoline2rv(sd1['line1'], sd1['line2'])
            sat2 = Satrec.twoline2rv(sd2['line1'], sd2['line2'])

            n_steps, step_s = 1440, 60
            pos1, _, t = _propagate_sgp4(sat1, n_steps, step_s)
            pos2, _, _ = _propagate_sgp4(sat2, n_steps, step_s)

            if len(pos1) < 2 or len(pos2) < 2:
                self.error_msg = "Propagation failed"
                return

            min_len = min(len(pos1), len(pos2))
            pos1, pos2 = pos1[:min_len], pos2[:min_len]
            self.pos1 = pos1.astype(np.float32)
            self.pos2 = pos2.astype(np.float32)
            self.times = t[:min_len].astype(np.float32) if len(t) >= min_len else t.astype(np.float32)
            self.n_steps = min_len

            dists = np.linalg.norm(self.pos1 - self.pos2, axis=1)
            self.tca_idx = int(np.argmin(dists))
            self.miss_dist = float(dists[self.tca_idx])

            self.tr1.build(self.pos1, flip_alpha=True)
            self.tr2.build(self.pos2, flip_alpha=True)

        except Exception as e:
            self.error_msg = f"{e}"

    def update(self, dt):
        if self.pos1 is None or self.paused:
            return
        self.anim_t += dt * self.speed
        if self.anim_t >= self.n_steps:
            self.anim_t = 0.0

    def render(self, proj, view, view_pos=None, elapsed=0.0):
        if self.pos1 is None:
            return

        self.tr1.render(proj, view, (0.3, 0.6, 1.0))
        self.tr2.render(proj, view, (1.0, 0.7, 0.15))

        idx = min(int(self.anim_t), self.n_steps - 1)
        self.tr1.render_dot(proj, view, self.pos1[idx], (0.5, 0.8, 1.0), 8.0)
        self.tr2.render_dot(proj, view, self.pos2[idx], (1.0, 0.85, 0.3), 8.0)

        if self.tca_idx < self.n_steps:
            mid = (self.pos1[self.tca_idx] + self.pos2[self.tca_idx]) * 0.5
            pulse = 0.15 + 0.08 * math.sin(elapsed * 3.0)
            alpha = 0.6 + 0.4 * math.sin(elapsed * 3.0)
            self.marker.render(proj, view, mid, (1.0, 0.15, 0.15), pulse, alpha, view_pos=view_pos)

    def hud_lines(self):
        if self.error_msg:
            return [self.name, f"Error: {self.error_msg}",
                    "---", "Press 1/2/3 to switch scenes"]
        if self.pos1 is None:
            return [self.name, "Loading..."]
        idx = min(int(self.anim_t), self.n_steps - 1)
        d_now = float(np.linalg.norm(self.pos1[idx] - self.pos2[idx]))

        severity = "ADVISORY"
        if self.miss_dist < 1.0:
            severity = "CRITICAL"
        elif self.miss_dist < 10.0:
            severity = "WARNING"

        return [
            self.name,
            f"S1: {self.sat1_name}",
            f"S2: {self.sat2_name}",
            "---",
            f"Miss Distance: {self.miss_dist:.2f} km",
            f"Severity: {severity}",
            f"Current Dist: {d_now:.2f} km",
            f"TCA at step: {self.tca_idx}",
            "---",
            f"Progress: {int(self.anim_t)} / {self.n_steps}",
        ]

    def destroy(self):
        self.tr1.destroy()
        self.tr2.destroy()
        self.marker.destroy()


class SceneManager:
    def __init__(self, ctx, hud):
        self.ctx = ctx
        self.hud = hud
        self.scenes = [
            TrackScene(ctx),
            CompareScene(ctx),
            ConjunctionScene(ctx),
        ]
        self.current = -1
        self._elapsed = 0.0

    def activate(self, idx):
        idx = max(0, min(idx, len(self.scenes) - 1))
        if self.current == idx:
            return
        self.current = idx
        self._elapsed = 0.0
        scene = self.scenes[idx]
        scene.activate()

    def update(self, dt):
        self._elapsed += dt
        if self.current >= 0:
            self.scenes[self.current].update(dt)

    def render(self, proj, view, view_pos=None, elapsed=0.0):
        if self.current >= 0:
            self.scenes[self.current].render(proj, view, view_pos, self._elapsed)

    def get_hud_lines(self):
        if self.current < 0:
            return ["Astrosis Orbital Engine",
                    "Press 1: Track Satellite",
                    "Press 2: Compare Force Models",
                    "Press 3: Conjunction Scenario",
                    "---",
                    "Drag mouse to orbit | Scroll to zoom",
                    "SPACE: pause  |  +/-: speed  |  R: reset cam"]
        scene = self.scenes[self.current]
        lines = scene.hud_lines()
        controls = [
            "",
            f"Speed: {scene.speed:.0f} step/s  {'PAUSED' if scene.paused else 'RUNNING'}",
            "1/2/3: scenes  SPACE: pause  +/-: speed  R: reset",
        ]
        return lines + controls

    def pause_toggle(self):
        if self.current >= 0:
            self.scenes[self.current].paused = not self.scenes[self.current].paused

    def speed_up(self):
        if self.current >= 0:
            self.scenes[self.current].speed = min(self.scenes[self.current].speed * 1.5, 5000.0)

    def speed_down(self):
        if self.current >= 0:
            self.scenes[self.current].speed = max(self.scenes[self.current].speed / 1.5, 1.0)

    def destroy(self):
        for s in self.scenes:
            s.destroy()
