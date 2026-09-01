"""The small terminal-end symbol drawn at a tap's outward stub end,
shared by every horizontal-bus drawer (single_bus/main_and_transfer/
breaker_and_half) and ring_bus alike -- kept in one place so "what a
line tap looks like" only has one definition.

Line tap = filled arrowhead (points off the strip, "power leaves here").
Feeder tap = hollow triangle (visually distinct load-side termination).
Transformer tap = no arrow at all -- draw_transformer.py's elbow
connector attaches directly to the bare point instead.
"""

from ..topology import TapKind
from .svg_primitives import svg_polygon, svg_circle

_SIZE = 10


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
