"""One-line diagram drawer for the 1.5-breaker layout: two horizontal
bus rails (top/bottom), each diameter drawn as a zigzag string between
them -- CB_a from the top rail down to a waist, CB_mid as a horizontal
jumper across the waist to the second tap's column, CB_b from there down
to the bottom rail. Each tap's symbol sits at its own waist junction.
"""

from ..topology import VoltageLevelBuild
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_line, svg_rect, svg_circle, svg_text


def draw(vl: VoltageLevelBuild, strip_top: float):
    elements = []
    tap_positions = {}

    top_y = strip_top + 30
    bot_y = strip_top + geo.STRIP_HEIGHT - 30
    waist_y = strip_top + geo.STRIP_HEIGHT / 2
    diameters = [b for b in vl.bays if b.name.startswith("Diameter")]
    width = geo.strip_width(len(vl.taps))

    elements.append(svg_line(geo.LEFT_MARGIN - 40, top_y, geo.LEFT_MARGIN - 40 + width, top_y,
                              stroke="#333", stroke_width=3))
    elements.append(svg_line(geo.LEFT_MARGIN - 40, bot_y, geo.LEFT_MARGIN - 40 + width, bot_y,
                              stroke="#333", stroke_width=3))
    elements.append(svg_text(geo.LEFT_MARGIN - 50, top_y - 10, "%s -- %g kV" % (vl.vl_name, vl.kv),
                              text_anchor="end", font_size=13, font_weight="bold"))

    for d, diameter in enumerate(diameters):
        x0, x1 = geo.tap_x(2 * d), geo.tap_x(2 * d + 1)
        cb_a, cb_mid, cb_b = diameter.breakers
        node0, node1 = diameter.connectivity_nodes
        tap0, tap1 = node0.tap, node1.tap

        elements.append(svg_line(x0, top_y, x0, waist_y, stroke="#333", stroke_width=2))
        elements.append(svg_line(x0, waist_y, x1, waist_y, stroke="#333", stroke_width=2))
        elements.append(svg_line(x1, waist_y, x1, bot_y, stroke="#333", stroke_width=2))
        elements.append(svg_circle(x0, top_y, 3, fill="#333"))
        elements.append(svg_circle(x1, bot_y, 3, fill="#333"))

        _breaker(elements, x0, (top_y + waist_y) / 2, cb_a.name, vertical=True)
        _breaker(elements, (x0 + x1) / 2, waist_y, cb_mid.name, vertical=False)
        _breaker(elements, x1, (waist_y + bot_y) / 2, cb_b.name, vertical=True)

        elements.extend(tap_symbols.draw(x0, waist_y, -1, tap0.kind))
        elements.append(svg_text(x0, waist_y - 26, tap0.name, text_anchor="middle", font_size=11))
        elements.extend(tap_symbols.draw(x1, waist_y, 1, tap1.kind))
        elements.append(svg_text(x1, waist_y + 30, tap1.name, text_anchor="middle", font_size=11))

        tap_positions[node0] = (x0, waist_y)
        tap_positions[node1] = (x1, waist_y)

    return elements, tap_positions


def _breaker(elements, x, y, name, vertical):
    elements.append(svg_rect(x - geo.BREAKER_SIZE / 2, y - geo.BREAKER_SIZE / 2,
                              geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))
    if vertical:
        elements.append(svg_text(x + 12, y + 4, name, font_size=11))
    else:
        elements.append(svg_text(x, y - 12, name, text_anchor="middle", font_size=11))
