import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind
from generator.layouts import breaker_and_half


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


class TestBreakerAndHalf(unittest.TestCase):
    def test_two_taps_matches_switchyard_scd_diameter1(self):
        taps = _taps(("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
        vl = breaker_and_half.build("V800", 800, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.BREAKER_AND_HALF)
        self.assertEqual([b.name for b in vl.breakers], ["CB1", "CB2", "CB3"])
        self.assertEqual(len(vl.bays), 3)  # BusA, BusB, Diameter1

        bus_a_bay = next(b for b in vl.bays if b.name == "BusA")
        bus_b_bay = next(b for b in vl.bays if b.name == "BusB")
        bus_a = bus_a_bay.connectivity_nodes[0]
        bus_b = bus_b_bay.connectivity_nodes[0]
        n1 = vl.tap_node_for(taps[0])
        n2 = vl.tap_node_for(taps[1])

        cb1, cb2, cb3 = vl.breakers
        self.assertEqual({cb1.node_a, cb1.node_b}, {bus_a, n1})
        self.assertEqual({cb2.node_a, cb2.node_b}, {n1, n2})
        self.assertEqual({cb3.node_a, cb3.node_b}, {n2, bus_b})

    def test_four_taps_makes_two_diameters(self):
        taps = _taps(
            ("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER),
            ("Line2", TapKind.LINE), ("Feed1", TapKind.FEEDER),
        )
        vl = breaker_and_half.build("V800", 800, taps)
        self.assertEqual([b.name for b in vl.breakers], ["CB1", "CB2", "CB3", "CB4", "CB5", "CB6"])
        diameter_bays = [b for b in vl.bays if b.name.startswith("Diameter")]
        self.assertEqual(len(diameter_bays), 2)
        self.assertEqual(len(diameter_bays[0].breakers), 3)
        self.assertEqual(len(diameter_bays[1].breakers), 3)

    def test_start_index_offsets_breaker_numbering(self):
        taps = _taps(("Xfmr1LV", TapKind.TRANSFORMER), ("Feed1", TapKind.FEEDER))
        vl = breaker_and_half.build("V230", 230, taps, start_index=4)
        self.assertEqual([b.name for b in vl.breakers], ["CB4", "CB5", "CB6"])

    def test_rejects_odd_tap_count(self):
        taps = _taps(("Line1", TapKind.LINE))
        with self.assertRaises(ValueError):
            breaker_and_half.build("V800", 800, taps)

    def test_rejects_zero_taps(self):
        with self.assertRaises(ValueError):
            breaker_and_half.build("V800", 800, [])


if __name__ == "__main__":
    unittest.main()
