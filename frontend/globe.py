import numpy as np
import moderngl as mgl
from PIL import Image
from .shaders import GLOBE_VERT, GLOBE_FRAG, ATMO_VERT, ATMO_FRAG

SCALE = 1.0 / 1000.0
EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS = EARTH_RADIUS_KM * SCALE

# Earth sidereal rotation rate (rad/s)
EARTH_OMEGA = 7.2921150e-5  # rad/s


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


# ---------------------------------------------------------------------------
# Land mask: list of (lat_min, lat_max, lon_min, lon_max, region_key) tuples
# Region keys drive biome colour selection.
# ---------------------------------------------------------------------------
_LAND_PATCHES = [
    # ---- North America ----
    (24, 49, -125, -66, "temperate"),    # contiguous US
    (49, 70, -141, -52, "boreal"),       # Canada
    (14, 24, -118, -77, "tropical"),     # Mexico / Central America
    (60, 84, -57, -17, "arctic"),        # Greenland

    # ---- South America ----
    (-5,  13, -82, -34, "tropical"),     # Amazon basin / north
    (-56,  -5, -82, -34, "temperate"),   # Patagonia / south

    # ---- Europe ----
    (35, 72, -12, 35, "temperate"),      # continental
    (60, 72,   5, 32, "boreal"),         # Scandinavia extension

    # ---- Africa ----
    (-36, 38, -18, 52, "mixed_africa"),  # whole continent

    # ---- Middle East / Arabia ----
    (12, 38,  36, 60, "desert"),

    # ---- Asia ----
    (0,  78,  26, 145, "mixed_asia"),    # Eurasia main block
    (8,  25, 100, 122, "tropical"),      # SE Asian peninsula
    (-8,   8,  95, 142, "tropical"),     # Indonesian archipelago
    (30, 46, 130, 146, "temperate"),     # Japan

    # ---- Oceania ----
    (-44, -10, 113, 155, "mixed_aus"),   # Australia
    (-47, -41, 164, 170, "temperate"),   # New Zealand

    # ---- Antarctica ----
    (-90, -60, -180, 180, "arctic"),
]


def _land_region(lat, lon):
    """Return region key if (lat, lon) is land, else None."""
    for lat_min, lat_max, lon_min, lon_max, region in _LAND_PATCHES:
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return region
    return None


def _biome_color(region, lat, lon):
    """Return (r, g, b) land biome colour."""
    lat_abs = abs(lat)
    if region == "arctic":
        return (210, 215, 220)
    if region == "boreal":
        return (48, 78, 50)
    if region == "tropical":
        return (28, 95, 38)
    if region == "desert":
        return (175, 138, 72)
    if region == "temperate":
        if lat_abs > 55:
            return (55, 85, 52)
        return (42, 88, 44)
    if region == "mixed_africa":
        if lat_abs < 10:
            return (28, 95, 38)   # tropical rainforest
        if lat_abs < 22:
            return (130, 115, 55) # sahel / savanna
        if lat_abs < 32:
            return (170, 130, 65) # Sahara / Kalahari
        return (55, 90, 48)       # south African temperate
    if region == "mixed_asia":
        if lat > 60:
            return (58, 82, 55)   # Siberian boreal
        if lat < 20:
            return (28, 95, 38)   # tropical south Asia
        if 30 < lat < 50 and 80 < lon < 120:
            return (42, 88, 44)   # temperate China
        return (48, 80, 46)
    if region == "mixed_aus":
        if lat > -25:
            return (168, 128, 62) # red-sand interior
        return (58, 95, 50)       # southern temperate fringe
    return (42, 88, 44)


def create_earth_texture(width=2048, height=1024):
    img = Image.new('RGB', (width, height))
    px = img.load()

    for y in range(height):
        lat = 90.0 - (y / height) * 180.0
        lat_abs = abs(lat)

        for x in range(width):
            lon = (x / width) * 360.0 - 180.0

            # ---- Ocean base ----
            # Deep blue at equator, slightly lighter toward poles
            t = lat_abs / 90.0
            r = int(4  + t * 12)
            g = int(14 + t * 22)
            b = int(52 + t * 28)

            # ---- Polar ice ----
            if lat_abs > 68:
                blend = min(1.0, (lat_abs - 68) / 10.0)
                r = int(r + (210 - r) * blend)
                g = int(g + (218 - g) * blend)
                b = int(b + (228 - b) * blend)

            # ---- Land ----
            region = _land_region(lat, lon)
            if region is not None:
                lr, lg, lb = _biome_color(region, lat, lon)
                # Polar ice override on land
                if lat_abs > 68:
                    blend = min(1.0, (lat_abs - 68) / 10.0)
                    lr = int(lr + (218 - lr) * blend)
                    lg = int(lg + (225 - lg) * blend)
                    lb = int(lb + (235 - lb) * blend)
                r, g, b = lr, lg, lb

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
        self.atmo_prog  = ctx.program(vertex_shader=ATMO_VERT,  fragment_shader=ATMO_FRAG)

        v, u, n, idx = uv_sphere(EARTH_RADIUS, 64, 32)
        self.vao, self.idx_count = make_vao(ctx, self.globe_prog, v, u, n, idx)

        v2, _, n2, idx2 = uv_sphere(EARTH_RADIUS * 1.028, 32, 16)
        self.atmo_vao, self.atmo_count = make_vao(ctx, self.atmo_prog, v2, [], n2, idx2, has_uv=False)

        print("[Globe] Generating Earth texture…")
        img = create_earth_texture()
        self.texture = ctx.texture(img.size, 3, img.tobytes())
        self.texture.build_mipmaps()
        self.texture.filter = mgl.LINEAR_MIPMAP_LINEAR, mgl.LINEAR

        self.light_dir = np.array([0.8, 0.3, 0.6], dtype=np.float32)
        self.light_dir /= np.linalg.norm(self.light_dir)

    def render(self, proj, view, view_pos=None, globe_angle=0.0):
        if view_pos is None:
            view_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        ct, st = np.cos(globe_angle), np.sin(globe_angle)
        model = np.array([
            [ct, -st, 0, 0],
            [st,  ct, 0, 0],
            [0,   0,  1, 0],
            [0,   0,  0, 1],
        ], dtype=np.float32)
        mvp          = (proj @ view @ model).astype(np.float32)
        view_pos_arr = np.array(view_pos, dtype=np.float32)

        p = self.globe_prog
        p['u_mvp'].write(mvp.T.tobytes())
        p['u_model'].write(model.T.tobytes())
        p['u_texture']   = 0
        p['u_light_dir'].write(self.light_dir.tobytes())
        p['u_view_pos'].write(view_pos_arr.tobytes())
        self.texture.use(0)

        self.ctx.enable(mgl.DEPTH_TEST)
        self.ctx.disable(mgl.BLEND)
        self.vao.render(mgl.TRIANGLES)

        self.ctx.enable(mgl.BLEND)
        self.ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
        ap = self.atmo_prog
        ap['u_mvp'].write(mvp.T.tobytes())
        ap['u_model'].write(model.T.tobytes())
        ap['u_view_pos'].write(view_pos_arr.tobytes())
        self.atmo_vao.render(mgl.TRIANGLES)
