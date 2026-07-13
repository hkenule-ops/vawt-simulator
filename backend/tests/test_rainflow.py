"""
Rainflow counting tests, validated against hand-traced worked examples using
the ASTM E1049 3-point stack algorithm -- not against a black-box reference
implementation, but derived independently by tracing the algorithm step by
step (documented in the module's development notes), the same standard
applied to every solver in this platform: don't trust an algorithm just
because it runs, check it against an answer you can verify by hand.
"""
import pytest
from app.fatigue.rainflow import count_cycles


def test_nested_cycle_extracts_inner_and_outer_ranges():
    """
    [0,10,4,6,0]: a small 4->6 bump nested inside a big 0->10->0 swing.
    Hand-traced result: one cycle of range=2 (the nested bump) and one
    cycle of range=10 (the outer swing), both mean=5.
    """
    cycles = count_cycles([0, 10, 4, 6, 0])
    ranges = sorted(c.range_ for c in cycles)
    assert ranges == [2, 10]
    assert all(c.count == 1.0 for c in cycles)
    assert all(c.mean == pytest.approx(5.0) for c in cycles)


def test_clean_double_triangle_wave_gives_two_equal_full_cycles():
    """[0,5,0,5,0]: two clean, non-nested triangle cycles, no residual."""
    cycles = count_cycles([0, 5, 0, 5, 0])
    assert len(cycles) == 2
    for c in cycles:
        assert c.range_ == pytest.approx(5.0)
        assert c.mean == pytest.approx(2.5)
        assert c.count == 1.0


def test_flat_signal_gives_no_cycles():
    cycles = count_cycles([3, 3, 3, 3, 3])
    assert len(cycles) == 0


def test_monotonic_signal_gives_no_full_cycles():
    """A purely increasing signal has no closed hysteresis loops -- at most a residual half-cycle."""
    cycles = count_cycles([0, 1, 2, 3, 4, 5])
    assert all(c.count == 0.5 for c in cycles)


def test_single_point_gives_no_cycles():
    assert count_cycles([5.0]) == []


def test_empty_series_gives_no_cycles():
    assert count_cycles([]) == []


def test_larger_ranges_have_larger_damage_potential_ordering():
    """A bigger swing should never produce a smaller extracted range than a swing nested inside it."""
    cycles = count_cycles([0, 20, 8, 12, 0])  # small bump (8->12, range 4) inside big swing (0->20->0, range 20)
    ranges = sorted(c.range_ for c in cycles)
    assert ranges[0] < ranges[-1]
    assert ranges == [4, 20]
