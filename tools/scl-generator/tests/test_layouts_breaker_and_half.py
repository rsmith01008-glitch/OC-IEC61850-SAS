import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind, EQUIP_CBR, EQUIP_DIS
from generator.layouts import breaker_and_half
from generator.layouts.common import breakers_bounding


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


def _cbr(vl):
    return [b for b in vl.breakers if b.equip_type == EQUIP_CBR]


class TestBreakerAndHalf(unittest.TestCase):
    def test_two_taps_matches_switchyard_scd_diameter1(self):
        taps = _taps(("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
        vl = breaker_and_half.build("V800", 800, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.BREAKER_AND_HALF)
        self.assertEqual([b.name for b in _cbr(vl)], ["CB1", "CB2", "CB3"])
        self.assertEqual(len(vl.bays), 3)  # BusA, BusB, Diameter1

        bus_a_bay = next(b for b in vl.bays if b.name == "BusA")
        bus_b_bay = next(b for b in vl.bays if b.name == "BusB")
        bus_a = bus_a_bay.connectivity_nodes[0]
        bus_b = bus_b_bay.connectivity_nodes[0]
        n1 = vl.tap_node_for(taps[0])  # Line1 (LINE -- gets an exit disconnect too)
        n2 = vl.tap_node_for(taps[1])  # XfmrHV (TRANSFORMER -- no exit disconnect)

        cb1, cb2, cb3 = _cbr(vl)
        # Terminals no longer touch bus_a/n1/n2 directly (each breaker is
        # now flanked by its own isolating DIS -- see
        # generator/layouts/common.py's add_isolating_disconnects), but
        # breakers_bounding still resolves through those disconnects to
        # the same real breaker on each side, which is what actually
        # matters (remote-trip/interlock derivation, IED wiring).
        self.assertEqual(breakers_bounding(bus_a, vl.breakers), [cb1])
        self.assertEqual(breakers_bounding(n1, vl.breakers), [cb1, cb2])
        self.assertEqual(breakers_bounding(n2, vl.breakers), [cb2, cb3])
        self.assertEqual(breakers_bounding(bus_b, vl.breakers), [cb3])

    def test_every_breaker_gets_disconnects_on_both_sides(self):
        taps = _taps(("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
        vl = breaker_and_half.build("V800", 800, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        for cb in ("CB1", "CB2", "CB3"):
            self.assertIn("%sDA" % cb, dis_names)
            self.assertIn("%sDB" % cb, dis_names)

    def test_line_feeder_taps_get_exit_disconnect_transformer_does_not(self):
        taps = _taps(("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
        vl = breaker_and_half.build("V800", 800, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        self.assertIn("Line1D", dis_names)
        self.assertNotIn("XfmrHVD", dis_names)

    def test_all_line_feeder_diameter_has_eight_disconnects(self):
        # 3 breakers x 2 (bus/tap side each) + 2 tap exits (both taps
        # are line/feeder) = 8 -- matches the reference one-line diagram
        # this tool was corrected against.
        taps = _taps(("Line1", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = breaker_and_half.build("V800", 800, taps)
        n_dis = sum(1 for b in vl.breakers if b.equip_type == EQUIP_DIS)
        self.assertEqual(n_dis, 8)

    def test_four_taps_makes_two_diameters(self):
        taps = _taps(
            ("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER),
            ("Line2", TapKind.LINE), ("Feed1", TapKind.FEEDER),
        )
        vl = breaker_and_half.build("V800", 800, taps)
        self.assertEqual([b.name for b in _cbr(vl)], ["CB1", "CB2", "CB3", "CB4", "CB5", "CB6"])
        diameter_bays = [b for b in vl.bays if b.name.startswith("Diameter")]
        self.assertEqual(len(diameter_bays), 2)
        self.assertEqual(len([b for b in diameter_bays[0].breakers if b.equip_type == EQUIP_CBR]), 3)
        self.assertEqual(len([b for b in diameter_bays[1].breakers if b.equip_type == EQUIP_CBR]), 3)

    def test_start_index_offsets_breaker_numbering(self):
        taps = _taps(("Xfmr1LV", TapKind.TRANSFORMER), ("Feed1", TapKind.FEEDER))
        vl = breaker_and_half.build("V230", 230, taps, start_index=4)
        self.assertEqual([b.name for b in _cbr(vl)], ["CB4", "CB5", "CB6"])

    def test_rejects_odd_tap_count(self):
        taps = _taps(("Line1", TapKind.LINE))
        with self.assertRaises(ValueError):
            breaker_and_half.build("V800", 800, taps)

    def test_rejects_zero_taps(self):
        with self.assertRaises(ValueError):
            breaker_and_half.build("V800", 800, [])


if __name__ == "__main__":
    unittest.main()
