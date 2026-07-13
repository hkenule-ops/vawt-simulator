"""
Rainflow cycle counting (ASTM E1049-85 "3-point" stack-based method).

Takes a stress (or load) time history, extracts the sequence of turning
points (peaks and valleys), and decomposes it into closed hysteresis cycles
plus a residual (unclosed) sequence -- the standard technique for reducing a
variable-amplitude load history into discrete range/mean cycle counts that
Miner's rule can use.

Algorithm: maintain a stack of turning points. For the three most recently
pushed points A, B, C (oldest to newest), compare the two most recent
ranges: Y = |B-A|, X = |C-B|. If X >= Y, the smaller/older excursion (A->B)
is a closed cycle -- record it (range Y, mean (A+B)/2), remove A and B from
the stack, and re-check the new top of the stack (a removal can expose
another closable cycle). If X < Y, push the next point and repeat. Whatever
remains on the stack at the end is the "residual" -- an unclosed sequence,
each range counted as a half-cycle for Miner's rule purposes (standard
practice, e.g. per ASTM E1049).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RainflowCycle:
    range_: float
    mean: float
    count: float  # 1.0 for a full cycle, 0.5 for a residual half-cycle


def _turning_points(series: list[float]) -> list[float]:
    """Reduce a time history to just its local peaks and valleys (removes flat/monotonic runs)."""
    if len(series) < 3:
        return list(series)
    points = [series[0]]
    for i in range(1, len(series) - 1):
        prev, cur, nxt = series[i - 1], series[i], series[i + 1]
        if (cur - prev) * (nxt - cur) < 0:  # direction reversal
            points.append(cur)
        elif (cur - prev) * (nxt - cur) == 0 and cur != prev:
            # plateau handling: keep the point if it's a genuine reversal boundary
            continue
    points.append(series[-1])
    return points


def count_cycles(series: list[float]) -> list[RainflowCycle]:
    points = _turning_points(series)
    stack: list[float] = []
    cycles: list[RainflowCycle] = []

    for point in points:
        stack.append(point)
        while len(stack) >= 3:
            A, B, C = stack[-3], stack[-2], stack[-1]
            Y = abs(B - A)
            X = abs(C - B)
            if X >= Y:
                cycles.append(RainflowCycle(range_=Y, mean=(A + B) / 2, count=1.0))
                del stack[-3:-1]  # remove A and B, keep C on top
            else:
                break

    # Residual: whatever's left on the stack forms unclosed half-cycles.
    for i in range(len(stack) - 1):
        A, B = stack[i], stack[i + 1]
        if A != B:
            cycles.append(RainflowCycle(range_=abs(B - A), mean=(A + B) / 2, count=0.5))

    return cycles
