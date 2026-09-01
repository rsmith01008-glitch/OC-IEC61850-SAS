"""The small terminal-end symbol drawn at a tap's outward stub end,
shared by every horizontal-bus drawer (single_bus/main_and_transfer/
breaker_and_half) and ring_bus alike -- kept in one place so "what a
line tap looks like" only has one definition.

Line tap = filled arrowhead (points off the strip, "power leaves here").
Feeder tap = hollow triangle (visually distinct load-side termination).
Transformer tap = no arrow at all -- draw_transformer.py's elbow
connector attaches directly to the bare point instead.

`draw_disconnect`/`draw_disconnect_at` are the separate isolator/
disconnect-switch symbol (a short diagonal tick across the conductor,
the open-position convention this tool's reference one-line uses) --
drawn adjacent to breakers in every strip drawer and at every
transformer LV output, never merged with the breaker symbol itself (a
disconnect and a circuit breaker are two distinct devices in series,
same as the reference). `draw_tap_with_exit` is the shared "line/feeder
tap gets its own exit disconnect on a short stub, transformer tap
connects straight in" pattern used by every vertical-stub drawer
(single_bus/main_and_transfer/breaker_and_half) -- see its own
docstring and generator/layouts/common.py's `add_exit_disconnect`.
"""

import math

from ..topology import TapKind
from .svg_primitives import svg_polygon, svg_circle, svg_line, svg_text

_SIZE = 10
_DISCONNECT_SIZE = 7
_EXIT_STUB_LEN = 10
_LABEL_GAP = 26

#: Distance from a breaker's own center to each of its 2 flanking
#: disconnects -- shared by every strip drawer so a breaker's pair of
#: isolating disconnects always sits close to it regardless of the
#: surrounding span length (see draw_breaker_and_half.py for why a
#: fraction-of-the-whole-span placement doesn't generalize safely).
DISCONNECT_GAP = 18


def draw_disconnect(x: float, y: float, vertical: bool) -> list:
    """A short diagonal tick centered at (x, y), across a vertical
    conductor (`vertical=True`) or a horizontal one (`vertical=False`).
    For a conductor at an arbitrary angle (ring_bus's radial stubs), use
    `draw_disconnect_at` instead.
    """
    if vertical:
        return [svg_line(x - _DISCONNECT_SIZE, y + _DISCONNECT_SIZE,
                          x + _DISCONNECT_SIZE, y - _DISCONNECT_SIZE, stroke="#333", stroke_width=2)]
    return [svg_line(x - _DISCONNECT_SIZE, y - _DISCONNECT_SIZE,
                      x + _DISCONNECT_SIZE, y + _DISCONNECT_SIZE, stroke="#333", stroke_width=2)]


def draw_disconnect_at(x: float, y: float, dx: float, dy: float) -> list:
    """A short tick centered at (x, y), perpendicular to a conductor
    running in direction (dx, dy) -- for a stub at an arbitrary angle
    (ring_bus's radial taps), where a fixed vertical/horizontal tick can
    end up running parallel to the stub itself and disappear.
    """
    length = math.hypot(dx, dy)
    if length == 0:
        return draw_disconnect(x, y, vertical=True)
    px, py = -dy / length, dx / length
    return [svg_line(x - px * _DISCONNECT_SIZE, y - py * _DISCONNECT_SIZE,
                      x + px * _DISCONNECT_SIZE, y + py * _DISCONNECT_SIZE, stroke="#333", stroke_width=2)]


def draw(x: float, y: float, direction_dy: float, kind: TapKind) -> list:
    """`direction_dy` is +1 (symbol points downward/outward below the
    point) or -1 (points upward/outward above it) -- callers pass
    whichever matches their stub's outward direction.
    """
    tip = (x, y + direction_dy * _SIZE * 1.6)
    left = (x - _SIZE * 0.7, y)
    right = (x + _SIZE * 0.7, y)

    if kind == TapKind.LINE:
        return [svg_polygon([tip, left, right], fill="#333")]
    if kind == TapKind.FEEDER:
        return [svg_polygon([tip, left, right], fill="none", stroke="#333", stroke_width=1.5)]
    return [svg_circle(x, y, 3, fill="#333")]


