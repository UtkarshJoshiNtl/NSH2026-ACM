import numpy as np
import moderngl as mgl
from PIL import Image, ImageDraw, ImageFont
from .shaders import HUD_VERT, HUD_FRAG, STAR_VERT, STAR_FRAG


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
        self.ctx = ctx
        self.viewport = viewport

        self.hud_prog = ctx.program(vertex_shader=HUD_VERT, fragment_shader=HUD_FRAG)
        quad_vbo = ctx.buffer(QUAD.tobytes())
        self.hud_vao = ctx.vertex_array(self.hud_prog, [
            (quad_vbo, '2f 2f', 'in_position', 'in_uv')
        ])

        self.star_prog = ctx.program(vertex_shader=STAR_VERT, fragment_shader=STAR_FRAG)
        stars = self._generate_stars()
        star_vbo = ctx.buffer(stars.tobytes())
        self.star_vao = ctx.vertex_array(self.star_prog, [
            (star_vbo, '3f', 'in_position')
        ])
        self.n_stars = len(stars) // 3

        self.font = ImageFont.load_default()
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        except (OSError, IOError):
            try:
                self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except (OSError, IOError):
                pass

        self._last_text = ""
        self._texture = None

    def _generate_stars(self, n=3000, radius=900):
        np.random.seed(42)
        theta = np.random.uniform(0, 2 * np.pi, n)
        phi = np.arccos(2 * np.random.uniform(0, 1, n) - 1)
        x = radius * np.sin(phi) * np.cos(theta)
        y = radius * np.sin(phi) * np.sin(theta)
        z = radius * np.cos(phi)
        return np.column_stack([x, y, z]).ravel().astype(np.float32)

    def render_stars(self, proj, view):
        mvp = (proj @ view).astype(np.float32)
        p = self.star_prog
        p['u_mvp'].write(mvp.tobytes())
        p['u_size'] = 1.5
        self.ctx.disable(mgl.DEPTH_TEST)
        self.star_vao.render(mgl.POINTS, vertices=self.n_stars)
        self.ctx.enable(mgl.DEPTH_TEST)

    def render(self, lines):
        text = "\n".join(lines) if lines else ""
        if text != self._last_text or self._texture is None:
            self._build_texture(text)
            self._last_text = text

        if self._texture is None:
            return

        self.ctx.disable(mgl.DEPTH_TEST)
        self.ctx.enable(mgl.BLEND)
        self.ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA

        self.hud_prog['u_texture'] = 0
        self._texture.use(0)
        self.hud_vao.render(mgl.TRIANGLES)
        self.ctx.enable(mgl.DEPTH_TEST)

    def _build_texture(self, text):
        pad = 12
        line_h = 20
        lines = text.split("\n")
        w = 440
        h = max(32, len(lines) * line_h + pad * 2 + 20)

        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [0, 0, w - 1, h - 1],
            radius=8,
            fill=(8, 10, 18, 200),
            outline=(60, 80, 120, 80),
        )

        y = pad + 4
        title_rendered = False
        for line in lines:
            if not title_rendered:
                draw.text((pad, y), line, fill=(180, 210, 255, 255), font=self.font)
                y += line_h + 4
                title_rendered = True
                draw.line([(pad, y - 6), (w - pad, y - 6)], fill=(60, 80, 120, 60), width=1)
            else:
                if "---" in line:
                    y += 6
                    draw.line([(pad, y), (w - pad, y)], fill=(60, 80, 120, 40), width=1)
                    y += 8
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    draw.text((pad, y), key + ":", fill=(130, 150, 180, 200), font=self.font)
                    kw = draw.textlength(key + ":", font=self.font)
                    draw.text((pad + kw + 6, y), val.strip(), fill=(210, 230, 255, 230), font=self.font)
                else:
                    draw.text((pad, y), line, fill=(160, 180, 210, 200), font=self.font)
                y += line_h

        if self._texture is not None:
            self._texture.release()
        self._texture = self.ctx.texture(img.size, 4, img.transpose(Image.FLIP_TOP_BOTTOM).tobytes())
