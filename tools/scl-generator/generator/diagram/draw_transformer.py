"""The transformer symbol + its LV output fan, hanging directly off its
HV tap point in whichever real switchyard strip it belongs to. Not a
second strip -- see generator/layouts/transformer_lv.py's header for why
a transformer's LV side is deliberately not drawn as one.

Known simplification (documented, not silently dropped): every
transformer's symbol+fan is drawn in one shared horizontal band below
the BOTTOM of all real switchyard strips, so it never overlaps a real
strip -- if a transformer's HV tap lives in an upper strip while another
real switchyard strip sits below it, its connector is simply a longer
vertical line down to that shared band. Multiple transformers close
together in x are not collision-avoided beyond that. Both are fine for
this tool's common case (one real switchyard, a handful of transformers)
and are schematic-diagram simplifications consistent with the rest of
this drawer's "not to scale" scope.

The LV output fan is deliberately offset entirely to the right of the
HV connector's own x (`hv_x`), never centered on/under it -- a centered
fan puts one output (always, for an odd count, exactly one) directly
under `hv_x`, which visually reads as a straight continuation of
whichever breaker sits directly above `hv_x` in the switchyard strip,
rather than as a distinct device hanging off to the side.
"""

from ..topology import TapKind
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_circle, svg_line, svg_text, svg_group

_RADIUS = 20
_OVERLAP = 8
_SYMBOL_GAP = 40    # hv_point down to the transformer symbol
_BUS_GAP = 46       # symbol down to the LV bus stub
_OUTPUT_GAP = 36    # LV bus stub down to each output's disconnect/symbol
_OUTPUT_PITCH = 60  # horizontal spacing between output stubs


def band_height() -> float:
    """Total vertical space one transformer's symbol+fan needs below the
    shared band's top -- callers use this to size the canvas.
    """
    return _SYMBOL_GAP + _BUS_GAP + _OUTPUT_GAP + 40


def max_x(hv_x: float, n_outputs: int) -> float:
    """Rightmost x-coordinate this transformer's fan (offset entirely to
    the right of `hv_x`, see this module's header) reaches -- callers
    use this to size the canvas width.
    """
    return hv_x + _OUTPUT_PITCH * n_outputs + 50


def draw(xfmr_name: str, hv_point, lv_kv: float, lv_outputs: list, band_top: float) -> list:
    """`lv_outputs` is `xfmr.lv_vl.taps` (a list of Tap: name + kind).
    Returns a flat list of SVG element strings.
    """
    hv_x, hv_y = hv_point
    symbol_y = band_top + _SYMBOL_GAP
    bus_y = symbol_y + _BUS_GAP
    output_y = bus_y + _OUTPUT_GAP

    elements = []
    elements.append(svg_line(hv_x, hv_y, hv_x, symbol_y - _RADIUS, stroke="#333", stroke_width=2))
    elements.extend(tap_symbols.draw_disconnect(hv_x, (hv_y + symbol_y - _RADIUS) / 2, vertical=True))

    elements.append(svg_circle(hv_x - _OVERLAP / 2, symbol_y, _RADIUS, stroke="#333", stroke_width=2, fill="white"))
    elements.append(svg_circle(hv_x + _OVERLAP / 2, symbol_y, _RADIUS, stroke="#333", stroke_width=2, fill="white"))
    elements.append(svg_text(hv_x, symbol_y - _RADIUS - 8, xfmr_name, text_anchor="middle", font_size=12, font_weight="bold"))

    elements.append(svg_line(hv_x, symbol_y + _RADIUS, hv_x, bus_y, stroke="#333", stroke_width=2))

    n = len(lv_outputs)
    # Offset entirely to the right of hv_x (never centered on it) -- see
    # this module's header for why.
    start_x = hv_x + _OUTPUT_PITCH
    end_x = start_x + (n - 1) * _OUTPUT_PITCH
    elements.append(svg_line(hv_x, bus_y, end_x, bus_y, stroke="#333", stroke_width=3))
    elements.append(svg_text(end_x + 10, bus_y + 4, "%g kV" % lv_kv, font_size=10, fill="#666"))

    for i, tap in enumerate(lv_outputs):
        x = start_x + i * _OUTPUT_PITCH
        elements.append(svg_line(x, bus_y, x, output_y, stroke="#333", stroke_width=2))
        elements.extend(tap_symbols.draw_disconnect(x, (bus_y + output_y) / 2, vertical=True))
        elements.extend(tap_symbols.draw(x, output_y, 1, tap.kind))
        elements.append(svg_text(x, output_y + 30, tap.name, text_anchor="middle", font_size=10))

    return [svg_group(elements)]
