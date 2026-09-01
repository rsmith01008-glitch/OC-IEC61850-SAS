import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind
from generator.layouts import single_bus


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


class TestSingleBus(unittest.TestCase):
    def test_three_taps_off_one_bus(self):
        taps = _taps(("Line1", TapKind.LINE), ("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.SINGLE_BUS)
        self.assertEqual([b.name for b in vl.breakers], ["CB1", "CB2", "CB3"])
        self.assertEqual(len(vl.bays), 4)  # Bus + 3 tap bays

        bus = next(n for n in vl.nodes if n.name == "Bus")
        for i, breaker in enumerate(vl.breakers):
            tap_node = vl.tap_node_for(taps[i])
            self.assertEqual({breaker.node_a, breaker.node_b}, {bus, tap_node})

    def test_start_index_offset(self):
        taps = _taps(("Feed1", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps, start_index=7)
        self.assertEqual(vl.breakers[0].name, "CB7")

    def test_rejects_zero_taps(self):
        with self.assertRaises(ValueError):
            single_bus.build("V13", 13.8, [])


if __name__ == "__main__":
    unittest.main()
