import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind
from generator.layouts import ring_bus


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


class TestRingBus(unittest.TestCase):
    def test_three_taps_closes_the_loop(self):
        taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = ring_bus.build("V69", 69, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.RING_BUS)
        self.assertEqual([b.name for b in vl.breakers], ["CB1", "CB2", "CB3"])
        self.assertEqual(len(vl.bays), 3)

        n0 = vl.tap_node_for(taps[0])
        n1 = vl.tap_node_for(taps[1])
        n2 = vl.tap_node_for(taps[2])
        cb1, cb2, cb3 = vl.breakers
        self.assertEqual({cb1.node_a, cb1.node_b}, {n0, n1})
        self.assertEqual({cb2.node_a, cb2.node_b}, {n1, n2})
        # Wraps back: the last breaker closes the ring to the first node.
        self.assertEqual({cb3.node_a, cb3.node_b}, {n2, n0})

    def test_every_tap_has_exactly_two_bounding_breakers(self):
        from generator.layouts.common import breakers_bounding
        taps = _taps(*[("T%d" % i, TapKind.FEEDER) for i in range(5)])
        vl = ring_bus.build("V69", 69, taps)
        for tap in taps:
            node = vl.tap_node_for(tap)
            self.assertEqual(len(breakers_bounding(node, vl.breakers)), 2)

    def test_rejects_fewer_than_three_taps(self):
        taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE))
        with self.assertRaises(ValueError):
            ring_bus.build("V69", 69, taps)


if __name__ == "__main__":
    unittest.main()
