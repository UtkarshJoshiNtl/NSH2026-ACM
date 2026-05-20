import numpy as np
import moderngl as mgl
from PIL import Image, ImageDraw, ImageFont
from .shaders import HUD_VERT, HUD_FRAG, STAR_VERT, STAR_FRAG


# Placeholder quad — overwritten immediately by _build_texture each frame
QUAD = np.array([
    -1, -1, 0, 0,
     1, -1, 1, 0,
     1,  1, 1, 1,
    -1, -1, 0, 0,
     1,  1, 1, 1,
    -1,  1, 0, 1,
], dtype=np.float32)


class HUD:
    def __init__(self, ctx, viewport=(1280, 800)):
        self.ctx      = ctx
        self.viewport = viewport

        self.hud_prog = ctx.program(vertex_shader=HUD_VERT, fragment_shader=HUD_FRAG)
        self.quad_vbo = ctx.buffer(QUAD.tobytes(), dynamic=True)
        self.hud_vao  = ctx.vertex_array(self.hud_prog, [
            (self.quad_vbo, '2f 2f', 'in_position', 'in_uv')
        ])

        self.star_prog = ctx.program(vertex_shader=STAR_VERT, fragment_shader=STAR_FRAG)
        star_data      = self._generate_stars()
        star_vbo       = ctx.buffer(star_data.tobytes())
        # layout: 3f position, 1f size, 3f color
        self.star_vao  = ctx.vertex_array(self.star_prog, [
            (star_vbo, '3f 1f 3f', 'in_position', 'in_size', 'in_color')
        ])
        # 7 floats per star
        self.n_stars = star_data.size // 7

        # Font loading — prefer a crisp mono font, fall back gracefully
        self.font_sm = ImageFont.load_default()
        self.font_lg = ImageFont.load_default()
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]:
            try:
                self.font_sm = ImageFont.truetype(path, 13)
                self.font_lg = ImageFont.truetype(path, 15)
                break
            except (OSError, IOError):
                pass

        self._last_text     = ""
        self._last_viewport = None
        self._texture       = None

    # ------------------------------------------------------------------
    def _generate_stars(self, n=4000, radius=900):
        rng = np.random.default_rng(42)
        theta = rng.uniform(0, 2 * np.pi, n)
        phi   = np.arccos(2 * rng.uniform(0, 1, n) - 1)
        x = radius * np.sin(phi) * np.cos(theta)
        y = radius * np.sin(phi) * np.sin(theta)
        z = radius * np.cos(phi)

        # 70 % small, 20 % medium, 8 % large, 2 % bright giant
        sizes = rng.choice(
            np.array([1.0, 1.6, 2.2, 3.0], dtype=np.float32), n,
            p=[0.70, 0.20, 0.08, 0.02]
        )

        # Star colour classes: white, warm yellow, cool blue-white, red-orange
        ctype = rng.choice(4, n, p=[0.55, 0.20, 0.18, 0.07])
        palettes = np.array([
            [0.95, 0.96, 1.00],   # white
            [1.00, 0.92, 0.70],   # warm K/G type
            [0.80, 0.90, 1.00],   # cool blue-white B/A
            [1.00, 0.72, 0.52],   # red-orange M type
        ], dtype=np.float32)
        colors = palettes[ctype]   # (n, 3)

        # Interleave: x y z size r g b  → shape (n, 7)
        data = np.column_stack([x, y, z, sizes, colors]).astype(np.float32)
        return data.ravel()

    # ------------------------------------------------------------------
    def render_stars(self, proj, view):
        mvp = (proj @ view).astype(np.float32)
        self.star_prog['u_mvp'].write(mvp.T.tobytes())
        self.ctx.disable(mgl.DEPTH_TEST)
        self.star_vao.render(mgl.POINTS, vertices=self.n_stars)
        self.ctx.enable(mgl.DEPTH_TEST)

    # ------------------------------------------------------------------
    def render(self, lines):
        text = "\n".join(lines) if lines else ""
        rebuild = (text != self._last_text
                   or self.viewport != self._last_viewport
                   or self._texture is None)
        if rebuild:
            self._build_texture(text)
            self._last_text     = text
            self._last_viewport = self.viewport

        if self._texture is None:
            return

        self.ctx.disable(mgl.DEPTH_TEST)
        self.ctx.enable(mgl.BLEND)
        self.ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA

        self.hud_prog['u_texture'] = 0
        self._texture.use(0)
        self.hud_vao.render(mgl.TRIANGLES)
        self.ctx.enable(mgl.DEPTH_TEST)

    # ------------------------------------------------------------------
    def _build_texture(self, text):
        PAD    = 14
        LINE_H = 19
        lines  = text.split("\n")
        W      = 440
        H      = max(40, len(lines) * LINE_H + PAD * 2 + 24)

        # ---- Position the quad in the top-left corner ----------------
        vw, vh = self.viewport
        margin = 18.0
        x1 = margin
        x2 = margin + W
        y1 = vh - margin - H
        y2 = vh - margin

        nx1 = (x1 / vw) * 2.0 - 1.0
        nx2 = (x2 / vw) * 2.0 - 1.0
        ny1 = (y1 / vh) * 2.0 - 1.0
        ny2 = (y2 / vh) * 2.0 - 1.0

        quad = np.array([
            nx1, ny1, 0.0, 0.0,
            nx2, ny1, 1.0, 0.0,
            nx2, ny2, 1.0, 1.0,
            nx1, ny1, 0.0, 0.0,
            nx2, ny2, 1.0, 1.0,
            nx1, ny2, 0.0, 1.0,
        ], dtype=np.float32)
        self.quad_vbo.write(quad.tobytes())

        # ---- Draw the panel image ------------------------------------
        img  = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Panel background with subtle gradient feel via two-pass rect
        draw.rounded_rectangle(
            [0, 0, W - 1, H - 1], radius=10,
            fill=(6, 9, 20, 210), outline=(55, 85, 140, 100),
        )
        # Subtle top highlight line for "glass" feel
        draw.rounded_rectangle(
            [1, 1, W - 2, 12], radius=9,
            fill=(80, 110, 180, 30),
        )

        TITLE_COL  = (170, 210, 255, 255)
        KEY_COL    = (110, 140, 175, 210)
        VAL_COL    = (215, 235, 255, 235)
        BODY_COL   = (155, 180, 215, 210)
        DIV_COL    = (55, 85, 140, 70)

        cy = PAD + 2
        first = True
        for line in lines:
            if first:
                # Title row
                draw.text((PAD, cy), line, fill=TITLE_COL, font=self.font_lg)
                cy += LINE_H + 4
                # Divider under title
                draw.line([(PAD, cy - 3), (W - PAD, cy - 3)],
                          fill=(70, 110, 175, 80), width=1)
                first = False
                continue

            if "---" in line:
                cy += 4
                draw.line([(PAD, cy), (W - PAD, cy)], fill=DIV_COL, width=1)
                cy += 7
                continue

            if ":" in line and not line.strip().startswith("Press"):
                key, val = line.split(":", 1)
                draw.text((PAD, cy), key + ":", fill=KEY_COL, font=self.font_sm)
                kw = draw.textlength(key + ":", font=self.font_sm)
                draw.text((PAD + kw + 6, cy), val.strip(), fill=VAL_COL, font=self.font_sm)
            else:
                draw.text((PAD, cy), line, fill=BODY_COL, font=self.font_sm)

            cy += LINE_H

        # ---- Upload to GPU -------------------------------------------
        if self._texture is not None:
            self._texture.release()
        flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
        self._texture = self.ctx.texture(img.size, 4, flipped.tobytes())
        self._texture.filter = mgl.LINEAR, mgl.LINEAR
