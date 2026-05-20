GLOBE_VERT = """
#version 330 core
in vec3 in_position;
in vec2 in_uv;
in vec3 in_normal;

uniform mat4 u_mvp;
uniform mat4 u_model;

out vec2 v_uv;
out vec3 v_normal;
out vec3 v_frag_pos;

void main() {
    vec4 world_pos = u_model * vec4(in_position, 1.0);
    v_frag_pos = world_pos.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * in_normal;
    v_uv = in_uv;
    gl_Position = u_mvp * vec4(in_position, 1.0);
}
"""

GLOBE_FRAG = """
#version 330 core
in vec2 v_uv;
in vec3 v_normal;
in vec3 v_frag_pos;

uniform sampler2D u_texture;
uniform vec3 u_light_dir;
uniform vec3 u_view_pos;

out vec4 frag_color;

void main() {
    vec3 tex_color = texture(u_texture, v_uv).rgb;
    vec3 normal    = normalize(v_normal);
    vec3 light_dir = normalize(u_light_dir);
    vec3 view_dir  = normalize(u_view_pos - v_frag_pos);

    float diff    = max(dot(normal, light_dir), 0.0);
    float ambient = 0.08;

    // Night-side city-lights hint: very faint warm glow on dark side
    float dark = 1.0 - clamp(diff * 4.0, 0.0, 1.0);
    vec3 night_glow = vec3(0.12, 0.09, 0.04) * dark * 0.35;

    // Specular: ocean pixels (low red, mid-high blue) are shinier
    float ocean_mask = clamp((tex_color.b - tex_color.r) * 3.0, 0.0, 1.0);
    vec3 reflect_dir = reflect(-light_dir, normal);
    float spec_base  = pow(max(dot(view_dir, reflect_dir), 0.0), 64.0);
    float spec       = spec_base * (0.08 + ocean_mask * 0.55);

    // Limb darkening
    float ndotv      = max(dot(normal, view_dir), 0.0);
    float limb       = pow(ndotv, 0.4);

    vec3 result = tex_color * (ambient + diff * 0.92) * limb
                + vec3(spec)
                + night_glow;

    frag_color = vec4(clamp(result, 0.0, 1.0), 1.0);
}
"""

ATMO_VERT = """
#version 330 core
in vec3 in_position;
in vec3 in_normal;

uniform mat4 u_mvp;
uniform mat4 u_model;

out vec3 v_normal;
out vec3 v_frag_pos;

void main() {
    vec4 world_pos = u_model * vec4(in_position, 1.0);
    v_frag_pos = world_pos.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * in_normal;
    gl_Position = u_mvp * vec4(in_position, 1.0);
}
"""

ATMO_FRAG = """
#version 330 core
in vec3 v_normal;
in vec3 v_frag_pos;

uniform vec3 u_view_pos;

out vec4 frag_color;

void main() {
    vec3 normal   = normalize(v_normal);
    vec3 view_dir = normalize(u_view_pos - v_frag_pos);
    float ndotv   = max(dot(normal, view_dir), 0.0);
    float fresnel = 1.0 - ndotv;

    // Two-tone scatter: core is pale blue, rim is deeper violet-blue
    float rim = pow(fresnel, 2.5);
    float core_halo = pow(fresnel, 5.0);
    vec3 scatter_color = mix(vec3(0.28, 0.58, 1.0), vec3(0.12, 0.28, 0.80), rim);
    float alpha = rim * 0.50 + core_halo * 0.20;

    frag_color = vec4(scatter_color, clamp(alpha, 0.0, 0.65));
}
"""

TRAIL_VERT = """
#version 330 core
in vec3 in_position;
in float in_alpha;

uniform mat4 u_mvp;

out float v_alpha;

void main() {
    v_alpha = in_alpha;
    gl_Position = u_mvp * vec4(in_position, 1.0);
}
"""

TRAIL_FRAG = """
#version 330 core
in float v_alpha;

uniform vec3 u_color;

out vec4 frag_color;

void main() {
    frag_color = vec4(u_color, v_alpha * 0.85);
}
"""

DOT_VERT = """
#version 330 core
in vec3 in_position;

uniform mat4 u_mvp;
uniform float u_size;

void main() {
    gl_Position = u_mvp * vec4(in_position, 1.0);
    gl_PointSize = u_size;
}
"""

DOT_FRAG = """
#version 330 core
out vec4 frag_color;

uniform vec3 u_color;

void main() {
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);
    if (dist > 0.5) discard;
    // Bright core + soft halo
    float core  = 1.0 - smoothstep(0.0, 0.18, dist);
    float halo  = smoothstep(0.5, 0.1, dist);
    float alpha = clamp(core * 0.9 + halo * 0.5, 0.0, 1.0);
    vec3 col    = mix(vec3(1.0), u_color, smoothstep(0.0, 0.3, dist));
    frag_color  = vec4(col, alpha);
}
"""

HUD_VERT = """
#version 330 core
in vec2 in_position;
in vec2 in_uv;

out vec2 v_uv;

void main() {
    v_uv = in_uv;
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""

HUD_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;

out vec4 frag_color;

void main() {
    frag_color = texture(u_texture, v_uv);
}
"""

# Stars: per-vertex position (3f) + size (1f) + color (3f)
STAR_VERT = """
#version 330 core
in vec3 in_position;
in float in_size;
in vec3 in_color;

uniform mat4 u_mvp;

out vec3 v_color;

void main() {
    gl_Position  = u_mvp * vec4(in_position, 1.0);
    gl_PointSize = in_size;
    v_color      = in_color;
}
"""

STAR_FRAG = """
#version 330 core
in vec3 v_color;
out vec4 frag_color;

void main() {
    vec2  coord = gl_PointCoord - vec2(0.5);
    float dist  = length(coord);
    if (dist > 0.5) discard;
    // Bright pinpoint core blending to soft halo
    float core  = 1.0 - smoothstep(0.0, 0.15, dist);
    float halo  = smoothstep(0.5, 0.05, dist);
    float alpha = clamp(core * 1.0 + halo * 0.55, 0.0, 1.0) * 0.88;
    vec3  col   = mix(v_color, vec3(1.0), core * 0.6);
    frag_color  = vec4(col, alpha);
}
"""

SOLID_VERT = """
#version 330 core
in vec3 in_position;
in vec3 in_normal;

uniform mat4 u_mvp;
uniform mat4 u_model;

out vec3 v_normal;
out vec3 v_frag_pos;

void main() {
    vec4 world_pos = u_model * vec4(in_position, 1.0);
    v_frag_pos = world_pos.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * in_normal;
    gl_Position = u_mvp * vec4(in_position, 1.0);
}
"""

SOLID_FRAG = """
#version 330 core
in vec3 v_normal;
in vec3 v_frag_pos;

uniform vec3 u_color;
uniform vec3 u_light_dir;
uniform vec3 u_view_pos;
uniform float u_alpha;

out vec4 frag_color;

void main() {
    vec3 normal    = normalize(v_normal);
    vec3 light_dir = normalize(u_light_dir);
    float ambient  = 0.25;
    float diff     = max(dot(normal, light_dir), 0.0);
    // Rim / fresnel glow
    vec3 view_dir  = normalize(u_view_pos - v_frag_pos);
    float rim      = 1.0 - max(dot(normal, view_dir), 0.0);
    rim            = pow(rim, 3.0) * 0.4;
    vec3 result    = u_color * (ambient + diff * 0.75) + u_color * rim;
    frag_color     = vec4(clamp(result, 0.0, 1.0), u_alpha);
}
"""
