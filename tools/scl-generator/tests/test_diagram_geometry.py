import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree

from generator.diagram import layout_geometry as geo
from generator.diagram import draw_transformer, onelinediagram, tap_symbols
from generator.layouts import breaker_and_half, single_bus, transformer_lv
from generator.topology import Tap, TapKind, Station


class TestStripLayout(unittest.TestCase):
    def test_strip_y0_increasing_with_rank(self):
        self.assertLess(geo.strip_y0(0), geo.strip_y0(1))
        self.assertLess(geo.strip_y0(1), geo.strip_y0(2))

    def test_strip_y0_spacing_matches_height_plus_gap(self):
        self.assertAlmostEqual(geo.strip_y0(1) - geo.strip_y0(0), geo.STRIP_HEIGHT + geo.STRIP_GAP)

    def test_total_height_grows_with_strip_count(self):
        self.assertLess(geo.total_height(1), geo.total_height(2))
        self.assertLess(geo.total_height(2), geo.total_height(3))

    def test_total_height_zero_strips(self):
        self.assertEqual(geo.total_height(0), geo.TITLE_HEIGHT)


class TestTapX(unittest.TestCase):
    def test_tap_x_increasing(self):
        self.assertLess(geo.tap_x(0), geo.tap_x(1))
        self.assertAlmostEqual(geo.tap_x(1) - geo.tap_x(0), geo.TAP_PITCH)

    def test_strip_width_grows_with_tap_count(self):
        self.assertLess(geo.strip_width(1), geo.strip_width(2))
        self.assertGreater(geo.strip_width(0), 0)


class TestBranchStubClearsItsOwnColumn(unittest.TestCase):
    """A line/feeder tap branching sideways off a vertical diameter
    string (draw_breaker_and_half.py) must clear its own exit disconnect
    of that string -- the string continues on both sides of the branch
    point, so a disconnect tick centered too close to it visually
    crosses back over the string it just branched off of.
    """

    def test_exit_disconnect_tick_does_not_cross_the_origin_column(self):
        x, y = 100.0, 50.0
        svg = "".join(tap_symbols.draw_tap_with_exit_horizontal(x, y, 1, Tap("Line1", TapKind.LINE)))
        endpoints = re.findall(r'x1="([\d.+-]+)"[^/]*x2="([\d.+-]+)"', svg)
        self.assertTrue(endpoints)
        # every drawn line segment's endpoints must stay on the branch
        # side of x (the column this tap branches off of)
        for x1, x2 in endpoints:
            self.assertGreaterEqual(float(x1), x)
            self.assertGreaterEqual(float(x2), x)


class TestDiameterX(unittest.TestCase):
    def test_diameter_x_increasing(self):
        self.assertLess(geo.diameter_x(0), geo.diameter_x(1))
        self.assertAlmostEqual(geo.diameter_x(1) - geo.diameter_x(0), geo.DIAMETER_PITCH)

    def test_diameter_strip_width_grows_with_diameter_count(self):
        self.assertLess(geo.diameter_strip_width(1), geo.diameter_strip_width(2))
        self.assertGreater(geo.diameter_strip_width(0), 0)

    def test_branch_len_fits_within_diameter_pitch(self):
        # A tap's sideways branch must never reach the next diameter's
        # own vertical string (see draw_breaker_and_half.py).
        self.assertLess(geo.BRANCH_LEN, geo.DIAMETER_PITCH)


class TestRingGeometry(unittest.TestCase):
    def test_ring_radius_grows_with_tap_count(self):
        self.assertLess(geo.ring_radius(3), geo.ring_radius(6))

    def test_ring_radius_has_a_floor(self):
        self.assertEqual(geo.ring_radius(1), 80.0)
        self.assertEqual(geo.ring_radius(2), 80.0)

    def test_breaker_angles_evenly_spaced(self):
        n = 4
        angles = [geo.ring_breaker_angle(i, n) for i in range(n)]
        diffs = [angles[i + 1] - angles[i] for i in range(n - 1)]
        for d in diffs:
            self.assertAlmostEqual(d, 2 * math.pi / n)

    def test_breaker_zero_at_twelve_oclock(self):
        # 12 o'clock in SVG screen coords (y grows downward) is angle -pi/2.
        self.assertAlmostEqual(geo.ring_breaker_angle(0, 4), -math.pi / 2)

    def test_tap_angle_is_midpoint_of_its_two_neighboring_breakers(self):
        n = 5
        for i in range(n):
            b_prev = geo.ring_breaker_angle(i - 1, n)
            b_here = geo.ring_breaker_angle(i, n)
            expected_mid = (b_prev + b_here) / 2
            self.assertAlmostEqual(geo.ring_tap_angle(i, n), expected_mid)

    def test_point_on_circle_at_zero_angle_is_directly_right_of_center(self):
        center = (100.0, 100.0)
        x, y = geo.point_on_circle(center, 50.0, 0.0)
        self.assertAlmostEqual(x, 150.0)
        self.assertAlmostEqual(y, 100.0)

    def test_point_on_circle_radius_is_correct_distance_from_center(self):
        center = (50.0, 50.0)
        for angle in (0.0, 1.0, 3.14, -2.0):
            x, y = geo.point_on_circle(center, 30.0, angle)
            dist = math.hypot(x - center[0], y - center[1])
            self.assertAlmostEqual(dist, 30.0)

    def test_ring_center_is_horizontally_offset_by_radius_plus_margin(self):
        cx, cy = geo.ring_center(strip_top=0.0, radius=90.0)
        self.assertAlmostEqual(cx, geo.LEFT_MARGIN + 90.0)
        self.assertAlmostEqual(cy, geo.STRIP_HEIGHT / 2)


