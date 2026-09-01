"""Pure coordinate math for the one-line diagram -- no SVG string
building here, no Station/topology objects either, just numbers in,
numbers out, so this is directly unit-testable without touching any
rendering code (see tests/test_diagram_geometry.py).
"""

import math

STRIP_HEIGHT = 240
STRIP_GAP = 40
LEFT_MARGIN = 160
TAP_PITCH = 140
BREAKER_SIZE = 16
TITLE_HEIGHT = 60


def strip_y0(rank: int) -> float:
    """Top y-coordinate of the rank-th voltage-level strip (0 = topmost,
    i.e. highest kV -- callers sort voltage levels descending by kV
    before assigning ranks).
    """
    return TITLE_HEIGHT + rank * (STRIP_HEIGHT + STRIP_GAP)


def total_height(n_strips: int) -> float:
    if n_strips <= 0:
        return TITLE_HEIGHT
    return strip_y0(n_strips - 1) + STRIP_HEIGHT + 20


def tap_x(index: int) -> float:
    """Left-to-right x-coordinate for the index-th tap slot (0-based) in
    a horizontal-bus-kind strip.
    """
    return LEFT_MARGIN + index * TAP_PITCH


def strip_width(n_taps: int) -> float:
    return tap_x(max(n_taps - 1, 0)) + TAP_PITCH


def ring_radius(n_taps: int) -> float:
    return max(80.0, 18.0 * n_taps)


def ring_center(strip_top: float, radius: float):
    return (LEFT_MARGIN + radius, strip_top + STRIP_HEIGHT / 2)


def ring_breaker_angle(i: int, n: int) -> float:
    """Angle (radians) of breaker[i] on the ring -- i=0 at 12 o'clock,
    clockwise (matches generator/layouts/ring_bus.py's breaker[i]
    connecting tap[i]<->tap[(i+1)%n]).
    """
    return 2 * math.pi * i / n - math.pi / 2


def ring_tap_angle(i: int, n: int) -> float:
    """Angle of tap[i], at the midpoint between breaker[i-1] (which
    closes tap[i-1]<->tap[i]) and breaker[i] (which opens tap[i]<->
    tap[i+1]) -- i.e. exactly between its two neighboring breakers.
    """
    return 2 * math.pi * (i - 0.5) / n - math.pi / 2


def point_on_circle(center, radius: float, angle: float):
    cx, cy = center
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
