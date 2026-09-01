"""Per-layout-kind topology builders. Every builder shares one contract:
`build(vl_name, kv, taps) -> VoltageLevelBuild` (see generator.topology).
`LAYOUT_BUILDERS` is the registry `wizard.py` and `scl_writer.py` dispatch
through -- add a new layout kind by writing one module here and
registering it, nothing else needs to change.
"""

from ..topology import LayoutKind
from . import breaker_and_half, single_bus, main_and_transfer, ring_bus

LAYOUT_BUILDERS = {
    LayoutKind.BREAKER_AND_HALF: breaker_and_half.build,
    LayoutKind.SINGLE_BUS: single_bus.build,
    LayoutKind.MAIN_AND_TRANSFER: main_and_transfer.build,
    LayoutKind.RING_BUS: ring_bus.build,
}