class TestTransformerBand(unittest.TestCase):
    """draw_transformer.py draws a transformer's symbol+LV-output-fan in
    a shared band below every real switchyard strip -- never a second
    strip of its own (see that module's header)."""

    def test_band_height_is_positive_and_fixed(self):
        self.assertGreater(draw_transformer.band_height(), 0)

    def test_draw_returns_nonempty_elements_for_each_output(self):
        elements = draw_transformer.draw(
            "XFMR1", hv_point=(100.0, 50.0), lv_kv=230, lv_outputs=[
                Tap("Feed1", TapKind.FEEDER), Tap("Feed2", TapKind.LINE),
            ], band_top=0.0,
        )
        # draw_transformer wraps its output in one <g> per call.
        self.assertEqual(len(elements), 1)
        self.assertIn("<g>", elements[0])
        self.assertIn("XFMR1", elements[0])
        self.assertIn("Feed1", elements[0])
        self.assertIn("Feed2", elements[0])

    def test_single_output_is_inline_with_the_transformer_body(self):
        # The LV fan is centered on body_x (the winding symbol's own x),
        # not offset from it -- unlike the HV run above the symbol,
        # there's no breaker/bus-rail column below it for a centered
        # output to be confused with (see this module's header).
        hv_x = 100.0
        svg = draw_transformer.draw(
            "XFMR1", hv_point=(hv_x, 50.0), lv_kv=230,
            lv_outputs=[Tap("Feed1", TapKind.FEEDER)], band_top=0.0,
        )[0]
        m = re.search(r'<text x="([\d.+-]+)"[^>]*>Feed1<', svg)
        self.assertIsNotNone(m)
        circle_cx = [float(c) for c in re.findall(r'<circle cx="([\d.+-]+)"', svg)]
        body_x = sum(circle_cx) / len(circle_cx)
        self.assertAlmostEqual(float(m.group(1)), body_x, delta=1)

    def test_max_x_grows_with_output_count_and_clears_hv_x(self):
        self.assertGreater(draw_transformer.max_x(100.0, 1), 100.0)
        self.assertLess(draw_transformer.max_x(100.0, 1), draw_transformer.max_x(100.0, 3))

    def test_winding_symbol_itself_is_offset_off_the_hv_tap_column(self):
        # The whole body (not just the LV fan) must be jogged off hv_x,
        # not just drawn on a straight vertical line down from the tap --
        # a straight run reads as if the HV side ties directly to
        # whatever breaker/bus sits below the tap in the switchyard
        # column (see this module's header).
        hv_x = 100.0
        svg = draw_transformer.draw(
            "XFMR1", hv_point=(hv_x, 50.0), lv_kv=230,
            lv_outputs=[Tap("Feed1", TapKind.FEEDER)], band_top=0.0,
        )[0]
        circle_cx = [float(m) for m in re.findall(r'<circle cx="([\d.+-]+)"', svg)]
        self.assertTrue(circle_cx)
        for cx in circle_cx:
            self.assertGreater(abs(cx - hv_x), 30)


class TestOneLineDiagramRender(unittest.TestCase):
    """Full-Station smoke tests: the diagram must be well-formed SVG
    whether or not the station has a transformer -- this is what
    regressed when a transformer's LV side stopped being a second real
    strip (KeyError on tap_positions[xfmr.lv_tap]) before draw_transformer.py
    /onelinediagram.py were reworked to draw it as a band instead.
    """

    def test_renders_well_formed_svg_with_no_transformers(self):
        taps = [Tap("Feed1", TapKind.FEEDER)]
        vl = single_bus.build("V13", 13.8, taps)
        svg = onelinediagram.render(Station(name="NoXfmr", voltage_levels=[vl]))
        root = etree.fromstring(svg.encode())
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_renders_well_formed_svg_with_a_transformer(self):
        hv_taps = [Tap("Line1", TapKind.LINE), Tap("XfmrHV", TapKind.TRANSFORMER)]
        hv_vl = breaker_and_half.build("V800", 800, hv_taps, start_index=1)
        hv_tap = hv_vl.tap_node_for(hv_taps[1])
        xfmr = transformer_lv.build_transformer(
            "XFMR1", hv_vl, hv_tap, lv_kv=230, lv_outputs=[("Feed1", TapKind.FEEDER)],
        )
        station = Station(name="WithXfmr", voltage_levels=[hv_vl], transformers=[xfmr])
        svg = onelinediagram.render(station)
        root = etree.fromstring(svg.encode())
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("XFMR1", svg)

    def test_renders_well_formed_svg_with_multiple_diameters(self):
        # Each diameter is its own vertical string (see
        # draw_breaker_and_half.py) -- this locks in that the strip
        # width scales with diameter count, not tap count, and that a
        # second diameter's own tap positions don't collide with the
        # first's.
        taps = [
            Tap("Line1", TapKind.LINE), Tap("Line2", TapKind.LINE),
            Tap("Line3", TapKind.LINE), Tap("Line4", TapKind.LINE),
        ]
        vl = breaker_and_half.build("V800", 800, taps)
        svg = onelinediagram.render(Station(name="MultiDiameter", voltage_levels=[vl]))
        root = etree.fromstring(svg.encode())
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        width = float(root.get("width"))
        self.assertGreaterEqual(width, geo.diameter_strip_width(2) + geo.LEFT_MARGIN)


if __name__ == "__main__":
    unittest.main()
