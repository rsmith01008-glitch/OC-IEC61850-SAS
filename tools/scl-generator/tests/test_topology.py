import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.topology import (
    Tap, TapKind, TapNode, BusNode, Breaker, VoltageLevelBuild,
    Transformer, LayoutKind, Station,
)


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
    def test_scale_matches_worked_example(self):
        hv_vl = _vl("V800", 800, ["XfmrHV"])
        lv_vl = _vl("V230", 230, ["XfmrLV"])
        xfmr = Transformer(
            name="XFMR1", hv_vl=hv_vl, hv_tap=hv_vl.tap_node_for(hv_vl.taps[0]),
            lv_vl=lv_vl, lv_tap=lv_vl.tap_node_for(lv_vl.taps[0]),
        )
        self.assertEqual(xfmr.scale_hv, 1.0)
        self.assertAlmostEqual(xfmr.scale_lv, 800 / 230, places=3)

    def test_rejects_hv_not_higher_than_lv(self):
        vl_a = _vl("V230a", 230, ["Tap1"])
        vl_b = _vl("V230b", 230, ["Tap2"])
        with self.assertRaises(ValueError):
            Transformer(
                name="XFMR1", hv_vl=vl_a, hv_tap=vl_a.tap_node_for(vl_a.taps[0]),
                lv_vl=vl_b, lv_tap=vl_b.tap_node_for(vl_b.taps[0]),
            )

    def test_rejects_same_voltage_level(self):
        vl = _vl("V800", 800, ["Tap1", "Tap2"])
        with self.assertRaises(ValueError):
            Transformer(
                name="XFMR1", hv_vl=vl, hv_tap=vl.tap_node_for(vl.taps[0]),
                lv_vl=vl, lv_tap=vl.tap_node_for(vl.taps[1]),
            )


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
