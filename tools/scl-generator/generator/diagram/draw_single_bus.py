"""One-line diagram drawer for the single/main-bus layout: one bus rail,
one breaker + stub per tap hanging below it.
"""

from ..topology import VoltageLevelBuild
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_line, svg_rect, svg_circle, svg_text


def draw(vl: VoltageLevelBuild, strip_top: float):
    elements = []
    tap_positions = {}

    rail_y = strip_top + 60
    tap_y = strip_top + geo.STRIP_HEIGHT - 50
    width = geo.strip_width(len(vl.taps))

    elements.append(svg_line(geo.LEFT_MARGIN - 40, rail_y, geo.LEFT_MARGIN - 40 + width, rail_y,
                              stroke="#333", stroke_width=3))
    elements.append(svg_text(geo.LEFT_MARGIN - 50, rail_y - 10, "%s -- %g kV" % (vl.vl_name, vl.kv),
                              text_anchor="end", font_size=13, font_weight="bold"))

    for i, tap in enumerate(vl.taps):
        x = geo.tap_x(i)
        node = vl.tap_node_for(tap)
        mid_y = (rail_y + tap_y) / 2

        elements.append(svg_circle(x, rail_y, 3, fill="#333"))
        elements.append(svg_line(x, rail_y, x, tap_y, stroke="#333", stroke_width=2))
        elements.extend(tap_symbols.draw_disconnect(x, rail_y + (mid_y - rail_y) / 2, vertical=True))
        elements.append(svg_rect(x - geo.BREAKER_SIZE / 2, mid_y - geo.BREAKER_SIZE / 2,
                                  geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))

        breaker = next(b for b in vl.breakers if node in (b.node_a, b.node_b))
        elements.append(svg_text(x + 12, mid_y + 4, breaker.name, font_size=11))
        elements.extend(tap_symbols.draw(x, tap_y, 1, tap.kind))
        elements.append(svg_text(x, tap_y + 30, tap.name, text_anchor="middle", font_size=11))

        tap_positions[node] = (x, tap_y)

    return elements, tap_positions
