"""Shared graph helper used by every layout builder's output and by
generator/derive.py -- the one place that knows how to ask "which
breakers touch this node," so remote-trip/interlock derivation never
needs to special-case a layout kind.
"""

from typing import List

from ..topology import Breaker, Node


def breakers_bounding(node: Node, breakers: List[Breaker]) -> List[Breaker]:
    """Every breaker with `node` as one of its two terminals, in the
    order they appear in `breakers`.
    """
    return [b for b in breakers if b.node_a is node or b.node_b is node]
