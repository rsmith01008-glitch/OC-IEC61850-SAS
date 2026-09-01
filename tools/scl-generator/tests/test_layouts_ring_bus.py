import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind, EQUIP_CBR, EQUIP_DIS
from generator.layouts import ring_bus
from generator.layouts.common import breakers_bounding


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


def _cbr(vl):
    return [b for b in vl.breakers if b.equip_type == EQUIP_CBR]


class TestRingBus(unittest.TestCase):
    def test_three_taps_closes_the_loop(self):
        taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = ring_bus.build("V69", 69, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.RING_BUS)
        self.assertEqual([b.name for b in _cbr(vl)], ["CB1", "CB2", "CB3"])
        self.assertEqual(len(vl.bays), 3)

        n0 = vl.tap_node_for(taps[0])
        n1 = vl.tap_node_for(taps[1])
        n2 = vl.tap_node_for(taps[2])
        cb1, cb2, cb3 = _cbr(vl)
        # Each breaker is now flanked by its own isolating DIS rather
        # than touching its two neighboring taps directly --
        # breakers_bounding resolves through those.
        self.assertEqual(breakers_bounding(n0, vl.breakers), [cb1, cb3])
        self.assertEqual(breakers_bounding(n1, vl.breakers), [cb1, cb2])
        self.assertEqual(breakers_bounding(n2, vl.breakers), [cb2, cb3])

    def test_every_tap_has_exactly_two_bounding_breakers(self):
        taps = _taps(*[("T%d" % i, TapKind.FEEDER) for i in range(5)])
        vl = ring_bus.build("V69", 69, taps)
        for tap in taps:
            node = vl.tap_node_for(tap)
            self.assertEqual(len(breakers_bounding(node, vl.breakers)), 2)

    def test_every_breaker_gets_disconnects_on_both_sides(self):
        taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = ring_bus.build("V69", 69, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        for cb in ("CB1", "CB2", "CB3"):
            self.assertIn("%sDA" % cb, dis_names)
            self.assertIn("%sDB" % cb, dis_names)

    def test_line_feeder_taps_get_exit_disconnect(self):
        taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = ring_bus.build("V69", 69, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        self.assertIn("Line1D", dis_names)
        self.assertIn("Line2D", dis_names)
        self.assertIn("Feed1D", dis_names)

    def test_rejects_fewer_than_three_taps(self):
        taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE))
        with self.assertRaises(ValueError):
            ring_bus.build("V69", 69, taps)


if __name__ == "__main__":
    unittest.main()
