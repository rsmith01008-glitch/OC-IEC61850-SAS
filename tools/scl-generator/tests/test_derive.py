import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import Tap, TapKind
from generator.layouts import breaker_and_half, single_bus, main_and_transfer, ring_bus, transformer_lv
from generator.derive import remote_trips_for, illustrative_interlocks


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


def _switchyard_transformer():
    """Rebuild switchyard.scd's own topology: 2 diameters in one real
    switchyard (V800), XFMR1 tapping N2 (its HV tap) with a simple LV
    output stub (see generator/layouts/transformer_lv.py) -- never a
    second real switchyard.
    """
    hv_taps = _taps(("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
    hv_vl = breaker_and_half.build("V800", 800, hv_taps, start_index=1)
    hv_tap = hv_vl.tap_node_for(hv_taps[1])
    xfmr = transformer_lv.build_transformer(
        "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
    )
    return hv_vl, xfmr


class TestRemoteTripsBreakerAndHalf(unittest.TestCase):
    def test_reproduces_switchyard_scd_two_breaker_fanout(self):
        hv_vl, xfmr = _switchyard_transformer()
        trips = remote_trips_for(xfmr)
        names = sorted(b.name for b in trips)
        # CB2/CB3 bound the HV tap (N2) -- the LV side has no IED to trip.
        self.assertEqual(names, ["CB2", "CB3"])


class TestRemoteTripsSingleBus(unittest.TestCase):
    def test_only_one_breaker_bounds_a_tap(self):
        hv_taps = _taps(("XfmrHV", TapKind.TRANSFORMER))
        hv_vl = single_bus.build("V800", 800, hv_taps)
        hv_tap = hv_vl.tap_node_for(hv_taps[0])
        xfmr = transformer_lv.build_transformer(
            "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
        )
        trips = remote_trips_for(xfmr)
        self.assertEqual(sorted(b.name for b in trips), ["CB1"])


class TestRemoteTripsRingBus(unittest.TestCase):
    def test_two_breakers_bound_a_ring_tap(self):
        hv_taps = _taps(("Line1", TapKind.LINE), ("Line2", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
        hv_vl = ring_bus.build("V800", 800, hv_taps)
        hv_tap = hv_vl.tap_node_for(hv_taps[2])
        xfmr = transformer_lv.build_transformer(
            "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
        )
        trips = remote_trips_for(xfmr)
        self.assertEqual(len(trips), 2)


class TestIllustrativeInterlocksBreakerAndHalf(unittest.TestCase):
    def test_reproduces_switchyard_scd_pairs_exactly(self):
        hv_vl, _ = _switchyard_transformer()
        hv_pairs = illustrative_interlocks(hv_vl)
        self.assertEqual([(a.name, b.name) for a, b in hv_pairs], [("CB1", "CB2")])

    def test_does_not_also_interlock_the_second_breaker_pair(self):
        hv_vl, _ = _switchyard_transformer()
        pairs = illustrative_interlocks(hv_vl)
        involved = {name for pair in pairs for name in (pair[0].name, pair[1].name)}
        self.assertNotIn("CB3", involved)  # CB2<->CB3 must NOT also appear


class TestIllustrativeInterlocksTransformerLv(unittest.TestCase):
    def test_lv_stub_never_produces_interlocks(self):
        # Every LV output tap is bounded by exactly 1 DIS, never 2
        # breakers -- the LV stub is not a junction, so it can never
        # qualify under illustrative_interlocks' "exactly 2 bounding
        # breakers" rule.
        _, xfmr = _switchyard_transformer()
        self.assertEqual(illustrative_interlocks(xfmr.lv_vl), [])


class TestIllustrativeInterlocksNoJunction(unittest.TestCase):
    def test_single_bus_never_produces_interlocks(self):
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER), ("Feed3", TapKind.FEEDER))
        vl = single_bus.build("V13", 13.8, taps)
        self.assertEqual(illustrative_interlocks(vl), [])

    def test_main_and_transfer_never_produces_interlocks_even_with_one_tap(self):
        # Degenerate 1-tap case: MainBus is bounded by exactly 2
        # breakers (the tap breaker + the tie breaker) -- but MainBus is
        # a BusNode, not a TapNode, so it must never qualify.
        taps = _taps(("Feed1", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)
        self.assertEqual(illustrative_interlocks(vl), [])

    def test_main_and_transfer_never_produces_interlocks_with_several_taps(self):
        taps = _taps(("Feed1", TapKind.FEEDER), ("Feed2", TapKind.FEEDER), ("Feed3", TapKind.FEEDER))
        vl = main_and_transfer.build("V13", 13.8, taps)
        self.assertEqual(illustrative_interlocks(vl), [])


class TestIllustrativeInterlocksRingBus(unittest.TestCase):
    def test_ring_produces_nonoverlapping_pairs(self):
        taps = _taps(*[("T%d" % i, TapKind.FEEDER) for i in range(5)])
        vl = ring_bus.build("V69", 69, taps)
        pairs = illustrative_interlocks(vl)
        self.assertGreater(len(pairs), 0)
        seen = set()
        for a, b in pairs:
            self.assertNotIn(a.name, seen)
            self.assertNotIn(b.name, seen)
            seen.add(a.name)
            seen.add(b.name)


if __name__ == "__main__":
    unittest.main()
