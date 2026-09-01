"""The transformer symbol + its LV output fan, hanging off its HV tap
point in whichever real switchyard strip it belongs to -- but shifted
entirely to one side of that tap's own x-coordinate, not directly below
it. Not a second strip -- see generator/layouts/transformer_lv.py's
header for why a transformer's LV side is deliberately not drawn as one.

Known simplification (documented, not silently dropped): every
transformer's symbol+fan is drawn in one shared horizontal band below
the BOTTOM of all real switchyard strips, so it never overlaps a real
strip -- if a transformer's HV tap lives in an upper strip while another
real switchyard strip sits below it, its connector is simply a longer
vertical run down to that shared band. Multiple transformers close
together in x are not collision-avoided beyond that. Both are fine for
this tool's common case (one real switchyard, a handful of transformers)
and are schematic-diagram simplifications consistent with the rest of
this drawer's "not to scale" scope.

The whole transformer body (winding symbol + LV bus + output fan) is
jogged sideways off the HV tap point -- right at the tap's own y, before
any further descent -- never drawn on a straight vertical line down from
it. The true connection point (the dot the caller draws at `hv_point`)
stays exactly where the switchyard puts it (e.g. between two of a
diameter's breakers); only the wiring FROM that point on is shifted to
`body_x`, so the long run down to the transformer -- which necessarily
crosses the bus rail -- does so with no junction dot there (the standard
"passes over, does not connect" convention), never overlapping the
breaker/bus-rail column directly below the tap. Its own isolating
disconnect sits low on that run, below the bus rail and just above the
winding symbol -- matching real practice (the transformer's HV
disconnect lives at the transformer end, not up in the switchyard bay
where the breakers' own disconnects already are). The LV output fan is
likewise offset clear of `body_x`, not centered on it -- otherwise a
single output (or the middle one, for an odd count) lands back on the
same straight line as the HV run feeding the transformer from above.
"""

from ..topology import TapKind
from . import layout_geometry as geo
from . import tap_symbols
from .svg_primitives import svg_circle, svg_line, svg_text, svg_group

_RADIUS = 20
_OVERLAP = 8
_JOG_OFFSET = 60    # how far right of the true HV tap point the whole
                     # transformer body (symbol+fan) is shifted
_SYMBOL_GAP = 60     # hv_point down to the transformer symbol
_DISCONNECT_MARGIN = 15  # transformer symbol up to its HV disconnect
_BUS_GAP = 46        # symbol down to the LV bus stub
_OUTPUT_GAP = 36     # LV bus stub down to each output's disconnect/symbol
_OUTPUT_PITCH = 60   # horizontal spacing between output stubs


def band_height() -> float:
    """Total vertical space one transformer's symbol+fan needs below the
    shared band's top -- callers use this to size the canvas.
    """
    return _SYMBOL_GAP + _BUS_GAP + _OUTPUT_GAP + 40


def max_x(hv_x: float, n_outputs: int) -> float:
    """Rightmost x-coordinate this transformer's fan reaches -- callers
    use this to size the canvas width.
    """
    body_x = hv_x + _JOG_OFFSET
    return body_x + _OUTPUT_PITCH * n_outputs + 50


def draw(xfmr_name: str, hv_point, lv_kv: float, lv_outputs: list, band_top: float) -> list:
    """`lv_outputs` is `xfmr.lv_vl.taps` (a list of Tap: name + kind).
    Returns a flat list of SVG element strings.
    """
    hv_x, hv_y = hv_point
    body_x = hv_x + _JOG_OFFSET
    symbol_y = band_top + _SYMBOL_GAP
    bus_y = symbol_y + _BUS_GAP
    output_y = bus_y + _OUTPUT_GAP

    elements = []
    # Jog right at the tap's own y (the caller already drew the real
    # connection dot at hv_point) -- everything from here on, including
    # the crossing of the bus rail below, runs at body_x, not hv_x.
    elements.append(svg_line(hv_x, hv_y, body_x, hv_y, stroke="#333", stroke_width=2))
    elements.append(svg_line(body_x, hv_y, body_x, symbol_y - _RADIUS, stroke="#333", stroke_width=2))
    elements.extend(tap_symbols.draw_disconnect(body_x, symbol_y - _RADIUS - _DISCONNECT_MARGIN, vertical=True))

    elements.append(svg_circle(body_x - _OVERLAP / 2, symbol_y, _RADIUS, stroke="#333", stroke_width=2, fill="white"))
    elements.append(svg_circle(body_x + _OVERLAP / 2, symbol_y, _RADIUS, stroke="#333", stroke_width=2, fill="white"))
    elements.append(svg_text(body_x - _RADIUS - _OVERLAP / 2 - 10, symbol_y + 4, xfmr_name,
                              text_anchor="end", font_size=12, font_weight="bold"))

    elements.append(svg_line(body_x, symbol_y + _RADIUS, body_x, bus_y, stroke="#333", stroke_width=2))

    n = len(lv_outputs)
    # Offset clear of body_x (never centered on/through it) -- see this
    # module's header for why.
    start_x = body_x + _OUTPUT_PITCH
    end_x = start_x + (n - 1) * _OUTPUT_PITCH
    elements.append(svg_line(body_x, bus_y, end_x, bus_y, stroke="#333", stroke_width=3))
    elements.append(svg_text(end_x + 10, bus_y + 4, "%g kV" % lv_kv, font_size=10, fill="#666"))

    for i, tap in enumerate(lv_outputs):
        x = start_x + i * _OUTPUT_PITCH
        elements.append(svg_line(x, bus_y, x, output_y, stroke="#333", stroke_width=2))
        elements.extend(tap_symbols.draw_disconnect(x, (bus_y + output_y) / 2, vertical=True))
        elements.extend(tap_symbols.draw(x, output_y, 1, tap.kind))
        elements.append(svg_text(x, output_y + 30, tap.name, text_anchor="middle", font_size=10))

    return [svg_group(elements)]
