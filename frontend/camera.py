import numpy as np


def _normalize(v):
    return v / np.linalg.norm(v)


def perspective(fov_y, aspect, z_near, z_far):
    f = 1.0 / np.tan(fov_y * 0.5)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (z_far + z_near) / (z_near - z_far), 2.0 * z_far * z_near / (z_near - z_far)],
        [0, 0, -1.0, 0]
    ], dtype=np.float32)


def look_at(eye, target, up):
    f = _normalize(target - eye)
    s = _normalize(np.cross(f, up))
    u = np.cross(s, f)
    return np.array([
        [s[0], s[1], s[2], -float(np.dot(s, eye))],
        [u[0], u[1], u[2], -float(np.dot(u, eye))],
        [-f[0], -f[1], -f[2], float(np.dot(f, eye))],
        [0, 0, 0, 1]
    ], dtype=np.float32)


class ArcballCamera:
    def __init__(self, distance=20.0, theta=0.0, phi=0.5):
        self.distance = distance
        self.theta = theta
        self.phi = phi
        self.target = np.array([0.0, 0.0, 0.0])

    @property
    def eye(self):
        ct, st = np.cos(self.theta), np.sin(self.theta)
        cp, sp = np.cos(self.phi), np.sin(self.phi)
        return np.array([
            self.distance * cp * ct,
            self.distance * cp * st,
            self.distance * sp
        ])

    def orbit(self, dx, dy):
        self.theta -= dx * 0.005
        self.phi = np.clip(self.phi + dy * 0.005, -np.pi / 2 + 0.02, np.pi / 2 - 0.02)

    def zoom(self, dy):
        self.distance *= (1.0 + dy * 0.1)
        self.distance = np.clip(self.distance, 5.0, 500.0)

    def reset(self):
        self.distance = 20.0
        self.theta = 0.0
        self.phi = 0.5

    def view_matrix(self):
        return look_at(self.eye, self.target, np.array([0.0, 0.0, 1.0]))

    def projection_matrix(self, aspect):
        return perspective(np.pi / 4, aspect, 0.1, 1000.0)
