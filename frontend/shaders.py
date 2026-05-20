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
    vec3 normal = normalize(v_normal);
    vec3 light_dir = normalize(u_light_dir);

    float ambient = 0.35;
    float diff = max(dot(normal, light_dir), 0.0);

    vec3 view_dir = normalize(u_view_pos - v_frag_pos);
    vec3 reflect_dir = reflect(-light_dir, normal);
    float spec = pow(max(dot(view_dir, reflect_dir), 0.0), 32.0) * 0.15;

    vec3 result = tex_color * (ambient + diff * 0.65) + vec3(spec);
    frag_color = vec4(result, 1.0);
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
    vec3 normal = normalize(v_normal);
    vec3 view_dir = normalize(u_view_pos - v_frag_pos);
    float fresnel = 1.0 - max(dot(normal, view_dir), 0.0);
    float alpha = pow(fresnel, 3.0) * 0.35;
    frag_color = vec4(0.25, 0.55, 1.0, alpha);
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
    frag_color = vec4(u_color, v_alpha * 0.8);
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
    float alpha = smoothstep(0.5, 0.0, dist);
    frag_color = vec4(u_color, alpha * 0.9);
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

STAR_VERT = """
#version 330 core
in vec3 in_position;

uniform mat4 u_mvp;
uniform float u_size;

void main() {
    gl_Position = u_mvp * vec4(in_position, 1.0);
    gl_PointSize = u_size;
}
"""

STAR_FRAG = """
#version 330 core
out vec4 frag_color;

void main() {
    vec2 coord = gl_PointCoord - vec2(0.5);
    float dist = length(coord);
    if (dist > 0.5) discard;
    float alpha = smoothstep(0.5, 0.0, dist) * 0.8;
    frag_color = vec4(1.0, 1.0, 1.0, alpha);
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
    vec3 normal = normalize(v_normal);
    vec3 light_dir = normalize(u_light_dir);
    float ambient = 0.3;
    float diff = max(dot(normal, light_dir), 0.0);
    vec3 result = u_color * (ambient + diff * 0.7);
    frag_color = vec4(result, u_alpha);
}
"""
