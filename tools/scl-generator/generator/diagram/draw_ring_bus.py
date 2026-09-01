"""One-line diagram drawer for the ring bus layout -- the one deliberate
exception to the other three drawers' horizontal-rail convention: drawn
as an actual circle, breakers at 12 o'clock going clockwise, taps at the
midpoint between their two neighboring breakers, each with a stub
radiating straight outward from the ring.
"""

import math

from ..topology import VoltageLevelBuild
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_circle, svg_line, svg_rect, svg_text

_STUB_LEN = 36


def draw(vl: VoltageLevelBuild, strip_top: float):
    elements = []
    tap_positions = {}

    n = len(vl.taps)
    radius = geo.ring_radius(n)
    center = geo.ring_center(strip_top, radius)

    elements.append(svg_circle(center[0], center[1], radius, fill="none", stroke="#333", stroke_width=3))
    elements.append(svg_text(center[0], strip_top - 6, "%s -- %g kV" % (vl.vl_name, vl.kv),
                              text_anchor="middle", font_size=13, font_weight="bold"))

    for i, breaker in enumerate(vl.breakers):
        angle = geo.ring_breaker_angle(i, n)
        x, y = geo.point_on_circle(center, radius, angle)
        elements.append(svg_rect(x - geo.BREAKER_SIZE / 2, y - geo.BREAKER_SIZE / 2,
                                  geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))
        label_x, label_y = geo.point_on_circle(center, radius + 20, angle)
        elements.append(svg_text(label_x, label_y, breaker.name, text_anchor="middle", font_size=10))

    for i, tap in enumerate(vl.taps):
        node = vl.tap_node_for(tap)
        angle = geo.ring_tap_angle(i, n)
        inner_x, inner_y = geo.point_on_circle(center, radius, angle)
        outer_x, outer_y = geo.point_on_circle(center, radius + _STUB_LEN, angle)

        elements.append(svg_circle(inner_x, inner_y, 3, fill="#333"))
        elements.append(svg_line(inner_x, inner_y, outer_x, outer_y, stroke="#333", stroke_width=2))

        direction = 1 if math.sin(angle) >= 0 else -1
        elements.extend(tap_symbols.draw(outer_x, outer_y, direction, tap.kind))

        label_x, label_y = geo.point_on_circle(center, radius + _STUB_LEN + 26, angle)
        elements.append(svg_text(label_x, label_y, tap.name, text_anchor="middle", font_size=11))

        tap_positions[node] = (outer_x, outer_y)

    return elements, tap_positions