def draw_horizontal(x: float, y: float, direction_dx: float, kind: TapKind) -> list:
    """Same symbol as `draw`, rotated 90 degrees: `direction_dx` is +1
    (points rightward/outward) or -1 (points leftward/outward) -- for a
    tap branching sideways off a vertical string (breaker_and_half's
    single-diameter column; see `draw_tap_with_exit_horizontal`).
    """
    tip = (x + direction_dx * _SIZE * 1.6, y)
    top = (x, y - _SIZE * 0.7)
    bot = (x, y + _SIZE * 0.7)

    if kind == TapKind.LINE:
        return [svg_polygon([tip, top, bot], fill="#333")]
    if kind == TapKind.FEEDER:
        return [svg_polygon([tip, top, bot], fill="none", stroke="#333", stroke_width=1.5)]
    return [svg_circle(x, y, 3, fill="#333")]


def draw_tap_with_exit_horizontal(x: float, y: float, direction_dx: float, tap) -> list:
    """Horizontal counterpart of `draw_tap_with_exit`, for a tap
    branching sideways off a vertical diameter string (see
    draw_breaker_and_half.py) instead of continuing straight out from a
    horizontal bus rail. Same rule: a transformer tap connects straight
    in with no exit switch; a line/feeder tap gets its own isolating
    disconnect on a short horizontal stub.
    """
    elements = []
    label_anchor = "start" if direction_dx > 0 else "end"
    label_dx = 8 if direction_dx > 0 else -8

    if tap.kind == TapKind.TRANSFORMER:
        elements.extend(draw_horizontal(x, y, direction_dx, tap.kind))
        elements.append(svg_text(x + direction_dx * _LABEL_GAP, y + 4, tap.name,
                                  text_anchor=label_anchor, font_size=11))
        return elements

    tap_x = x + direction_dx * _EXIT_STUB_LEN
    elements.append(svg_line(x, y, tap_x, y, stroke="#333", stroke_width=2))
    elements.extend(draw_disconnect(x + direction_dx * _EXIT_STUB_LEN / 2, y, vertical=False))
    elements.extend(draw_horizontal(tap_x, y, direction_dx, tap.kind))
    elements.append(svg_text(tap_x + direction_dx * _LABEL_GAP, y + 4, tap.name,
                              text_anchor=label_anchor, font_size=11))
    return elements


def draw_tap_with_exit(x: float, y: float, direction_dy: float, tap) -> list:
    """Draws a tap's symbol + label out from its junction point (x, y)
    in the `direction_dy` direction (+1/-1). A transformer tap connects
    straight into the yard at (x, y) -- no exit switch of its own (its
    HV side ties directly into the switchyard; see
    generator/layouts/transformer_lv.py). A line/feeder tap instead gets
    a short visible stub out to its symbol, with its own isolating
    disconnect -- a real `DIS`, see generator/layouts/common.py's
    `add_exit_disconnect` -- at the stub's midpoint, matching the
    reference one-line's switch before the line/feeder actually leaves.
    """
    elements = []
    if tap.kind == TapKind.TRANSFORMER:
        elements.extend(draw(x, y, direction_dy, tap.kind))
        elements.append(svg_text(x, y + direction_dy * _LABEL_GAP, tap.name,
                                  text_anchor="middle", font_size=11))
        return elements

    tap_y = y + direction_dy * _EXIT_STUB_LEN
    elements.append(svg_line(x, y, x, tap_y, stroke="#333", stroke_width=2))
    elements.extend(draw_disconnect(x, y + direction_dy * _EXIT_STUB_LEN / 2, vertical=True))
    elements.extend(draw(x, tap_y, direction_dy, tap.kind))
    elements.append(svg_text(x, tap_y + direction_dy * _LABEL_GAP, tap.name,
                              text_anchor="middle", font_size=11))
    return elements
