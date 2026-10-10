import pytest

from itgc.sampling import band_for_population, detection_probability, min_sample_for_confidence, sample_size, select


@pytest.mark.parametrize("n,band", [(1, "annual"), (4, "quarterly"), (12, "monthly"), (32, "weekly"),
                                    (365, "daily"), (2000, "multiple_daily")])
def test_bands(n, band):
    assert band_for_population(n) == band


def test_sample_sizes():
    assert sample_size(32, "high") == 15
    assert sample_size(32, "low") == 5
    assert sample_size(4, "high", frequency="quarterly") == 2
    assert sample_size(3, "high") == 2          # quarterly band, never more than population
    assert sample_size(1) == 1


def test_selection_is_reproducible_and_without_replacement():
    items = [f"item{i}" for i in range(40)]
    a = select(items, 10, "FY2026:X")
    assert a == select(list(reversed(items)), 10, "FY2026:X")   # order-independent
    assert len(set(a)) == 10
    assert a != select(items, 10, "FY2026:Y")
    assert select(items[:3], 10, "k") == sorted(items[:3])


def test_detection_probability_hypergeometric():
    # 4 bad changes among 32, sample 15: 1 - C(28,15)/C(32,15)
    assert detection_probability(32, 4, 15) == pytest.approx(0.9338, abs=1e-4)
    assert detection_probability(365, 2, 20) == pytest.approx(0.1071, abs=1e-3)
    assert detection_probability(10, 0, 5) == 0.0
    assert detection_probability(10, 3, 8) == 1.0
    assert min_sample_for_confidence(365, 2, 0.95) > 200
