import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import (
    Tap, TapKind, TapNode, BusNode, Breaker, VoltageLevelBuild,
    LayoutKind, Station,
)
from generator.layouts import transformer_lv


def _vl(name, kv, tap_names):
    taps = [Tap(n, TapKind.TRANSFORMER) for n in tap_names]
    vl = VoltageLevelBuild(vl_name=name, kv=kv, layout_kind=LayoutKind.SINGLE_BUS, taps=taps)
    bus = BusNode("Bus")
    vl.nodes.append(bus)
    for tap in taps:
        tap_node = TapNode(tap.name, tap=tap)
        vl.nodes.append(tap_node)
        vl.breakers.append(Breaker("CB_%s" % tap.name, bus, tap_node))
    return vl


class TestTapNode(unittest.TestCase):
    def test_requires_a_tap(self):
        with self.assertRaises(ValueError):
            TapNode("N1", tap=None)

    def test_holds_its_tap(self):
        tap = Tap("Line1", TapKind.LINE)
        node = TapNode("N1", tap=tap)
        self.assertIs(node.tap, tap)


class TestBreaker(unittest.TestCase):
    def test_other_node(self):
        a, b = BusNode("A"), BusNode("B")
        br = Breaker("CB1", a, b)
        self.assertIs(br.other_node(a), b)
        self.assertIs(br.other_node(b), a)

    def test_other_node_rejects_foreign_node(self):
        a, b, c = BusNode("A"), BusNode("B"), BusNode("C")
        br = Breaker("CB1", a, b)
        with self.assertRaises(ValueError):
            br.other_node(c)


class TestVoltageLevelBuild(unittest.TestCase):
    def test_tap_node_for(self):
        vl = _vl("V800", 800, ["XfmrHV"])
        tap = vl.taps[0]
        node = vl.tap_node_for(tap)
        self.assertEqual(node.name, "XfmrHV")

    def test_tap_node_for_raises_on_unknown_tap(self):
        vl = _vl("V800", 800, ["XfmrHV"])
        foreign = Tap("Other", TapKind.LINE)
        with self.assertRaises(ValueError):
            vl.tap_node_for(foreign)


class TestTransformer(unittest.TestCase):
    """Transformers are now built through
    generator/layouts/transformer_lv.py's build_transformer -- its LV
    side is always a freshly built, non-redundant stub (never a second
    independently-laid-out switchyard), so there is no "same voltage
    level" or "same VL object" case to guard against any more.
    """

    def test_scale_matches_worked_example(self):
        hv_vl = _vl("V800", 800, ["XfmrHV"])
        hv_tap = hv_vl.tap_node_for(hv_vl.taps[0])
        xfmr = transformer_lv.build_transformer(
            "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
        )
        self.assertEqual(xfmr.scale_hv, 1.0)
        self.assertAlmostEqual(xfmr.scale_lv, 800 / 230, places=3)

    def test_rejects_hv_not_higher_than_lv(self):
        hv_vl = _vl("V230", 230, ["XfmrHV"])
        hv_tap = hv_vl.tap_node_for(hv_vl.taps[0])
        with self.assertRaises(ValueError):
            transformer_lv.build_transformer(
                "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
            )

    def test_lv_side_is_a_distinct_non_selectable_stub(self):
        hv_vl = _vl("V800", 800, ["XfmrHV"])
        hv_tap = hv_vl.tap_node_for(hv_vl.taps[0])
        xfmr = transformer_lv.build_transformer(
            "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
        )
        self.assertIsNot(xfmr.lv_vl, hv_vl)
        self.assertEqual(xfmr.lv_vl.layout_kind, LayoutKind.TRANSFORMER_LV)


class TestStation(unittest.TestCase):
    def test_all_breakers_in_station_order(self):
        vl1 = _vl("V800", 800, ["Line1", "XfmrHV"])
        vl2 = _vl("V230", 230, ["XfmrLV", "Feed1"])
        station = Station(name="Switchyard1", voltage_levels=[vl1, vl2])
        names = [b.name for b in station.all_breakers()]
        self.assertEqual(names, ["CB_Line1", "CB_XfmrHV", "CB_XfmrLV", "CB_Feed1"])

    def test_find_vl(self):
        vl1 = _vl("V800", 800, ["Line1"])
        station = Station(name="Switchyard1", voltage_levels=[vl1])
        self.assertIs(station.find_vl("V800"), vl1)
        with self.assertRaises(KeyError):
            station.find_vl("V999")


if __name__ == "__main__":
    unittest.main()
