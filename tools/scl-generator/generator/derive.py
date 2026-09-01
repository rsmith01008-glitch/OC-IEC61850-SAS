"""Topology-agnostic remote-trip and illustrative-interlock derivation.
Operates only on the (nodes, breakers) graph any layout builder in
generator/layouts/ produces -- no per-layout-kind special-casing needed
here, by design (see each function's docstring for why the same rule
naturally produces the right result for all 4 supported layouts).
"""

from typing import List, Tuple

from .layouts.common import breakers_bounding
from .topology import Breaker, TapNode, Transformer, VoltageLevelBuild


def remote_trips_for(transformer: Transformer) -> List[Breaker]:
    """Every breaker that must be tripped to fully isolate `transformer`
    -- every breaker bounding its HV tap. Mechanically derived, decision
    #4: this is what "isolate the transformer" means regardless of
    layout kind. Naturally reproduces scl/switchyard.scd's 2-breaker
    fan-out for 1.5-breaker (both breakers bound the HV tap), degrades to
    exactly 1 breaker for single-bus/main-and-transfer (only 1 breaker
    ever touches a tap there -- an expected consequence of those
    layouts' construction, not a bug), and gives 2 breakers for ring bus
    (the tap's 2 ring neighbors).

    The LV side is deliberately NOT considered: tripping the HV-side
    breaker(s) fully de-energizes the transformer, which is sufficient,
    and generator/layouts/transformer_lv.py's LV outputs are `DIS`
    disconnects with no IED of their own to receive a remote trip in the
    first place (see that module's header).
    """
    return breakers_bounding(transformer.hv_tap, transformer.hv_vl.breakers)


def illustrative_interlocks(vl: VoltageLevelBuild) -> List[Tuple[Breaker, Breaker]]:
    """One illustrative mutual-interlock pair per "junction" -- decision
    #5, a placeholder pattern proving the cross-IED mechanism works, not
    a real site-specific interlock philosophy (see
    tools/scl-generator/README.md's Scoping decisions).

    Rule: walk `vl.nodes` in order; a TapNode bounded by exactly 2
    breakers, NEITHER of which has already been used in an emitted pair,
    contributes one interlock pair for those 2 breakers. Bus nodes
    (BusNode) are never candidates.

    This single rule, with no per-layout branching, produces exactly:
      - 1.5-breaker: one pair per diameter (matches switchyard.scd's
        CB1<->CB2 / CB4<->CB5 exactly -- a diameter's first tap qualifies
        and consumes both its breakers; the diameter's second tap then
        has one already-used breaker and is skipped, so CB2<->CB3 is
        correctly NOT also generated).
      - single-bus / main-and-transfer: ZERO pairs, always -- every tap
        in these two layouts has exactly 1 bounding breaker by
        construction (a BusNode, not a TapNode, is the only node ever
        touched by 2+ breakers there, and BusNodes are excluded), so no
        TapNode ever qualifies. This holds even in a degenerate
        1-tap main-and-transfer station (the tie breaker only ever meets
        a tap breaker at MainBus, a BusNode) -- confirmed by
        test_derive.py, not just asserted here.
      - ring bus: a deterministic, non-overlapping covering of roughly
        half the ring's breakers, one pair per unclaimed junction walked
        in tap order -- not literally "exactly one pair total," but
        every pair shares no breaker with any other, so no breaker is
        ever asked to honor two simultaneous illustrative interlocks.
    """
    pairs: List[Tuple[Breaker, Breaker]] = []
    used_breakers = set()

    for node in vl.nodes:
        if not isinstance(node, TapNode):
            continue
        bounding = breakers_bounding(node, vl.breakers)
        if len(bounding) != 2:
            continue
        b1, b2 = bounding
        if b1.name in used_breakers or b2.name in used_breakers:
            continue
        pairs.append((b1, b2))
        used_breakers.add(b1.name)
        used_breakers.add(b2.name)

    return pairs
