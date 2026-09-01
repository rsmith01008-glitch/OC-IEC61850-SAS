"""Main-and-transfer bus layout builder: a main bus (one breaker per
tap) plus a transfer bus joined to it by a single tie breaker.

Scoping decision (documented in tools/scl-generator/README.md and in the
wizard's post-generation summary whenever this layout is chosen): v1
does NOT model the per-bay transfer-bus bypass disconnect that gives
this layout its real maintenance-switching capability -- only the
transfer bus rail and the one tie breaker are represented, for
topological/diagram fidelity to the layout's name. Consequence: a
transformer landing on a main-and-transfer bay is only ever bounded by
its one main breaker (see generator/derive.py's remote-trip derivation),
never by any transfer-path breaker.

Every breaker (including the tie) also gets a real isolating `DIS` on
each side, and every line/feeder tap gets one more `DIS` on its outward
side (see generator/layouts/common.py) -- distinct from, and not a
substitute for, the per-bay bypass disconnect scoped out above.
"""

from ..topology import BusNode, TapNode, Breaker, BayGroup, VoltageLevelBuild, LayoutKind, TapKind
from ..naming import validate_identifier
from .common import add_isolating_disconnects, add_exit_disconnect


def build(vl_name: str, kv: float, taps: list, start_index: int = 1) -> VoltageLevelBuild:
    if len(taps) == 0:
        raise ValueError("main-and-transfer bus needs at least 1 tap")
    validate_identifier(vl_name)

    vl = VoltageLevelBuild(vl_name=vl_name, kv=kv, layout_kind=LayoutKind.MAIN_AND_TRANSFER, taps=taps)

    # Node name is generic "Bus" in both bays -- the bay name already
    # disambiguates in the full pathName, same convention as
    # breaker_and_half.py's BusA/BusB.
    main_bus = BusNode("Bus", desc="%s Main Bus" % vl_name)
    transfer_bus = BusNode("Bus", desc="%s Transfer Bus" % vl_name)
    vl.nodes.extend([main_bus, transfer_bus])
    vl.bays.append(BayGroup("MainBus", connectivity_nodes=[main_bus]))
    vl.bays.append(BayGroup("TransferBus", connectivity_nodes=[transfer_bus]))

    breaker_index = start_index
    for i, tap in enumerate(taps):
        node = TapNode(tap.name, desc="%s tap" % tap.kind.value.capitalize(), tap=tap)
        vl.nodes.append(node)

        cb = Breaker("CB%d" % breaker_index, main_bus, node)
        vl.breakers.append(cb)
        breaker_index += 1

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

    tie = Breaker("CB%d" % breaker_index, main_bus, transfer_bus)
    vl.breakers.append(tie)
    tie_bay = BayGroup("Tie", desc="Main-transfer bus tie", breakers=[tie])
    vl.bays.append(tie_bay)
    add_isolating_disconnects(vl, tie_bay, tie)

    return vl
