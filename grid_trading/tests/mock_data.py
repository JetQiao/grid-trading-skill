"""Synthetic price series for backtesting and unit tests."""

from __future__ import annotations

import math


def sine_wave(
    base_price: float = 50000.0,
    amplitude: float = 5000.0,
    periods: int = 5,
    points: int = 500,
    start_ts: float = 0.0,
    interval: float = 60.0,
) -> list[tuple[float, float]]:
    """Oscillating market — ideal for grid strategies.

    Args:
        base_price: Mid-point price.
        amplitude: Peak deviation from base_price.
        periods: Number of full sine cycles.
        points: Total data points.
        start_ts: Starting UNIX timestamp.
        interval: Seconds between ticks.

    Returns:
        List of (timestamp, price) tuples.
    """
    result: list[tuple[float, float]] = []
    for i in range(points):
        ts = start_ts + i * interval
        price = base_price + amplitude * math.sin(2 * math.pi * periods * i / points)
        result.append((ts, round(price, 2)))
    return result


def trending_down(
    start_price: float = 55000.0,
    end_price: float = 38000.0,
    noise: float = 300.0,
    points: int = 500,
    start_ts: float = 0.0,
    interval: float = 60.0,
) -> list[tuple[float, float]]:
    """Persistent downtrend — worst case for grid strategies.

    Args:
        start_price: Opening price.
        end_price: Final price (lower than start).
        noise: Random-looking zigzag amplitude (deterministic via sine).
        points: Total data points.
        start_ts: Starting UNIX timestamp.
        interval: Seconds between ticks.

    Returns:
        List of (timestamp, price) tuples.
    """
    result: list[tuple[float, float]] = []
    for i in range(points):
        ts = start_ts + i * interval
        linear = start_price + (end_price - start_price) * i / (points - 1)
        zigzag = noise * math.sin(2 * math.pi * 20 * i / points)
        price = max(1.0, linear + zigzag)
        result.append((ts, round(price, 2)))
    return result


def volatile_spike(
    base_price: float = 50000.0,
    drop_to: float = 40000.0,
    recover_to: float = 52000.0,
    points: int = 500,
    start_ts: float = 0.0,
    interval: float = 60.0,
) -> list[tuple[float, float]]:
    """Sharp drop followed by a recovery — tests stop-loss & rebound behavior.

    Args:
        base_price: Initial price.
        drop_to: Trough price at the midpoint.
        recover_to: Final recovery price.
        points: Total data points.
        start_ts: Starting UNIX timestamp.
        interval: Seconds between ticks.

    Returns:
        List of (timestamp, price) tuples.
    """
    result: list[tuple[float, float]] = []
    half = points // 2
    for i in range(points):
        ts = start_ts + i * interval
        if i < half:
            # Drop phase
            t = i / half
            price = base_price + (drop_to - base_price) * t
        else:
            # Recovery phase
            t = (i - half) / (points - half)
            price = drop_to + (recover_to - drop_to) * t
        result.append((ts, round(price, 2)))
    return result


if __name__ == "__main__":
    for name, series in [
        ("sine_wave", sine_wave()),
        ("trending_down", trending_down()),
        ("volatile_spike", volatile_spike()),
    ]:
        prices = [p for _, p in series]
        print(f"{name}: {len(series)} pts | min={min(prices):.2f} max={max(prices):.2f}")
