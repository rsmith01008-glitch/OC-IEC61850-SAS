"""One-line diagram drawer for the 1.5-breaker layout: each diameter is
ONE vertical string between the top (Bus1) and bottom (Bus2) rails --
Bus1 -- CB_a -- tap0 (branches sideways) -- CB_mid (the diameter's own
"tie") -- tap1 (branches sideways) -- CB_b -- Bus2 -- matching the
reference one-line's single-string diameter (not two separate columns
joined by a horizontal jumper, which visually read as if each tap
attached to CB_mid instead of to its own bus-side breaker).

Every breaker is flanked by 2 disconnect ticks (bus/tap side and the
opposite side), matching the real `DIS` devices
generator/layouts/breaker_and_half.py's `add_isolating_disconnects` adds
around it; a line/feeder tap branches sideways with one more disconnect
on its own exit stub (`tap_symbols.draw_tap_with_exit_horizontal`,
matching that same builder's `add_exit_disconnect`). A transformer-kind
tap has no branch/exit disconnect of its own -- it connects straight
into the yard (see generator/layouts/transformer_lv.py). 3 breakers x 2
+ up to 2 tap exits = up to 8 disconnects per diameter.
"""

from ..topology import VoltageLevelBuild, EQUIP_CBR
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_line, svg_rect, svg_circle, svg_text

_BRANCH_DIRECTION = 1  # both taps branch to the right of their string


def draw(vl: VoltageLevelBuild, strip_top: float):
    elements = []
    tap_positions = {}

    top_y = strip_top + 30
    bot_y = strip_top + geo.STRIP_HEIGHT - 30
    seg = (bot_y - top_y) / 6
    diameters = [b for b in vl.bays if b.name.startswith("Diameter")]
    width = geo.diameter_strip_width(len(diameters))

    elements.append(svg_line(geo.LEFT_MARGIN - 40, top_y, geo.LEFT_MARGIN - 40 + width, top_y,
                              stroke="#333", stroke_width=3))
    elements.append(svg_line(geo.LEFT_MARGIN - 40, bot_y, geo.LEFT_MARGIN - 40 + width, bot_y,
                              stroke="#333", stroke_width=3))
    elements.append(svg_text(geo.LEFT_MARGIN - 50, top_y - 10, "%s -- %g kV" % (vl.vl_name, vl.kv),
                              text_anchor="end", font_size=13, font_weight="bold"))

    gap = geo.BREAKER_SIZE / 2 + tap_symbols.DISCONNECT_GAP

    for d, diameter in enumerate(diameters):
        x = geo.diameter_x(d)
        cb_a, cb_mid, cb_b = [b for b in diameter.breakers if b.equip_type == EQUIP_CBR]
        # The diameter's own 2 tap ConnectivityNodes are always appended
        # first, before any isolating-disconnect intermediate nodes.
        node0, node1 = diameter.connectivity_nodes[:2]
        tap0, tap1 = node0.tap, node1.tap

        cb_a_y = top_y + seg
        tap0_y = top_y + 2 * seg
        cb_mid_y = top_y + 3 * seg
        tap1_y = top_y + 4 * seg
        cb_b_y = top_y + 5 * seg

        elements.append(svg_line(x, top_y, x, bot_y, stroke="#333", stroke_width=2))
        elements.append(svg_circle(x, top_y, 3, fill="#333"))
        elements.append(svg_circle(x, bot_y, 3, fill="#333"))

        elements.extend(tap_symbols.draw_disconnect(x, cb_a_y - gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x, cb_a_y + gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x, cb_mid_y - gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x, cb_mid_y + gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x, cb_b_y - gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x, cb_b_y + gap, vertical=True))

        _breaker(elements, x, cb_a_y, cb_a.name)
        _breaker(elements, x, cb_mid_y, cb_mid.name)
        _breaker(elements, x, cb_b_y, cb_b.name)

        elements.append(svg_circle(x, tap0_y, 3, fill="#333"))
        elements.append(svg_circle(x, tap1_y, 3, fill="#333"))
        elements.extend(tap_symbols.draw_tap_with_exit_horizontal(x, tap0_y, _BRANCH_DIRECTION, tap0))
        elements.extend(tap_symbols.draw_tap_with_exit_horizontal(x, tap1_y, _BRANCH_DIRECTION, tap1))

        tap_positions[node0] = (x, tap0_y)
        tap_positions[node1] = (x, tap1_y)

    return elements, tap_positions


def _breaker(elements, x, y, name):
    elements.append(svg_rect(x - geo.BREAKER_SIZE / 2, y - geo.BREAKER_SIZE / 2,
                              geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))
    elements.append(svg_text(x + 12, y + 4, name, font_size=11))
