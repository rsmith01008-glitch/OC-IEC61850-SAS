"""The transformer symbol shared by every voltage-level drawer: two
overlapping circles (the standard schematic winding symbol), connected
to its HV tap's point in one strip and its LV tap's point in a strip
below it -- taps need not share an x-coordinate (each voltage level lays
out its own taps independently), so the connector is a simple elbow
path, not a straight vertical line.
"""

from .svg_primitives import svg_circle, svg_path, svg_text, svg_group

_RADIUS = 20
_OVERLAP = 8


def draw(transformer_name: str, hv_point, lv_point, hv_y_bottom_of_strip: float, lv_y_top_of_strip: float) -> list:
    """`hv_point`/`lv_point` are (x, y) tap positions from the HV/LV
    strip's own drawer. The symbol is centered vertically between the
    bottom of the HV strip and the top of the LV strip.
    """
    hv_x, _hv_y = hv_point
    lv_x, _lv_y = lv_point
    mid_y = (hv_y_bottom_of_strip + lv_y_top_of_strip) / 2
    mid_x = (hv_x + lv_x) / 2

    elements = []
    # Elbow connector: HV tap point straight down to the symbol's row,
    # sideways to the LV tap's x, straight down into the LV strip.
    path_d = "M %g %g L %g %g L %g %g L %g %g" % (
        hv_x, hv_y_bottom_of_strip, hv_x, mid_y, lv_x, mid_y, lv_x, lv_y_top_of_strip,
    )
    elements.append(svg_path(path_d, stroke="#333", stroke_width=2, fill="none"))

    elements.append(svg_circle(mid_x - _OVERLAP / 2, mid_y, _RADIUS, stroke="#333", stroke_width=2, fill="white"))
    elements.append(svg_circle(mid_x + _OVERLAP / 2, mid_y, _RADIUS, stroke="#333", stroke_width=2, fill="white"))
    elements.append(svg_text(mid_x, mid_y + _RADIUS + 16, transformer_name, text_anchor="middle", font_size=12))

    return [svg_group(elements)]
