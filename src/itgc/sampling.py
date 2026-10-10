"""Sample-size selection and reproducible random selection for tests of operating effectiveness.

The table mirrors the frequency-based guidance commonly used for ITGC/SOX testing (ranges
widely published in firm methodologies and IIA/ISACA training material; exact numbers vary by
firm). Low end = lower risk / no reliance on other evidence; high end = higher risk or the
control is the sole mitigation. Expected deviations are zero: one exception = control fails.

Event-driven populations (e.g. "every new hire", "every change") are mapped to the frequency
band that has a similar number of occurrences per year.
"""
from __future__ import annotations

import hashlib
import random
from math import comb

FREQUENCY_TABLE: dict[str, tuple[int, int]] = {
    "annual": (1, 1),
    "quarterly": (2, 2),
    "monthly": (2, 5),
    "weekly": (5, 15),
    "daily": (20, 40),
    "multiple_daily": (25, 60),
}


def band_for_population(n: int) -> str:
    """Frequency band equivalent for an event-driven population of n occurrences per year."""
    if n <= 1:
        return "annual"
    if n <= 4:
        return "quarterly"
    if n <= 12:
        return "monthly"
    if n <= 52:
        return "weekly"
    if n <= 365:
        return "daily"
    return "multiple_daily"


def sample_size(population: int, risk: str = "low", frequency: str | None = None) -> int:
    """Number of items to test. Never more than the population (then test 100%)."""
    band = frequency or band_for_population(population)
    low, high = FREQUENCY_TABLE[band]
    n = high if risk.lower() == "high" else low
    return min(n, population)


def seed_for(key: str) -> int:
    """Stable seed derived from a string (e.g. 'FY2026:CM-01') so selections are reproducible."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)


def select(items: list[str], n: int, key: str) -> list[str]:
    """Simple random selection without replacement, reproducible from `key`."""
    ordered = sorted(items)
    if n >= len(ordered):
        return ordered
    return sorted(random.Random(seed_for(key)).sample(ordered, n))


def detection_probability(population: int, exceptions: int, n: int) -> float:
    """P(sample of n contains >= 1 of `exceptions` bad items) - hypergeometric, no replacement."""
    if exceptions <= 0 or n <= 0:
        return 0.0
    if n > population - exceptions:
        return 1.0
    return 1.0 - comb(population - exceptions, n) / comb(population, n)


def min_sample_for_confidence(population: int, exceptions: int, confidence: float) -> int:
    """Smallest n whose detection probability reaches `confidence` (e.g. 0.95)."""
    for n in range(0, population + 1):
        if detection_probability(population, exceptions, n) >= confidence:
            return n
    return population
