import sys
import math

import glfw
import moderngl as mgl
import numpy as np

from frontend.camera import ArcballCamera
from frontend.globe import Globe, EARTH_OMEGA
from frontend.hud import HUD
from frontend.scene import SceneManager


WIDTH, HEIGHT = 1280, 800
TITLE = "Astrosis — Orbital Mechanics Engine"

# Visual spin multiplier so rotation is perceptible in real time
# 120x sidereal rate → one full rotation ≈ 12 min of wall time
_GLOBE_VISUAL_RATE = EARTH_OMEGA * 120.0


def main():
    if not glfw.init():
        print("Failed to initialize GLFW", file=sys.stderr)
        return 1

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)

    window = glfw.create_window(WIDTH, HEIGHT, TITLE, None, None)
    if not window:
        print("Failed to create GLFW window", file=sys.stderr)
        glfw.terminate()
        return 1

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    ctx = mgl.create_context()
    ctx.enable(mgl.DEPTH_TEST | mgl.BLEND | mgl.PROGRAM_POINT_SIZE)
    ctx.blend_func   = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
    ctx.clear_color  = 0.01, 0.01, 0.03, 1.0

    camera    = ArcballCamera(distance=20.0)
    globe     = Globe(ctx)
    hud       = HUD(ctx, (WIDTH, HEIGHT))
    scene_mgr = SceneManager(ctx, hud)

    mouse_last    = [0.0, 0.0]
    mouse_pressed = False
    fb_w, fb_h    = glfw.get_framebuffer_size(window)
    globe_angle   = 0.0

    def scroll_cb(w, xoff, yoff):
        camera.zoom(yoff)
    glfw.set_scroll_callback(window, scroll_cb)

    def resize_cb(w, ww, wh):
        nonlocal fb_w, fb_h
        fb_w, fb_h = glfw.get_framebuffer_size(window)
        ctx.viewport = (0, 0, fb_w, fb_h)
        hud.viewport = (fb_w, fb_h)
    glfw.set_framebuffer_size_callback(window, resize_cb)

    def key_cb(w, key, scancode, action, mods):
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(w, True)
        elif key == glfw.KEY_1:
            scene_mgr.activate(0)
        elif key == glfw.KEY_2:
            scene_mgr.activate(1)
        elif key == glfw.KEY_3:
            scene_mgr.activate(2)
        elif key == glfw.KEY_SPACE:
            scene_mgr.pause_toggle()
        elif key in (glfw.KEY_EQUAL, glfw.KEY_KP_ADD):
            scene_mgr.speed_up()
        elif key in (glfw.KEY_MINUS, glfw.KEY_KP_SUBTRACT):
            scene_mgr.speed_down()
        elif key == glfw.KEY_R:
            camera.reset()
    glfw.set_key_callback(window, key_cb)

    scene_mgr.activate(0)

    prev_time = glfw.get_time()

    while not glfw.window_should_close(window):
        curr_time = glfw.get_time()
        dt        = min(curr_time - prev_time, 0.1)
        prev_time = curr_time

        # Globe auto-rotation (visually accelerated sidereal rate)
        globe_angle += _GLOBE_VISUAL_RATE * dt

        x, y = glfw.get_cursor_pos(window)
        if glfw.get_mouse_button(window, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS:
            if not mouse_pressed:
                mouse_pressed = True
                mouse_last    = [x, y]
            else:
                dx, dy = x - mouse_last[0], y - mouse_last[1]
                camera.orbit(dx, dy)
                mouse_last = [x, y]
        else:
            mouse_pressed = False

        scene_mgr.update(dt)

        ctx.clear()
        ctx.viewport = (0, 0, max(fb_w, 1), max(fb_h, 1))
        aspect = max(fb_w, 1) / max(fb_h, 1)

        proj = camera.projection_matrix(aspect)
        view = camera.view_matrix()
        eye  = camera.eye

        hud.render_stars(proj, view)
        globe.render(proj, view, eye, globe_angle)
        scene_mgr.render(proj, view, eye)
        hud.render(scene_mgr.get_hud_lines())

        glfw.swap_buffers(window)
        glfw.poll_events()

    scene_mgr.destroy()
    glfw.terminate()
    return 0


if __name__ == '__main__':
    sys.exit(main())
