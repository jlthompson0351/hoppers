from __future__ import annotations

import re
import statistics as st
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class Row:
    t_s: int
    wt_lbs: float
    raw_lbs: float
    raw_mv: float
    stable: bool
    reason: str


def _pct(xs_sorted: list[float], p: float) -> float:
    if not xs_sorted:
        raise ValueError("empty")
    if p <= 0:
        return xs_sorted[0]
    if p >= 1:
        return xs_sorted[-1]
    k = int(round((len(xs_sorted) - 1) * p))
    return xs_sorted[max(0, min(len(xs_sorted) - 1, k))]


def _summarize(name: str, xs: Iterable[float]) -> None:
    xs2 = sorted(float(x) for x in xs)
    if not xs2:
        print(f"{name}: NONE")
        return
    print(
        f"{name}: n={len(xs2)} "
        f"min={xs2[0]:.1f} "
        f"p50={_pct(xs2, 0.50):.1f} "
        f"p75={_pct(xs2, 0.75):.1f} "
        f"p90={_pct(xs2, 0.90):.1f} "
        f"max={xs2[-1]:.1f} "
        f"mean={st.fmean(xs2):.1f}"
    )


def parse_rows(path: Path) -> list[Row]:
    rx = re.compile(
        r"^(?P<hh>\d\d):(?P<mm>\d\d):(?P<ss>\d\d)\s+"
        r"wt=\s*(?P<wt>[-\d.]+)\s+"
        r"raw=\s*(?P<raw>[-\d.]+)\s+"
        r"mv=(?P<mv>[-\d.]+)\s+"
        r"stable=(?P<stable>True|False)\s+"
        r"reason=(?P<reason>[^ ]+)"
    )
    out: list[Row] = []
    for line in path.read_text(errors="ignore").splitlines():
        m = rx.search(line)
        if not m:
            continue
        hh = int(m["hh"])
        mm = int(m["mm"])
        ss = int(m["ss"])
        out.append(
            Row(
                t_s=hh * 3600 + mm * 60 + ss,
                wt_lbs=float(m["wt"]),
                raw_lbs=float(m["raw"]),
                raw_mv=float(m["mv"]),
                stable=(m["stable"] == "True"),
                reason=m["reason"],
            )
        )
    return out


def is_plausible(r: Row) -> bool:
    # Filter out obvious glitches (bad ADC packets, service restarts, etc.)
    if not (5.5 <= r.raw_mv <= 10.0):
        return False
    if not (-50.0 <= r.raw_lbs <= 400.0):
        return False
    if not (-50.0 <= r.wt_lbs <= 400.0):
        return False
    return True


def detect_dumps(rows: list[Row], *, drop_thr_lb: float, full_min_lb: float) -> list[int]:
    """Return indices in `rows` that look like dump starts."""
    idx: list[int] = []
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        if (cur.t_s - prev.t_s) != 1:
            continue
        if prev.raw_lbs < full_min_lb:
            continue
        if (prev.raw_lbs - cur.raw_lbs) >= drop_thr_lb:
            idx.append(i)

    # Coalesce events within a short window to avoid double-counting.
    out: list[int] = []
    last_t = -10_000
    for i in idx:
        if (rows[i].t_s - last_t) <= 8:
            continue
        out.append(i)
        last_t = rows[i].t_s
    return out


def _first_time_after(
    rows: list[Row], start_idx: int, *, predicate, max_lookahead_s: int
) -> Optional[int]:
    t0 = rows[start_idx].t_s
    for j in range(start_idx, len(rows)):
        if (rows[j].t_s - t0) > max_lookahead_s:
            return None
        if predicate(rows[j]):
            return j
    return None


import sys

