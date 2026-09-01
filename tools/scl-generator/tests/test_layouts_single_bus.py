import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind, EQUIP_CBR, EQUIP_DIS
from generator.layouts import single_bus
from generator.layouts.common import breakers_bounding


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


def _cbr(vl):
    return [b for b in vl.breakers if b.equip_type == EQUIP_CBR]


class TestSingleBus(unittest.TestCase):
    def test_three_taps_off_one_bus(self):
        taps = _taps(("Line1", TapKind.LINE), ("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.SINGLE_BUS)
        self.assertEqual([b.name for b in _cbr(vl)], ["CB1", "CB2", "CB3"])
        self.assertEqual(len(vl.bays), 4)  # Bus + 3 tap bays

        bus = next(n for n in vl.nodes if n.name == "Bus")
        bus_breakers = breakers_bounding(bus, vl.breakers)
        self.assertEqual(bus_breakers, _cbr(vl))
        for i, breaker in enumerate(_cbr(vl)):
            tap_node = vl.tap_node_for(taps[i])
            # Each breaker is now flanked by its own isolating DIS (see
            # generator/layouts/common.py) rather than touching bus/tap
            # directly -- breakers_bounding still resolves through them.
            self.assertIn(breaker, bus_breakers)
            self.assertEqual(breakers_bounding(tap_node, vl.breakers), [breaker])

    def test_every_breaker_gets_disconnects_on_both_sides(self):
        taps = _taps(("Line1", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        for cb in ("CB1", "CB2"):
            self.assertIn("%sDA" % cb, dis_names)
            self.assertIn("%sDB" % cb, dis_names)

    def test_line_feeder_taps_get_exit_disconnect(self):
        taps = _taps(("Line1", TapKind.LINE), ("Feed1", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        self.assertIn("Line1D", dis_names)
        self.assertIn("Feed1D", dis_names)

    def test_start_index_offset(self):
        taps = _taps(("Feed1", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps, start_index=7)
        self.assertEqual(_cbr(vl)[0].name, "CB7")

    def test_rejects_zero_taps(self):
        with self.assertRaises(ValueError):
            single_bus.build("V13", 13.8, [])


if __name__ == "__main__":
    unittest.main()
