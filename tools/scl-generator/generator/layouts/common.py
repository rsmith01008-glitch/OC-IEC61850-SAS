"""Shared graph helpers used by every layout builder's output and by
generator/derive.py -- the one place that knows how to ask "which real
breakers touch this node" and how to attach isolating disconnects, so
neither remote-trip/interlock derivation nor any individual layout
builder needs to special-case a layout kind.
"""

from typing import List

from ..topology import Breaker, Node, EQUIP_CBR, EQUIP_DIS


def breakers_bounding(node: Node, breakers: List[Breaker]) -> List[Breaker]:
    """Every real (`EQUIP_CBR`) breaker that isolates `node` -- found by
    walking outward from `node` through any non-breaker devices
    (isolating disconnects) and stopping at the first breaker reached
    along each path. Disconnects are transparent to this walk on
    purpose: a manual isolating switch never changes which breaker
    actually has to open to clear a fault, it only adds the ability to
    isolate a de-energized segment afterward -- so "which breakers bound
    this point" means the same thing whether or not a disconnect sits in
    between (see generator/layouts/common.py's `add_isolating_disconnects`
    for why every breaker now has one on each side).

    Returned in `breakers`' own order (not graph-walk-discovery order,
    which depends on traversal direction and isn't a meaningful
    ordering) -- matches this function's pre-disconnect behavior, which
    callers/tests rely on (e.g. illustrative_interlocks' pairs coming
    out lower-breaker-number-first).
    """
    found = set()
    seen = {node}
    frontier = [node]
    while frontier:
        n = frontier.pop()
        for b in breakers:
            if b.node_a is not n and b.node_b is not n:
                continue
            other = b.other_node(n)
            if b.equip_type == EQUIP_CBR:
                found.add(b)
            elif other not in seen:
                seen.add(other)
                frontier.append(other)
    return [b for b in breakers if b in found]


def add_isolating_disconnects(vl, bay, breaker: Breaker) -> None:
    """Wraps `breaker`'s own two terminals in one `DIS` device each --
    real breaker-and-a-half/ring/single-bus practice: every breaker gets
    an isolating disconnect on both sides so it (and only it) can be
    taken out for maintenance without an outage anywhere else. Mutates
    `breaker.node_a`/`node_b` in place to point at 2 new intermediate
    ConnectivityNodes instead of `breaker`'s original neighbors;
    `breakers_bounding` above walks straight through the new DIS to find
    `breaker` regardless, so no caller elsewhere needs to change.
    """
    orig_a, orig_b = breaker.node_a, breaker.node_b
    mid_a = Node("%sA" % breaker.name, desc="%s isolating point (%s side)" % (breaker.name, orig_a.name))
    mid_b = Node("%sB" % breaker.name, desc="%s isolating point (%s side)" % (breaker.name, orig_b.name))
    dis_a = Breaker("%sDA" % breaker.name, orig_a, mid_a, equip_type=EQUIP_DIS)
    dis_b = Breaker("%sDB" % breaker.name, mid_b, orig_b, equip_type=EQUIP_DIS)

    breaker.node_a = mid_a
    breaker.node_b = mid_b

    vl.nodes.extend([mid_a, mid_b])
    vl.breakers.extend([dis_a, dis_b])
    bay.connectivity_nodes.extend([mid_a, mid_b])
    bay.breakers.extend([dis_a, dis_b])


def add_exit_disconnect(vl, bay, tap_node: Node) -> None:
    """One more `DIS` between a line/feeder tap's own ConnectivityNode
    and a new dead-end node representing "beyond this switch is the
    outgoing line/feeder" -- a distinct device from any breaker-adjacent
    disconnect added by `add_isolating_disconnects`. Callers only invoke
    this for `TapKind.LINE`/`TapKind.FEEDER` taps, never
    `TapKind.TRANSFORMER` -- a transformer's HV tap connects straight
    into the switchyard with no separate "leaving the property" switch
    of its own (see generator/layouts/transformer_lv.py for its LV side,
    which already models its own DIS-gated outputs).
    """
    exit_node = Node("%sExit" % tap_node.name, desc="beyond %s's isolating switch" % tap_node.name)
    dis = Breaker("%sD" % tap_node.name, tap_node, exit_node, equip_type=EQUIP_DIS)

    vl.nodes.append(exit_node)
    vl.breakers.append(dis)
    bay.connectivity_nodes.append(exit_node)
    bay.breakers.append(dis)
