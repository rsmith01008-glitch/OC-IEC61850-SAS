"""Ring bus layout builder: breakers form a closed ring; each tap sits
between two adjacent breakers. No separate bus node -- the taps
themselves are the ring junctions. Needs at least 3 taps to close a
sensible loop.
"""

from ..topology import TapNode, Breaker, BayGroup, VoltageLevelBuild, LayoutKind
from ..naming import validate_identifier


def build(vl_name: str, kv: float, taps: list, start_index: int = 1) -> VoltageLevelBuild:
    if len(taps) < 3:
        raise ValueError(
            "ring bus needs at least 3 taps to form a closed loop -- got %d"
            % len(taps)
        )
    validate_identifier(vl_name)

    vl = VoltageLevelBuild(vl_name=vl_name, kv=kv, layout_kind=LayoutKind.RING_BUS, taps=taps)

    nodes = [
        TapNode(tap.name, desc="%s tap" % tap.kind.value.capitalize(), tap=tap)
        for tap in taps
    ]
    vl.nodes.extend(nodes)

    n = len(taps)
    breakers = [
        Breaker("CB%d" % (start_index + i), nodes[i], nodes[(i + 1) % n])
        for i in range(n)
    ]
    vl.breakers.extend(breakers)

    # Bay i bundles tap[i]'s ConnectivityNode with breaker[i] (the
    # breaker clockwise of it, per this builder's node[i]->node[i+1]
    # direction) -- every breaker ends up owned by exactly one bay, same
    # convention as breaker_and_half.py's diameter bays.
    for i, tap in enumerate(taps):
        vl.bays.append(BayGroup(
            "Bay%d" % (i + 1),
            desc="%s tap (%s)" % (tap.kind.value.capitalize(), tap.name),
            breakers=[breakers[i]],
            connectivity_nodes=[nodes[i]],
        ))

    return vl
