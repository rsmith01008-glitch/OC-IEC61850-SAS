"""1.5-breaker (breaker-and-a-half) layout builder.

A real diameter has exactly 2 taps and 3 breakers (the "1.5" ratio is
3 breakers : 2 bays) -- see scl/README.md for why this is the textbook-
minimal illustration and scl/switchyard.scd for the pattern this
generalizes. Taps must come in an even count; an odd count is a hard
error rather than silently padding or dropping a tap, since either would
fabricate topology the user didn't ask for.
"""

from typing import List

from ..topology import BusNode, TapNode, Breaker, BayGroup, VoltageLevelBuild, LayoutKind
from ..naming import validate_identifier


def build(vl_name: str, kv: float, taps: list, start_index: int = 1) -> VoltageLevelBuild:
    if len(taps) == 0 or len(taps) % 2 != 0:
        raise ValueError(
            "1.5-breaker needs an even number of taps (3 breakers : 2 bays "
            "per diameter) -- got %d; add or remove one" % len(taps)
        )
    validate_identifier(vl_name)

    vl = VoltageLevelBuild(vl_name=vl_name, kv=kv, layout_kind=LayoutKind.BREAKER_AND_HALF, taps=taps)

    # Node name is the generic "Bus" in both bays (not "BusA"/"BusB") --
    # the bay name already disambiguates them in the full pathName
    # ("V800/BusA/Bus" vs "V800/BusB/Bus"), matching switchyard.scd's
    # own BusA800/Bus convention rather than a redundant "BusA/BusA".
    bus_a = BusNode("Bus", desc="%s Bus A" % vl_name)
    bus_b = BusNode("Bus", desc="%s Bus B" % vl_name)
    bay_a = BayGroup("BusA", connectivity_nodes=[bus_a])
    bay_b = BayGroup("BusB", connectivity_nodes=[bus_b])
    vl.nodes.extend([bus_a, bus_b])
    vl.bays.extend([bay_a, bay_b])

    breaker_index = start_index
    n_diameters = len(taps) // 2
    for d in range(n_diameters):
        tap0, tap1 = taps[2 * d], taps[2 * d + 1]
        node0 = TapNode(tap0.name, desc="%s tap" % tap0.kind.value.capitalize(), tap=tap0)
        node1 = TapNode(tap1.name, desc="%s tap" % tap1.kind.value.capitalize(), tap=tap1)
        vl.nodes.extend([node0, node1])

        cb_a = Breaker("CB%d" % breaker_index, bus_a, node0)
        cb_mid = Breaker("CB%d" % (breaker_index + 1), node0, node1)
        cb_b = Breaker("CB%d" % (breaker_index + 2), node1, bus_b)
        vl.breakers.extend([cb_a, cb_mid, cb_b])

        diameter = BayGroup(
            "Diameter%d" % (d + 1),
            desc="Breaker-and-a-half diameter: %s tap (%s), %s tap (%s)"
                 % (tap0.kind.value, tap0.name, tap1.kind.value, tap1.name),
            breakers=[cb_a, cb_mid, cb_b],
            connectivity_nodes=[node0, node1],
        )
        vl.bays.append(diameter)
        breaker_index += 3

    return vl
