"""
Python-based RK4 + J2 fallback propagator for when the C++ module is unavailable.
"""

import math
from .constants import MU, RE, J2

def accel_py(r):
    x, y, z = r
    r2 = x*x + y*y + z*z
    rm = math.sqrt(r2)
    r3 = r2 * rm
    r5 = r3 * r2
    grav = -MU / r3
    j2f  = 1.5 * J2 * MU * RE * RE / r5
    z2r2 = z * z / r2
    return (
        grav*x + j2f*x*(5*z2r2 - 1),
        grav*y + j2f*y*(5*z2r2 - 1),
        grav*z + j2f*z*(5*z2r2 - 3),
    )

def rk4_py(state, dt):
    def deriv(s):
        a = accel_py(s[:3])
        return (s[3], s[4], s[5], a[0], a[1], a[2])
    k1 = deriv(state)
    s2 = tuple(state[i] + 0.5*dt*k1[i] for i in range(6))
    k2 = deriv(s2)
    s3 = tuple(state[i] + 0.5*dt*k2[i] for i in range(6))
    k3 = deriv(s3)
    s4 = tuple(state[i] + dt*k3[i] for i in range(6))
    k4 = deriv(s4)
    return tuple(state[i] + (dt/6)*(k1[i]+2*k2[i]+2*k3[i]+k4[i]) for i in range(6))
