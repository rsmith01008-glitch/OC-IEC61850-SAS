"""Single/main bus layout builder: one bus, one breaker per tap. The
simplest arrangement -- no diameter grouping, no bus-tie, no ring.

Every breaker also gets a real isolating `DIS` on each side (bus side
and tap side), and every line/feeder tap gets one more `DIS` on its
outward side (see generator/layouts/common.py).
"""

from ..topology import BusNode, TapNode, Breaker, BayGroup, VoltageLevelBuild, LayoutKind, TapKind
from ..naming import validate_identifier
from .common import add_isolating_disconnects, add_exit_disconnect


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

        bay = BayGroup(
            "Bay%d" % (i + 1),
            desc="%s tap (%s)" % (tap.kind.value.capitalize(), tap.name),
            breakers=[cb],
            connectivity_nodes=[node],
        )
        vl.bays.append(bay)

        add_isolating_disconnects(vl, bay, cb)
        if tap.kind in (TapKind.LINE, TapKind.FEEDER):
            add_exit_disconnect(vl, bay, node)

    return vl
