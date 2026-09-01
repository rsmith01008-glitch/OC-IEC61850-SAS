"""Single/main bus layout builder: one bus, one breaker per tap. The
simplest arrangement -- no diameter grouping, no bus-tie, no ring.
"""

from ..topology import BusNode, TapNode, Breaker, BayGroup, VoltageLevelBuild, LayoutKind
from ..naming import validate_identifier


def build(vl_name: str, kv: float, taps: list, start_index: int = 1) -> VoltageLevelBuild:
    if len(taps) == 0:
        raise ValueError("single/main bus needs at least 1 tap")
    validate_identifier(vl_name)

    vl = VoltageLevelBuild(vl_name=vl_name, kv=kv, layout_kind=LayoutKind.SINGLE_BUS, taps=taps)

    bus = BusNode("Bus", desc="%s Bus" % vl_name)
    vl.nodes.append(bus)
    vl.bays.append(BayGroup("Bus", connectivity_nodes=[bus]))

    for i, tap in enumerate(taps):
        node = TapNode(tap.name, desc="%s tap" % tap.kind.value.capitalize(), tap=tap)
        vl.nodes.append(node)

        cb = Breaker("CB%d" % (start_index + i), bus, node)
        vl.breakers.append(cb)

        vl.bays.append(BayGroup(
            "Bay%d" % (i + 1),
            desc="%s tap (%s)" % (tap.kind.value.capitalize(), tap.name),
            breakers=[cb],
            connectivity_nodes=[node],
        ))

    return vl
