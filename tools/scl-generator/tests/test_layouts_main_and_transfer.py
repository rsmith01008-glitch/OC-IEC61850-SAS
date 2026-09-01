import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind, LayoutKind
from generator.layouts import main_and_transfer


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


class TestMainAndTransfer(unittest.TestCase):
    def test_two_taps_plus_tie_breaker(self):
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)

        self.assertEqual(vl.layout_kind, LayoutKind.MAIN_AND_TRANSFER)
        self.assertEqual([b.name for b in vl.breakers], ["CB1", "CB2", "CB3"])  # 2 taps + 1 tie

        main_bus = next(b for b in vl.bays if b.name == "MainBus").connectivity_nodes[0]
        transfer_bus = next(b for b in vl.bays if b.name == "TransferBus").connectivity_nodes[0]

        cb1, cb2, tie = vl.breakers
        n1 = vl.tap_node_for(taps[0])
        n2 = vl.tap_node_for(taps[1])
        self.assertEqual({cb1.node_a, cb1.node_b}, {main_bus, n1})
        self.assertEqual({cb2.node_a, cb2.node_b}, {main_bus, n2})
        self.assertEqual({tie.node_a, tie.node_b}, {main_bus, transfer_bus})

    def test_tie_breaker_is_the_only_thing_touching_transfer_bus(self):
        # Locks in the documented bypass-not-modeled scoping decision:
        # no tap breaker ever references TransferBus.
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER), ("Feed3", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)
        transfer_bus = next(b for b in vl.bays if b.name == "TransferBus").connectivity_nodes[0]
        touching = [b for b in vl.breakers if transfer_bus in (b.node_a, b.node_b)]
        self.assertEqual(len(touching), 1)
        self.assertEqual(touching[0].name, "CB4")  # the tie breaker, last one built

    def test_rejects_zero_taps(self):
        with self.assertRaises(ValueError):
            main_and_transfer.build("V13", 13.8, [])


if __name__ == "__main__":
    unittest.main()
