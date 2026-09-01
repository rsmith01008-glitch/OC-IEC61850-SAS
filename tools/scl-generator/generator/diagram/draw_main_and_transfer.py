"""One-line diagram drawer for the main-and-transfer bus layout: a solid
main bus rail (taps hang off it, same as single_bus) plus a dashed
transfer bus rail joined to it by one tie breaker at the rightmost slot.
"""

from ..topology import VoltageLevelBuild
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_line, svg_rect, svg_circle, svg_text


def draw(vl: VoltageLevelBuild, strip_top: float):
    elements = []
    tap_positions = {}

    main_y = strip_top + 50
    transfer_y = strip_top + 90
    tap_y = strip_top + geo.STRIP_HEIGHT - 50
    n_taps = len(vl.taps)
    tie_x = geo.tap_x(n_taps)
    width = geo.strip_width(n_taps + 1)

    elements.append(svg_line(geo.LEFT_MARGIN - 40, main_y, geo.LEFT_MARGIN - 40 + width, main_y,
                              stroke="#333", stroke_width=3))
    elements.append(svg_line(geo.LEFT_MARGIN - 40, transfer_y, tie_x, transfer_y,
                              stroke="#888", stroke_width=2, stroke_dasharray="6,4"))
    elements.append(svg_text(geo.LEFT_MARGIN - 50, main_y - 10, "%s -- %g kV" % (vl.vl_name, vl.kv),
                              text_anchor="end", font_size=13, font_weight="bold"))
    elements.append(svg_text(geo.LEFT_MARGIN - 50, transfer_y + 4, "Transfer",
                              text_anchor="end", font_size=10, fill="#888"))

    for i, tap in enumerate(vl.taps):
        x = geo.tap_x(i)
        node = vl.tap_node_for(tap)
        mid_y = (main_y + tap_y) / 2

        elements.append(svg_circle(x, main_y, 3, fill="#333"))
        elements.append(svg_line(x, main_y, x, tap_y, stroke="#333", stroke_width=2))
        elements.append(svg_rect(x - geo.BREAKER_SIZE / 2, mid_y - geo.BREAKER_SIZE / 2,
                                  geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))

        breaker = next(b for b in vl.breakers if node in (b.node_a, b.node_b) and b.name != _tie_name(vl))
        elements.append(svg_text(x + 12, mid_y + 4, breaker.name, font_size=11))
        elements.extend(tap_symbols.draw(x, tap_y, 1, tap.kind))
        elements.append(svg_text(x, tap_y + 30, tap.name, text_anchor="middle", font_size=11))

        tap_positions[node] = (x, tap_y)

    tie = vl.breakers[-1]
    tie_mid_y = (main_y + transfer_y) / 2
    elements.append(svg_line(tie_x, main_y, tie_x, transfer_y, stroke="#333", stroke_width=2))
    elements.append(svg_rect(tie_x - geo.BREAKER_SIZE / 2, tie_mid_y - geo.BREAKER_SIZE / 2,
                              geo.BREAKER_SIZE, geo.BREAKER_SIZE, fill="white", stroke="#333", stroke_width=2))
    elements.append(svg_text(tie_x + 12, tie_mid_y + 4, tie.name, font_size=11))
    elements.append(svg_text(tie_x, transfer_y - 10, "Tie", text_anchor="middle", font_size=10, fill="#888"))

    return elements, tap_positions


def _tie_name(vl: VoltageLevelBuild) -> str:
    return vl.breakers[-1].name
