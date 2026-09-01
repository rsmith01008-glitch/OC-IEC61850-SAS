import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.diagram import layout_geometry as geo


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


if __name__ == "__main__":
    unittest.main()
