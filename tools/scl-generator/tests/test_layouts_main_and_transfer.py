import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind, EQUIP_CBR, EQUIP_DIS
from generator.layouts import main_and_transfer
from generator.layouts.common import breakers_bounding


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


def _cbr(vl):
    return [b for b in vl.breakers if b.equip_type == EQUIP_CBR]


class TestMainAndTransfer(unittest.TestCase):
    def test_two_taps_plus_tie_breaker(self):
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.MAIN_AND_TRANSFER)
        self.assertEqual([b.name for b in _cbr(vl)], ["CB1", "CB2", "CB3"])  # 2 taps + 1 tie

        main_bus = next(b for b in vl.bays if b.name == "MainBus").connectivity_nodes[0]
        transfer_bus = next(b for b in vl.bays if b.name == "TransferBus").connectivity_nodes[0]

        cb1, cb2, tie = _cbr(vl)
        n1 = vl.tap_node_for(taps[0])
        n2 = vl.tap_node_for(taps[1])
        # Every breaker (including the tie) is now flanked by its own
        # isolating DIS rather than touching main/transfer bus or a tap
        # directly -- breakers_bounding resolves through those.
        self.assertEqual(breakers_bounding(n1, vl.breakers), [cb1])
        self.assertEqual(breakers_bounding(n2, vl.breakers), [cb2])
        self.assertEqual(breakers_bounding(transfer_bus, vl.breakers), [tie])
        self.assertEqual(set(breakers_bounding(main_bus, vl.breakers)), {cb1, cb2, tie})

    def test_tie_breaker_is_the_only_thing_touching_transfer_bus(self):
        # Locks in the documented bypass-not-modeled scoping decision:
        # no tap breaker ever bounds TransferBus.
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER), ("Feed3", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)
        transfer_bus = next(b for b in vl.bays if b.name == "TransferBus").connectivity_nodes[0]
        touching = breakers_bounding(transfer_bus, vl.breakers)
        self.assertEqual(len(touching), 1)
        self.assertEqual(touching[0].name, "CB4")  # the tie breaker, last one built

    def test_every_breaker_including_tie_gets_disconnects_on_both_sides(self):
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)
        dis_names = {b.name for b in vl.breakers if b.equip_type == EQUIP_DIS}
        for cb in ("CB1", "CB2", "CB3"):  # CB3 is the tie
            self.assertIn("%sDA" % cb, dis_names)
            self.assertIn("%sDB" % cb, dis_names)

    def test_rejects_zero_taps(self):
        with self.assertRaises(ValueError):
            main_and_transfer.build("V13", 13.8, [])


if __name__ == "__main__":
    unittest.main()
