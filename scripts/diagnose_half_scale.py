#!/usr/bin/env python3
"""Half-scale PLC output diagnosis helper.

Workflow:
1) Arms outputs.
2) Commands fixed analog values via /api/output/test.
3) Prompts operator for DMM readings.
4) Classifies likely issue as mapping/config vs hardware path.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://localhost:8080"


@dataclass(frozen=True)
class PointResult:
    commanded: float
    measured: float


def _request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url=url, data=data, method=method, headers=headers)
    with urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _set_test_output(base_url: str, value: float, action: str) -> dict:
    return _request_json(
        f"{base_url}/api/output/test",
        method="POST",
        payload={"action": action, "value": float(value)},
    )


def _arm_outputs(base_url: str, armed: bool) -> dict:
    return _request_json(
        f"{base_url}/api/output/arm",
        method="POST",
        payload={"armed": bool(armed)},
    )


def _read_command(base_url: str) -> float:
    snap = _request_json(f"{base_url}/api/snapshot")
    plc = snap.get("plcOutput") or {}
    return float(plc.get("command", 0.0) or 0.0)


def _prompt_float(prompt: str) -> float:
    while True:
        text = input(prompt).strip()
        try:
            return float(text)
        except ValueError:
            print("Enter a numeric value.")


def _classify(results: list[PointResult]) -> str:
    if not results:
        return "No measurements captured."

    ratios = []
    for item in results:
        if abs(item.commanded) <= 1e-9:
            continue
        ratios.append(item.measured / item.commanded)
    if not ratios:
        return "Insufficient non-zero points to classify."

    avg_ratio = sum(ratios) / len(ratios)
    if 0.45 <= avg_ratio <= 0.55:
        return (
            "Likely hardware path issue: commanded output is around half at the terminal. "
            "Check MegaIND board calibration/wiring and verify meter test points."
        )
    if 0.90 <= avg_ratio <= 1.10:
        return (
            "Hardware path looks correct. Likely mapping/config issue in weight->output scaling "
            "(range min/max or profile/linear mode selection)."
        )
    return (
        f"Mixed result (average measured/commanded ratio = {avg_ratio:.3f}). "
        "Check mode, channel, and wiring, then repeat."
    )


def main() -> int:
    base_url = (sys.argv[1].strip() if len(sys.argv) > 1 else DEFAULT_BASE_URL).rstrip("/")
    points = [1.0, 2.0]
    results: list[PointResult] = []

    print("=== Half-Scale PLC Output Diagnostic ===")
    print(f"Base URL: {base_url}")
    print("")
    print("This will ARM outputs and command fixed test values through /api/output/test.")
    print("Use a DMM at MegaIND AO terminals and enter measured values when prompted.")
    print("")

    try:
        arm = _arm_outputs(base_url, True)
        if not arm.get("success", False):
            print(f"Failed to arm outputs: {arm}")
            return 1

        for commanded in points:
            out = _set_test_output(base_url, commanded, "start")
            if not out.get("success", False):
                print(f"Failed to set test output {commanded:.3f}: {out}")
                return 1

            actual_cmd = _read_command(base_url)
            measured = _prompt_float(
                f"Commanded {actual_cmd:.3f}. Enter DMM measured value: "
            )
            results.append(PointResult(commanded=actual_cmd, measured=measured))

        _set_test_output(base_url, 0.0, "stop")

    except (HTTPError, URLError) as e:
        print(f"HTTP communication failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 1

    print("")
    print("Results:")
    for item in results:
        ratio = (item.measured / item.commanded) if abs(item.commanded) > 1e-9 else 0.0
        print(
            f"- Commanded {item.commanded:.3f}, measured {item.measured:.3f}, ratio {ratio:.3f}"
        )
    print("")
    print(_classify(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
