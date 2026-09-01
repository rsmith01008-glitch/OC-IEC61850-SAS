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
    # Only REAL, user-chosen switchyards get a strip -- a transformer's
    # LV side is never one (see generator/layouts/transformer_lv.py).
    ordered_vls = sorted(station.voltage_levels, key=lambda vl: vl.kv, reverse=True)

    elements = []
    tap_positions = {}          # TapNode -> (x, y), across every real strip

    max_width = 0.0
    for rank, vl in enumerate(ordered_vls):
        top = geo.strip_y0(rank)

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

    # Every transformer's symbol+LV-output-fan hangs in one shared band
    # below the bottom of every real strip -- see draw_transformer.py's
    # header for why (and its documented simplification).
    band_top = geo.total_height(len(ordered_vls)) - 20
    for xfmr in station.transformers:
        hv_point = tap_positions[xfmr.hv_tap]
        elements.extend(draw_transformer.draw(
            xfmr.name, hv_point, xfmr.lv_vl.kv, xfmr.lv_vl.taps, band_top,
        ))
        n = len(xfmr.lv_vl.taps)
        fan_half_width = max(60 * (n - 1) / 2, 20) + 60
        max_width = max(max_width, hv_point[0] + fan_half_width)

    height = band_top + (draw_transformer.band_height() if station.transformers else 0) + 20
    title = [svg_text(max_width / 2, 30, station.name, text_anchor="middle", font_size=20, font_weight="bold")]

    body = "\n".join(title + elements)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g" '
        'width="%g" height="%g" font-family="sans-serif">\n'
        '<rect x="0" y="0" width="%g" height="%g" fill="white"/>\n'
        '%s\n</svg>\n'
    ) % (max_width, height, max_width, height, max_width, height, body)
