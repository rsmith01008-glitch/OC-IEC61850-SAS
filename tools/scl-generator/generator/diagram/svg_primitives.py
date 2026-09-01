"""Minimal hand-rolled SVG string builders -- no dependency, matching
this repo's established preference (tools/scl-compiler/scl/codegen.py's
hand-rolled Lua serializer) for small hand-written serializers over
pulling in a library. Every function returns one `<tag .../>`  or
`<tag>...</tag>` string; onelinediagram.py joins them into a document.
"""

from html import escape

_ATTR_NAME_MAP = {
    "stroke_width": "stroke-width",
    "stroke_dasharray": "stroke-dasharray",
    "font_size": "font-size",
    "font_weight": "font-weight",
    "text_anchor": "text-anchor",
    "fill_rule": "fill-rule",
}


def _attrs(attrs: dict) -> str:
    if not attrs:
        return ""
    parts = []
    for k, v in attrs.items():
        if v is None:
            continue
        name = _ATTR_NAME_MAP.get(k, k)
        parts.append('%s="%s"' % (name, escape(str(v), quote=True)))
    return (" " + " ".join(parts)) if parts else ""


def svg_line(x1, y1, x2, y2, **attrs) -> str:
    return '<line x1="%g" y1="%g" x2="%g" y2="%g"%s/>' % (x1, y1, x2, y2, _attrs(attrs))


def svg_rect(x, y, w, h, **attrs) -> str:
    return '<rect x="%g" y="%g" width="%g" height="%g"%s/>' % (x, y, w, h, _attrs(attrs))


def svg_circle(cx, cy, r, **attrs) -> str:
    return '<circle cx="%g" cy="%g" r="%g"%s/>' % (cx, cy, r, _attrs(attrs))


def svg_text(x, y, text, **attrs) -> str:
    return '<text x="%g" y="%g"%s>%s</text>' % (x, y, _attrs(attrs), escape(text))


def svg_path(d, **attrs) -> str:
    return '<path d="%s"%s/>' % (d, _attrs(attrs))


def svg_polygon(points, **attrs) -> str:
    pts = " ".join("%g,%g" % (x, y) for x, y in points)
    return '<polygon points="%s"%s/>' % (pts, _attrs(attrs))


def svg_group(children, **attrs) -> str:
    return '<g%s>\n%s\n</g>' % (_attrs(attrs), "\n".join(children))
