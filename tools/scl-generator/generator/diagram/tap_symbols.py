"""The small terminal-end symbol drawn at a tap's outward stub end,
shared by every horizontal-bus drawer (single_bus/main_and_transfer/
breaker_and_half) and ring_bus alike -- kept in one place so "what a
line tap looks like" only has one definition.

Line tap = filled arrowhead (points off the strip, "power leaves here").
Feeder tap = hollow triangle (visually distinct load-side termination).
Transformer tap = no arrow at all -- draw_transformer.py's elbow
connector attaches directly to the bare point instead.

`draw_disconnect` is the separate isolator/disconnect-switch symbol
(a short diagonal tick across the conductor, the open-position
convention this tool's reference one-line uses) -- drawn adjacent to
breakers in every strip drawer and at every transformer LV output, never
merged with the breaker symbol itself (a disconnect and a circuit
breaker are two distinct devices in series, same as the reference).
"""

import math

from ..topology import TapKind
from .svg_primitives import svg_polygon, svg_circle, svg_line

_SIZE = 10
_DISCONNECT_SIZE = 7


def draw_disconnect(x: float, y: float, vertical: bool) -> list:
    """A short diagonal tick centered at (x, y), across a vertical
    conductor (`vertical=True`) or a horizontal one (`vertical=False`).
    For a conductor at an arbitrary angle (ring_bus's radial stubs), use
    `draw_disconnect_at` instead.
    """
    if vertical:
        return [svg_line(x - _DISCONNECT_SIZE, y + _DISCONNECT_SIZE,
                          x + _DISCONNECT_SIZE, y - _DISCONNECT_SIZE, stroke="#333", stroke_width=2)]
    return [svg_line(x - _DISCONNECT_SIZE, y - _DISCONNECT_SIZE,
                      x + _DISCONNECT_SIZE, y + _DISCONNECT_SIZE, stroke="#333", stroke_width=2)]


def draw_disconnect_at(x: float, y: float, dx: float, dy: float) -> list:
    """A short tick centered at (x, y), perpendicular to a conductor
    running in direction (dx, dy) -- for a stub at an arbitrary angle
    (ring_bus's radial taps), where a fixed vertical/horizontal tick can
    end up running parallel to the stub itself and disappear.
    """
    length = math.hypot(dx, dy)
    if length == 0:
        return draw_disconnect(x, y, vertical=True)
    px, py = -dy / length, dx / length
    return [svg_line(x - px * _DISCONNECT_SIZE, y - py * _DISCONNECT_SIZE,
                      x + px * _DISCONNECT_SIZE, y + py * _DISCONNECT_SIZE, stroke="#333", stroke_width=2)]


def draw(x: float, y: float, direction_dy: float, kind: TapKind) -> list:
    """`direction_dy` is +1 (symbol points downward/outward below the
    point) or -1 (points upward/outward above it) -- callers pass
    whichever matches their stub's outward direction.
    """
    tip = (x, y + direction_dy * _SIZE * 1.6)
    left = (x - _SIZE * 0.7, y)
    right = (x + _SIZE * 0.7, y)

    if kind == TapKind.LINE:
        return [svg_polygon([tip, left, right], fill="#333")]
    if kind == TapKind.FEEDER:
        return [svg_polygon([tip, left, right], fill="none", stroke="#333", stroke_width=1.5)]
    return [svg_circle(x, y, 3, fill="#333")]
