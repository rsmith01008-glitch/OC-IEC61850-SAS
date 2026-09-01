"""One-line diagram drawer for the ring bus layout -- the one deliberate
exception to the other three drawers' horizontal-rail convention: drawn
as an actual circle, breakers at 12 o'clock going clockwise, taps at the
midpoint between their two neighboring breakers, each with a stub
radiating straight outward from the ring.

Every breaker is flanked by 2 disconnect ticks along the ring arc (one
toward each neighboring tap), matching the real `DIS` devices
generator/layouts/ring_bus.py's `add_isolating_disconnects` adds around
it; a line/feeder tap gets one more disconnect on its own radial exit
stub (`tap_symbols.draw_tap_with_exit` isn't used here since the ring's
outward direction isn't a simple +1/-1 -- see `_draw_tap` below, which
follows the same "transformer tap: no exit switch" rule).
"""

import math

from ..topology import VoltageLevelBuild, TapKind, EQUIP_CBR
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

    breakers = [b for b in vl.breakers if b.equip_type == EQUIP_CBR]
    delta = (2 * math.pi / n) * 0.3
    for i, breaker in enumerate(breakers):
        angle = geo.ring_breaker_angle(i, n)
        x, y = geo.point_on_circle(center, radius, angle)
        elements.append(svg_rect(x - geo.BREAKER_SIZE / 2, y - geo.BREAKER_SIZE / 2,
                                  geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))
        label_x, label_y = geo.point_on_circle(center, radius + 20, angle)
        elements.append(svg_text(label_x, label_y, breaker.name, text_anchor="middle", font_size=10))

        for disc_angle in (angle - delta, angle + delta):
            dx, dy = geo.point_on_circle(center, radius, disc_angle)
            tx, ty = -math.sin(disc_angle), math.cos(disc_angle)  # tangent to the ring
            elements.extend(tap_symbols.draw_disconnect_at(dx, dy, tx, ty))

    for i, tap in enumerate(vl.taps):
        node = vl.tap_node_for(tap)
        angle = geo.ring_tap_angle(i, n)
        inner_x, inner_y = geo.point_on_circle(center, radius, angle)
        outer_x, outer_y = geo.point_on_circle(center, radius + _STUB_LEN, angle)
        direction = 1 if math.sin(angle) >= 0 else -1

        elements.append(svg_circle(inner_x, inner_y, 3, fill="#333"))
        elements.append(svg_line(inner_x, inner_y, outer_x, outer_y, stroke="#333", stroke_width=2))
        _draw_tap(elements, inner_x, inner_y, outer_x, outer_y, direction, tap)

        label_x, label_y = geo.point_on_circle(center, radius + _STUB_LEN + 26, angle)
        elements.append(svg_text(label_x, label_y, tap.name, text_anchor="middle", font_size=11))

        tap_positions[node] = (outer_x, outer_y)

    return elements, tap_positions


def _draw_tap(elements, inner_x, inner_y, outer_x, outer_y, direction, tap):
    """A transformer tap connects straight into the yard at the ring
    (no exit switch of its own). A line/feeder tap gets its own
    isolating disconnect along the radial stub -- see this module's
    header and generator/layouts/ring_bus.py's `add_exit_disconnect`.
    """
    if tap.kind != TapKind.TRANSFORMER:
        disc_x = inner_x + (outer_x - inner_x) * 0.35
        disc_y = inner_y + (outer_y - inner_y) * 0.35
        elements.extend(tap_symbols.draw_disconnect_at(disc_x, disc_y, outer_x - inner_x, outer_y - inner_y))
    elements.extend(tap_symbols.draw(outer_x, outer_y, direction, tap.kind))
