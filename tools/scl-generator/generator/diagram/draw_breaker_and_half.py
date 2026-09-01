"""One-line diagram drawer for the 1.5-breaker layout: two horizontal
bus rails (top/bottom), each diameter drawn as a zigzag string between
them -- CB_a from the top rail down to a waist, CB_mid as a horizontal
jumper across the waist to the second tap's column, CB_b from there down
to the bottom rail. Each tap's symbol sits at its own waist junction.

Every breaker (real ConductingEquipment type="CBR") is flanked by 2
disconnect ticks -- one on each side, matching the real `DIS` devices
generator/layouts/breaker_and_half.py's `add_isolating_disconnects` adds
around it -- and every line/feeder tap gets one more disconnect tick on
a short stub between its waist junction and its tap symbol (matching
that same builder's `add_exit_disconnect`, and the reference one-line's
"Disc. switch" before the line leaves). A transformer-kind tap has no
exit stub/disconnect of its own -- it connects straight into the yard
(see generator/layouts/transformer_lv.py). 3 breakers x 2 + up to 2 tap
exits = up to 8 disconnects per diameter.
"""

from ..topology import VoltageLevelBuild, EQUIP_CBR
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
        cb_a, cb_mid, cb_b = [b for b in diameter.breakers if b.equip_type == EQUIP_CBR]
        # The diameter's own 2 tap ConnectivityNodes are always appended
        # first, before any isolating-disconnect intermediate nodes.
        node0, node1 = diameter.connectivity_nodes[:2]
        tap0, tap1 = node0.tap, node1.tap

        elements.append(svg_line(x0, top_y, x0, waist_y, stroke="#333", stroke_width=2))
        elements.append(svg_line(x0, waist_y, x1, waist_y, stroke="#333", stroke_width=2))
        elements.append(svg_line(x1, waist_y, x1, bot_y, stroke="#333", stroke_width=2))
        elements.append(svg_circle(x0, top_y, 3, fill="#333"))
        elements.append(svg_circle(x1, bot_y, 3, fill="#333"))

        # cb_a/cb_b sit closer to their own bus rail (not the exact leg
        # midpoint) so there's enough clear room near the waist for a
        # line/feeder tap's own exit-disconnect+symbol+label cluster
        # without colliding with cb_a/cb_b's own tap-side disconnect.
        cb_a_y = top_y + (waist_y - top_y) * 0.35
        cb_b_y = bot_y - (bot_y - waist_y) * 0.35
        cb_mid_x = (x0 + x1) / 2

        # 2 disconnects flanking each breaker, anchored a fixed distance
        # from the breaker's own center (not a fraction of the whole
        # span) so they stay close to their breaker regardless of leg
        # length, leaving the rest of the span clear for whatever sits
        # near the waist (a tap's own exit disconnect, the tie breaker).
        gap = geo.BREAKER_SIZE / 2 + tap_symbols.DISCONNECT_GAP
        elements.extend(tap_symbols.draw_disconnect(x0, cb_a_y - gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x0, cb_a_y + gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x1, cb_b_y - gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(x1, cb_b_y + gap, vertical=True))
        elements.extend(tap_symbols.draw_disconnect(cb_mid_x - gap, waist_y, vertical=False))
        elements.extend(tap_symbols.draw_disconnect(cb_mid_x + gap, waist_y, vertical=False))

        _breaker(elements, x0, cb_a_y, cb_a.name, vertical=True)
        _breaker(elements, cb_mid_x, waist_y, cb_mid.name, vertical=False)
        _breaker(elements, x1, cb_b_y, cb_b.name, vertical=True)

        elements.extend(tap_symbols.draw_tap_with_exit(x0, waist_y, -1, tap0))
        elements.extend(tap_symbols.draw_tap_with_exit(x1, waist_y, 1, tap1))

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
