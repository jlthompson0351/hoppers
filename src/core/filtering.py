from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional


@dataclass
class IIRLowPass:
    """Simple exponential low-pass filter.

    y[n] = y[n-1] + alpha * (x[n] - y[n-1])
    alpha in (0, 1], higher alpha = faster response / less filtering.
    """

    alpha: float
    y: Optional[float] = None

    def update(self, x: float) -> float:
        x = float(x)
        a = float(self.alpha)
        if self.y is None:
            self.y = x
            return x
        self.y = self.y + a * (x - self.y)
        return float(self.y)


class KalmanFilter:
    """1D Kalman filter for load cell weight estimation.

    Optimized for speed and accuracy in production weighing/counting.
    Pure Python, no dependencies.

    Key advantage over IIR/moving average:
    - Zero lag: Responds instantly to real weight changes
    - Optimal noise reduction: Distinguishes noise from real signal changes
    - Tunable: Adjust process_noise and measurement_noise per mode

    Usage:
        kf = KalmanFilter(process_noise=1.0, measurement_noise=2000.0)
        filtered_value = kf.update(raw_reading)
    """

    def __init__(
        self,
        process_noise: float = 1.0,
        measurement_noise: float = 2000.0,
        initial_value: float = 0.0,
    ) -> None:
        """Initialize Kalman filter.

        Args:
            process_noise: Q - How much true weight changes between readings.
                           Low = stable weight (hopper sitting), High = fast changes.
            measurement_noise: R - How noisy ADC readings are (in raw counts/units).
                               Low = trust measurements more, High = filter more.
            initial_value: Starting estimate.
        """
        # State estimate (best guess of true weight)
        self.x: float = float(initial_value)

        # Estimation error covariance (confidence in estimate)
        self.P: float = 1000.0

        # Process noise covariance
        self.Q: float = float(process_noise)

        # Measurement noise covariance
        self.R: float = float(measurement_noise)

    def predict(self) -> None:
        """Prediction step: Estimate next state (weight doesn't change on its own)."""
        # x = F * x, where F = 1 (state transition)
        # P = F * P * F + Q
        self.P = self.P + self.Q

    def update(self, measurement: float) -> float:
        """Update step: Correct prediction with new measurement.

        Args:
            measurement: Raw sensor reading.

        Returns:
            Filtered estimate.
        """
        measurement = float(measurement)

        # Predict first
        self.predict()

        # Innovation (residual): difference between measurement and prediction
        y = measurement - self.x

        # Innovation covariance
        S = self.P + self.R

        # Kalman gain: how much to trust the measurement
        K = self.P / S

        # Update state estimate
        self.x = self.x + K * y

        # Update error covariance
        self.P = (1.0 - K) * self.P

        return self.x

    def reset(self, value: float = 0.0) -> None:
        """Reset filter state to a known value."""
        self.x = float(value)
        self.P = 1000.0


class MedianFilter:
    """Median (spike-rejection) filter over a sliding window.

    This is useful for rejecting occasional single-sample glitches from I2C/ADC
    before feeding Kalman/IIR filters.
    """

    def __init__(self, window: int = 5) -> None:
        w = max(1, int(window))
        # Median filters are typically odd-sized; coerce to odd to avoid ambiguity.
        if (w % 2) == 0:
            w += 1
        self.window = int(w)
        self._buf: Deque[float] = deque(maxlen=self.window)

    def reset(self) -> None:
        self._buf.clear()

    def update(self, x: float) -> float:
        x = float(x)
        self._buf.append(x)
        vals = sorted(self._buf)
        return float(vals[len(vals) // 2])


@dataclass
class NotchFilter:
    """Biquad notch filter (IIR) for a single signal stream.

    Typical use: attenuate 50/60 Hz power-line pickup when sampling fast enough.

    NOTE: This filter is only valid when f0 < fs/2 (Nyquist). If the configured
    f0 is not representable at the current sample rate, the filter auto-disables
    and becomes a pass-through.
    """

    f0_hz: float = 60.0
    fs_hz: float = 20.0
    q: float = 30.0

    # Coefficients (Direct Form I)
    _b0: float = 1.0
    _b1: float = 0.0
    _b2: float = 0.0
    _a1: float = 0.0
    _a2: float = 0.0

    # State
    _x1: float = 0.0
    _x2: float = 0.0
    _y1: float = 0.0
    _y2: float = 0.0
    _enabled: bool = False

    def __post_init__(self) -> None:
        self.configure(f0_hz=self.f0_hz, fs_hz=self.fs_hz, q=self.q)

    @property
    def enabled(self) -> bool:
        return bool(self._enabled)

    def reset(self) -> None:
        self._x1 = 0.0
        self._x2 = 0.0
        self._y1 = 0.0
        self._y2 = 0.0

    def configure(self, *, f0_hz: float | None = None, fs_hz: float | None = None, q: float | None = None) -> None:
        """(Re)configure the notch filter coefficients.

        This preserves existing state; call reset() if you want to clear history.
        """
        if f0_hz is not None:
            self.f0_hz = float(f0_hz)
        if fs_hz is not None:
            self.fs_hz = float(fs_hz)
        if q is not None:
            self.q = float(q)

        f0 = float(self.f0_hz)
        fs = float(self.fs_hz)
        qv = float(self.q)

        # Validate parameters
        if not (fs > 0.0) or not (f0 > 0.0) or not (qv > 0.0):
            self._enabled = False
            return
        # Nyquist constraint
        if f0 >= (fs * 0.5):
            self._enabled = False
            return

        w0 = 2.0 * math.pi * (f0 / fs)
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * qv)

        # Standard notch biquad (RBJ Audio EQ Cookbook)
        b0 = 1.0
        b1 = -2.0 * cos_w0
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

        if a0 == 0.0:
            self._enabled = False
            return

        # Normalize
        self._b0 = b0 / a0
        self._b1 = b1 / a0
        self._b2 = b2 / a0
        self._a1 = a1 / a0
        self._a2 = a2 / a0
        self._enabled = True

    def update(self, x: float) -> float:
        x = float(x)
        if not self._enabled:
            return x

        # Direct Form I
        y = (
            self._b0 * x
            + self._b1 * self._x1
            + self._b2 * self._x2
            - self._a1 * self._y1
            - self._a2 * self._y2
        )

        self._x2 = self._x1
        self._x1 = x
        self._y2 = self._y1
        self._y1 = y
        return float(y)


@dataclass
class StabilityDetector:
    """Windowed stability detector based on stddev and slope."""

    window: int = 25
    stddev_threshold: float = 0.8  # lb
    slope_threshold: float = 0.8  # lb/s (approx)
    _buf: Deque[float] = None
    _last: Optional[float] = None
    _last_dt: float = 0.0

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=int(self.window))

    def update(self, x: float, dt_s: float) -> bool:
        x = float(x)
        dt_s = max(1e-6, float(dt_s))
        self._buf.append(x)

        if self._last is None:
            self._last = x
            self._last_dt = dt_s
            return False

        slope = abs((x - self._last) / dt_s)
        self._last = x
        self._last_dt = dt_s

        if len(self._buf) < max(5, int(self.window * 0.6)):
            return False

        mean = sum(self._buf) / len(self._buf)
        var = sum((v - mean) ** 2 for v in self._buf) / max(1, len(self._buf) - 1)
        std = math.sqrt(var)

        return (std <= float(self.stddev_threshold)) and (slope <= float(self.slope_threshold))