def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = Path(r"C:\Users\jthompson\Desktop\Scales\docs\archive\shift_log_20260218_1310.txt")
    
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    rows = parse_rows(path)
    print("parsed_rows=", len(rows))
    if not rows:
        return 0

    rows_f = [r for r in rows if is_plausible(r)]
    print("filtered_rows=", len(rows_f))

    stables = [r.stable for r in rows_f]
    print("stable_pct=", round(100.0 * sum(stables) / max(1, len(stables)), 1))

    dumps = detect_dumps(rows_f, drop_thr_lb=25.0, full_min_lb=20.0)
    print("dump_candidates=", len(dumps))
    for n, i in enumerate(dumps[:8], start=1):
        prev = rows_f[i - 1]
        cur = rows_f[i]
        print(
            f"dump#{n} t={cur.t_s} raw_drop={prev.raw_lbs-cur.raw_lbs:.1f} "
            f"({prev.raw_lbs:.1f}->{cur.raw_lbs:.1f}) stable_before={prev.stable} stable_after={cur.stable}"
        )

    # Compute settle times relative to a chosen empty threshold.
    empty_thr = 5.0  # 2% of 250 lb capacity
    fill_resume_thr = empty_thr + max(1.0, empty_thr * 0.5)

    t_to_stable: list[float] = []
    t_to_empty_stable: list[float] = []
    t_to_fill_resume: list[float] = []
    min_abs_stable_after_dump: list[float] = []

    for i in dumps:
        t0 = rows_f[i].t_s

        # Best-effort "how empty did we actually get" metric (stable samples only).
        best = None
        for r in rows_f[i : min(len(rows_f), i + 120)]:
            if not r.stable:
                continue
            v = abs(float(r.raw_lbs))
            if best is None or v < best:
                best = v
        if best is not None:
            min_abs_stable_after_dump.append(best)

        j_stable = _first_time_after(
            rows_f,
            i,
            predicate=lambda r: bool(r.stable),
            max_lookahead_s=120,
        )
        j_empty_stable = _first_time_after(
            rows_f,
            i,
            predicate=lambda r: bool(r.stable) and abs(r.raw_lbs) <= empty_thr,
            max_lookahead_s=120,
        )
        if j_stable is not None:
            t_to_stable.append(rows_f[j_stable].t_s - t0)
        if j_empty_stable is not None:
            t_to_empty_stable.append(rows_f[j_empty_stable].t_s - t0)

            j_fill = _first_time_after(
                rows_f,
                j_empty_stable,
                predicate=lambda r: float(r.raw_lbs) > fill_resume_thr,
                max_lookahead_s=240,
            )
            if j_fill is not None:
                t_to_fill_resume.append(rows_f[j_fill].t_s - t0)

    _summarize("time_to_stable_s", t_to_stable)
    _summarize(f"time_to_empty_stable_s (<= {empty_thr:.1f} lb)", t_to_empty_stable)
    _summarize("time_to_fill_resume_s", t_to_fill_resume)
    _summarize("min_abs_stable_raw_lb_after_dump", min_abs_stable_after_dump)

    # Success rate table for practical tuning.
    if dumps:
        print("success_rates (stable + abs(raw)<=thr within window):")
        for thr in (5.0, 7.5, 10.0):
            for win in (10, 15, 30, 45):
                ok_ct = 0
                for i in dumps:
                    t0 = rows_f[i].t_s
                    found = False
                    for r in rows_f[i:]:
                        if (r.t_s - t0) > win:
                            break
                        if r.stable and abs(r.raw_lbs) <= thr:
                            found = True
                            break
                    if found:
                        ok_ct += 1
                pct = 100.0 * ok_ct / max(1, len(dumps))
                print(f"  thr={thr:4.1f} win={win:2d}s  ok={ok_ct:2d}/{len(dumps):2d}  ({pct:5.1f}%)")

    # Empty noise estimate (stable + low weight), used to sanity-check empty threshold.
    empty_samples = [abs(r.raw_lbs) for r in rows_f if r.stable and abs(r.raw_lbs) <= 10.0]
    empty_samples_sorted = sorted(empty_samples)
    if empty_samples_sorted:
        p99 = _pct(empty_samples_sorted, 0.99)
        p999 = _pct(empty_samples_sorted, 0.999)
        print(f"empty_abs_raw_lb p99={p99:.2f} p99.9={p999:.2f} (from stable samples <=10 lb)")

    # Recommendation heuristics:
    # - min_delay: protect against early 'stable' on bounce; use p75(time_to_stable) rounded up.
    # - window: allow enough time to reach empty+stable in most cases but stop before typical fill resumes.
    rec_min_delay = None
    if t_to_stable:
        t_sorted = sorted(t_to_stable)
        rec_min_delay = max(1.0, min(12.0, float(_pct(t_sorted, 0.75) + 1.0)))
    if rec_min_delay is not None:
        print(f"RECOMMEND post_dump_min_delay_s ~= {rec_min_delay:.1f}")

    rec_window = None
    if t_to_empty_stable:
        te_sorted = sorted(t_to_empty_stable)
        rec_window = max(8.0, min(30.0, float(_pct(te_sorted, 0.90) + 5.0)))
    if rec_window is not None:
        print(f"RECOMMEND post_dump_window_s ~= {rec_window:.1f}")

    # Empty threshold is a tradeoff:
    # - Too low => post-dump re-zero never runs when drift is already several pounds.
    # - Too high => risk of burying small residual material.
    # Use capacity defaults, but show a data-driven suggestion from this log.
    rec_empty = 5.0
    if min_abs_stable_after_dump:
        mins_sorted = sorted(min_abs_stable_after_dump)
        rec_empty = max(5.0, min(20.0, float(_pct(mins_sorted, 0.90) + 1.0)))
    print(f"RECOMMEND post_dump_empty_threshold_lb ~= {rec_empty:.1f} (capacity default 5.0)")

    # Max correction: allow post-dump capture to fix drift up to a bounded amount.
    # Start with 4% of 250 lb capacity (10 lb) unless drift routinely exceeds it.
    rec_max_corr = 10.0
    if rec_empty > 5.0:
        rec_max_corr = max(10.0, min(25.0, float(rec_empty * 2.0)))
    print(f"RECOMMEND post_dump_max_correction_lb ~= {rec_max_corr:.1f} (capacity default 10.0)")
    print("RECOMMEND AZT range_lb=0.05 rate_lbs=0.05 deadband_lb=0.02 hold_s=1.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

