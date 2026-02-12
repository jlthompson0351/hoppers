from __future__ import annotations

import unittest

from src.core.plc_profile import PlcProfileCurve


class PlcProfileCurveTests(unittest.TestCase):
    def test_interpolates_between_points(self) -> None:
        curve = PlcProfileCurve(
            output_mode="0_10V",
            points=[(0.0, 0.0), (25.0, 1.0), (50.0, 2.0)],
        )
        self.assertAlmostEqual(curve.analog_from_weight(25.0), 1.0, places=6)
        self.assertAlmostEqual(curve.analog_from_weight(37.5), 1.5, places=6)

    def test_extrapolates_outside_defined_range(self) -> None:
        curve = PlcProfileCurve(
            output_mode="0_10V",
            points=[(0.0, 0.0), (25.0, 1.0), (50.0, 2.0)],
        )
        self.assertAlmostEqual(curve.analog_from_weight(-25.0), -1.0, places=6)
        self.assertAlmostEqual(curve.analog_from_weight(75.0), 3.0, places=6)

    def test_duplicate_weight_points_are_collapsed(self) -> None:
        curve = PlcProfileCurve(
            output_mode="0_10V",
            points=[(0.0, 0.0), (25.0, 1.0), (25.0, 1.2), (50.0, 2.0)],
        )
        self.assertAlmostEqual(curve.analog_from_weight(25.0), 1.1, places=6)

    def test_requires_two_unique_weights(self) -> None:
        with self.assertRaises(ValueError):
            PlcProfileCurve(output_mode="0_10V", points=[(25.0, 1.0), (25.0, 1.1)])


if __name__ == "__main__":
    unittest.main()
