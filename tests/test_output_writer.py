from __future__ import annotations

import unittest

from src.core.plc_profile import PlcProfileCurve
from src.services.output_writer import OutputWriter


class OutputWriterTests(unittest.TestCase):
    # Fallback is 0-250 lb → 0-10V (25 lb/V) or 0-250 lb → 4-20mA.

    def test_linear_fallback_0_10v(self) -> None:
        writer = OutputWriter()
        self.assertAlmostEqual(
            writer.compute(weight_lb=0, output_mode="0_10V").value,
            0.0,
            places=6,
        )
        self.assertAlmostEqual(
            writer.compute(weight_lb=125, output_mode="0_10V").value,
            5.0,
            places=6,
        )
        self.assertAlmostEqual(
            writer.compute(weight_lb=250, output_mode="0_10V").value,
            10.0,
            places=6,
        )

    def test_linear_fallback_4_20ma(self) -> None:
        writer = OutputWriter()
        self.assertAlmostEqual(
            writer.compute(weight_lb=0, output_mode="4_20mA").value,
            4.0,
            places=6,
        )
        self.assertAlmostEqual(
            writer.compute(weight_lb=125, output_mode="4_20mA").value,
            12.0,
            places=6,
        )
        self.assertAlmostEqual(
            writer.compute(weight_lb=250, output_mode="4_20mA").value,
            20.0,
            places=6,
        )

    def test_fault_and_disarm_force_safe_output(self) -> None:
        writer = OutputWriter()
        safe_v = writer.compute(
            weight_lb=200,
            output_mode="0_10V",
            fault=True,
            armed=True,
            safe_v=1.23,
        )
        self.assertEqual(safe_v.units, "V")
        self.assertAlmostEqual(safe_v.value, 1.23, places=6)

        safe_ma = writer.compute(
            weight_lb=200,
            output_mode="4_20mA",
            fault=False,
            armed=False,
            safe_ma=6.5,
        )
        self.assertEqual(safe_ma.units, "mA")
        self.assertAlmostEqual(safe_ma.value, 6.5, places=6)

    def test_deadband_can_be_disabled(self) -> None:
        writer = OutputWriter()
        first = writer.compute(
            weight_lb=100.0,
            output_mode="0_10V",
            deadband_enabled=False,
            deadband_lb=10.0,
        )
        second = writer.compute(
            weight_lb=101.0,
            output_mode="0_10V",
            deadband_enabled=False,
            deadband_lb=10.0,
        )
        self.assertGreater(second.value, first.value)

    def test_ramp_limits_step_change(self) -> None:
        writer = OutputWriter()
        writer.compute(
            weight_lb=0.0,
            output_mode="0_10V",
            ramp_enabled=True,
            ramp_rate_v=1.0,  # 1 V/s
            dt_s=0.1,         # max 0.1 V step
            deadband_enabled=False,
        )
        stepped = writer.compute(
            weight_lb=250.0,
            output_mode="0_10V",
            ramp_enabled=True,
            ramp_rate_v=1.0,
            dt_s=0.1,
            deadband_enabled=False,
        )
        self.assertAlmostEqual(stepped.value, 0.1, places=6)

    def test_profile_curve_overrides_linear_fallback(self) -> None:
        writer = OutputWriter()
        profile = PlcProfileCurve(
            output_mode="0_10V",
            points=[(0.0, 0.0), (25.0, 1.0), (50.0, 2.0)],
        )
        # Profile should win over the fallback.
        cmd_25 = writer.compute(
            weight_lb=25.0,
            output_mode="0_10V",
            plc_profile=profile,
            deadband_enabled=False,
        )
        cmd_50 = writer.compute(
            weight_lb=50.0,
            output_mode="0_10V",
            plc_profile=profile,
            deadband_enabled=False,
        )
        self.assertAlmostEqual(cmd_25.value, 1.0, places=6)
        self.assertAlmostEqual(cmd_50.value, 2.0, places=6)

    def test_hw_clamp_prevents_over_range(self) -> None:
        """Even with extrapolation, output cannot exceed hardware limits."""
        writer = OutputWriter()
        # 500 lb on 0-250 fallback = 20V unclamped, but hardware cap = 10V
        cmd = writer.compute(weight_lb=500.0, output_mode="0_10V", deadband_enabled=False)
        self.assertAlmostEqual(cmd.value, 10.0, places=6)


if __name__ == "__main__":
    unittest.main()
