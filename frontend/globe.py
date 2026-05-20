import numpy as np
import moderngl as mgl
from PIL import Image
from .shaders import GLOBE_VERT, GLOBE_FRAG, ATMO_VERT, ATMO_FRAG

SCALE = 1.0 / 1000.0
EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS = EARTH_RADIUS_KM * SCALE


def uv_sphere(radius, sectors=48, rings=24):
    verts, uvs, norms, idx = [], [], [], []
    for r in range(rings + 1):
        phi = r * np.pi / rings
        for s in range(sectors + 1):
            theta = s * 2.0 * np.pi / sectors
            x = radius * np.sin(phi) * np.cos(theta)
            z = radius * np.cos(phi)
            y = radius * np.sin(phi) * np.sin(theta)
            verts.extend([x, y, z])
            uvs.extend([s / sectors, r / rings])
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
    return verts, uvs, norms, idx


CONTINENTS = [
    (25, 50, -130, -70, (35, 65, 30)),
    (50, 72, -170, -130, (35, 55, 25)),
    (10, 25, -110, -80, (30, 60, 25)),
    (-56, 10, -82, -34, (30, 65, 25)),
    (35, 60, -10, 42, (40, 60, 30)),
    (-36, 37, -20, 52, (45, 60, 25)),
    (5, 75, 42, 150, (35, 55, 25)),
    (-42, -10, 112, 156, (50, 55, 25)),
    (-80, -60, -80, -20, (55, 60, 30)),
]


def _in_continent(lat, lon):
    for lat_min, lat_max, lon_min, lon_max, _ in CONTINENTS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return True
    return False


def create_earth_texture(width=1024, height=512):
    img = Image.new('RGB', (width, height))
    px = img.load()
    for y in range(height):
        lat = 90.0 - (y / height) * 180.0
        for x in range(width):
            lon = (x / width) * 360.0 - 180.0
            is_land = _in_continent(lat, lon)
            if is_land:
                r, g, b = 20, 40, 25
            else:
                depth = (lat + 90) / 180
                r = int(5 + depth * 8)
                g = int(12 + depth * 12)
                b = int(30 + depth * 20)
            lat_grid = abs(lat % 15) < 0.6
            lon_grid = abs(lon % 15) < 0.6
            if lat_grid or lon_grid:
                r = min(255, r + 18)
                g = min(255, g + 28)
                b = min(255, b + 42)
            if abs(lat) < 0.3:
                r, g, b = 30, 70, 110
            px[x, y] = (r, g, b)
    return img


def make_vao(ctx, prog, verts, uvs, norms, idx, has_uv=True):
    data = []
    for i in range(len(verts) // 3):
        data.extend([verts[i * 3], verts[i * 3 + 1], verts[i * 3 + 2]])
        if has_uv:
            data.extend([uvs[i * 2], uvs[i * 2 + 1]])
        data.extend([norms[i * 3], norms[i * 3 + 1], norms[i * 3 + 2]])
    vbo = ctx.buffer(np.array(data, dtype=np.float32).tobytes())
    ibo = ctx.buffer(np.array(idx, dtype=np.uint32).tobytes())
    if has_uv:
        vao = ctx.vertex_array(prog, [(vbo, '3f 2f 3f', 'in_position', 'in_uv', 'in_normal')], ibo)
    else:
        vao = ctx.vertex_array(prog, [(vbo, '3f 3f', 'in_position', 'in_normal')], ibo)
    return vao, len(idx)


class Globe:
    def __init__(self, ctx):
        self.ctx = ctx
        self.globe_prog = ctx.program(vertex_shader=GLOBE_VERT, fragment_shader=GLOBE_FRAG)
        self.atmo_prog = ctx.program(vertex_shader=ATMO_VERT, fragment_shader=ATMO_FRAG)

        v, u, n, idx = uv_sphere(EARTH_RADIUS, 64, 32)
        self.vao, self.idx_count = make_vao(ctx, self.globe_prog, v, u, n, idx)

        v2, _, n2, idx2 = uv_sphere(EARTH_RADIUS * 1.025, 32, 16)
        self.atmo_vao, self.atmo_count = make_vao(ctx, self.atmo_prog, v2, [], n2, idx2, has_uv=False)

        img = create_earth_texture()
        self.texture = ctx.texture(img.size, 3, img.tobytes())
        self.texture.build_mipmaps()

        self.light_dir = np.array([0.4, -0.2, 1.0], dtype=np.float32)
        self.light_dir /= np.linalg.norm(self.light_dir)

    def render(self, proj, view, view_pos=None, globe_angle=0.0):
        if view_pos is None:
            view_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        ct, st = np.cos(globe_angle), np.sin(globe_angle)
        model = np.array([
            [ct, -st, 0, 0],
            [st, ct, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)
        mvp = (proj @ view @ model).astype(np.float32)
        view_pos_arr = np.array(view_pos, dtype=np.float32)

        p = self.globe_prog
        p['u_mvp'].write(mvp.tobytes())
        p['u_model'].write(model.tobytes())
        p['u_texture'] = 0
        p['u_light_dir'].write(self.light_dir.tobytes())
        p['u_view_pos'].write(view_pos_arr.tobytes())
        self.texture.use(0)

        self.ctx.enable(mgl.DEPTH_TEST)
        self.ctx.disable(mgl.BLEND)
        self.vao.render(mgl.TRIANGLES)

        self.ctx.enable(mgl.BLEND)
        self.ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
        gl_model = np.array([
            [ct, -st, 0, 0],
            [st, ct, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=np.float32)
        ap = self.atmo_prog
        ap['u_mvp'].write(mvp.tobytes())
        ap['u_model'].write(gl_model.tobytes())
        ap['u_view_pos'].write(view_pos_arr.tobytes())
        self.atmo_vao.render(mgl.TRIANGLES)
