"""Station -> full SVG one-line diagram document. Schematic, not to
scale, not IEC-60617-symbol-library-exact -- see
tools/scl-generator/README.md's Scoping decisions.
"""

from ..topology import Station, LayoutKind
from . import layout_geometry as geo
from . import draw_transformer
from .svg_primitives import svg_text
from . import draw_breaker_and_half, draw_single_bus, draw_main_and_transfer, draw_ring_bus

_DRAWERS = {
    LayoutKind.BREAKER_AND_HALF: draw_breaker_and_half.draw,
    LayoutKind.SINGLE_BUS: draw_single_bus.draw,
    LayoutKind.MAIN_AND_TRANSFER: draw_main_and_transfer.draw,
    LayoutKind.RING_BUS: draw_ring_bus.draw,
}


def render(station: Station) -> str:
    # Highest kV on top, matching real single-line-diagram convention.
    ordered_vls = sorted(station.voltage_levels, key=lambda vl: vl.kv, reverse=True)

    elements = []
    tap_positions = {}          # TapNode -> (x, y), across every VL
    strip_bottom_y = {}         # vl_name -> y of the strip's bottom edge
    strip_top_y = {}            # vl_name -> y of the strip's top edge

    max_width = 0.0
    for rank, vl in enumerate(ordered_vls):
        top = geo.strip_y0(rank)
        strip_top_y[vl.vl_name] = top
        strip_bottom_y[vl.vl_name] = top + geo.STRIP_HEIGHT

        drawer = _DRAWERS[vl.layout_kind]
        vl_elements, vl_tap_positions = drawer(vl, top)
        elements.extend(vl_elements)
        tap_positions.update(vl_tap_positions)

        if vl.layout_kind == LayoutKind.RING_BUS:
            width = 2 * (geo.ring_radius(len(vl.taps)) + 70) + geo.LEFT_MARGIN
        else:
            n_slots = len(vl.taps) + (1 if vl.layout_kind == LayoutKind.MAIN_AND_TRANSFER else 0)
            width = geo.strip_width(n_slots) + geo.LEFT_MARGIN
        max_width = max(max_width, width)

    for xfmr in station.transformers:
        hv_point = tap_positions[xfmr.hv_tap]
        lv_point = tap_positions[xfmr.lv_tap]
        elements.extend(draw_transformer.draw(
            xfmr.name, hv_point, lv_point,
            strip_bottom_y[xfmr.hv_vl.vl_name], strip_top_y[xfmr.lv_vl.vl_name],
        ))

    height = geo.total_height(len(ordered_vls))
    title = [svg_text(max_width / 2, 30, station.name, text_anchor="middle", font_size=20, font_weight="bold")]

    body = "\n".join(title + elements)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g" '
        'width="%g" height="%g" font-family="sans-serif">\n'
        '<rect x="0" y="0" width="%g" height="%g" fill="white"/>\n'
        '%s\n</svg>\n'
    ) % (max_width, height, max_width, height, max_width, height, body)
