"""A transformer's LV side: a small, fixed, non-redundant structure --
never a second independently-laid-out switchyard.

This exists because of a real substation-architecture fact this tool
initially got wrong: breaker-and-a-half's redundant double-bus switching
belongs on the transmission side, where multiple lines (and any
transformers) share it as taps. A transformer's LV side does NOT
typically get its own matching double-bus/ring arrangement at the same
site -- "the next step-down happens closer to the point of use" (a
different substation). Differential protection (PDIF) for the
transformer covers the zone between its HV-side CT (at the breaker(s)
bounding its HV tap) and its LV-side CT, right at the transformer's own
output -- "usually just on the output of a transformer before the output
disconnects," not spanning a whole second switchyard.

So the LV side built here is deliberately minimal: one LV bus node, and
one `DIS` (disconnect switch, not `CBR`) per configured output, each
disconnect-gated exit representing an outgoing line/feeder leaving the
station. No breakers, no IEDs, no protection of their own -- these are
descriptive topology only (matching real "manual/local, not remotely
monitored" disconnect practice at this scope). Consequently
generator/derive.py's remote-trip derivation only ever needs to act on
the HV side: tripping the breakers bounding the transformer's HV tap
fully de-energizes it, which is sufficient -- the LV disconnects don't
need (and can't receive, having no IED) a remote trip of their own.
"""

from ..topology import (
    BusNode, TapNode, Tap, TapKind, Breaker, BayGroup, VoltageLevelBuild,
    LayoutKind, Transformer, EQUIP_DIS,
)
from ..naming import validate_identifier


def build(xfmr_name: str, lv_kv: float, lv_outputs: list) -> VoltageLevelBuild:
    """`lv_outputs` is a list of (name, TapKind) pairs -- each becomes one
    disconnect-gated exit off the shared LV bus.
    """
    if not lv_outputs:
        raise ValueError("transformer %r needs at least 1 LV output" % xfmr_name)

    vl_name = "%sLV" % xfmr_name
    validate_identifier(vl_name)
    vl = VoltageLevelBuild(vl_name=vl_name, kv=lv_kv, layout_kind=LayoutKind.TRANSFORMER_LV, taps=[])

    lv_bus = BusNode("Bus", desc="%s LV bus" % xfmr_name)
    vl.nodes.append(lv_bus)
    vl.bays.append(BayGroup("LVBus", connectivity_nodes=[lv_bus]))

    for i, (output_name, output_kind) in enumerate(lv_outputs, start=1):
        tap = Tap(output_name, output_kind)
        vl.taps.append(tap)
        node = TapNode(output_name, desc="%s output" % output_kind.value.capitalize(), tap=tap)
        vl.nodes.append(node)

        dis = Breaker("%sDIS%d" % (xfmr_name, i), lv_bus, node, equip_type=EQUIP_DIS)
        vl.breakers.append(dis)
        vl.bays.append(BayGroup(
            "Output%d" % i,
            desc="%s output (%s)" % (output_kind.value.capitalize(), output_name),
            breakers=[dis], connectivity_nodes=[node],
        ))

    return vl


def build_transformer(name: str, hv_vl: VoltageLevelBuild, hv_tap: TapNode,
                       lv_kv: float, lv_outputs: list) -> Transformer:
    """Builds the LV stub and the Transformer object together -- the one
    entry point generator/wizard.py needs once a switchyard's HV tap
    (`hv_tap`, from that switchyard's own layout builder) is available.
    """
    lv_vl = build(name, lv_kv, lv_outputs)
    lv_bus = lv_vl.nodes[0]
    return Transformer(name=name, hv_vl=hv_vl, hv_tap=hv_tap, lv_vl=lv_vl, lv_tap=lv_bus)
