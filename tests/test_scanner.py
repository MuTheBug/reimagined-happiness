"""Tests for the symbol scanner analysis functions."""

import math

from grid_trading_bot.scanner import (
    SymbolAnalysis,
    _adx,
    _bollinger_oscillation_score,
    _compute_auto_grid_levels,
    _hurst_exponent,
    _log_returns,
    _mean,
    _range_consistency,
    _score_symbol,
    _simulate_grid_profit,
    _std,
)


class TestMathHelpers:
    def test_mean(self):
        assert _mean([1, 2, 3, 4, 5]) == 3.0

    def test_std(self):
        data = [2, 4, 4, 4, 5, 5, 7, 9]
        assert abs(_std(data) - 2.0) < 0.01

    def test_log_returns(self):
        closes = [100, 110, 105]
        returns = _log_returns(closes)
        assert len(returns) == 2
        assert abs(returns[0] - math.log(1.1)) < 1e-10


class TestHurstExponent:
    def test_random_walk_around_half(self):
        # A simple oscillating series should be mean-reverting (< 0.5)
        closes = []
        price = 100.0
        for i in range(200):
            price = 100 + 5 * math.sin(i * 0.3)
            closes.append(price)
        h = _hurst_exponent(closes)
        assert h < 0.55  # should be mean-reverting or close to 0.5

    def test_trending_series(self):
        # Monotonically increasing = trending
        closes = [100 + i * 0.5 for i in range(200)]
        h = _hurst_exponent(closes)
        assert h > 0.4  # trending or random, definitely not strongly mean-reverting

    def test_mean_reverting_series(self):
        # Strong oscillation
        closes = [100 + 10 * ((-1) ** i) for i in range(200)]
        h = _hurst_exponent(closes)
        assert h < 0.5  # should detect mean-reversion

    def test_short_series_returns_default(self):
        closes = [100, 101, 102]
        h = _hurst_exponent(closes)
        assert h == 0.5


class TestADX:
    def test_ranging_market_vs_trending(self):
        # A ranging market should have lower ADX than a strongly trending one
        n = 100
        # Ranging: oscillating around a center
        r_highs = [101 + 2 * math.sin(i * 0.5) for i in range(n)]
        r_lows = [99 + 2 * math.sin(i * 0.5) for i in range(n)]
        r_closes = [100 + 2 * math.sin(i * 0.5) for i in range(n)]
        adx_ranging = _adx(r_highs, r_lows, r_closes)

        # Trending: steady upward move
        t_highs = [100 + i * 2.0 for i in range(n)]
        t_lows = [99 + i * 2.0 for i in range(n)]
        t_closes = [99.5 + i * 2.0 for i in range(n)]
        adx_trending = _adx(t_highs, t_lows, t_closes)

        assert adx_ranging < adx_trending

    def test_trending_market_higher_adx(self):
        n = 100
        highs = [100 + i * 2.0 for i in range(n)]
        lows = [99 + i * 2.0 for i in range(n)]
        closes = [99.5 + i * 2.0 for i in range(n)]
        adx_val = _adx(highs, lows, closes)
        # Strong trend should give higher ADX
        assert adx_val > 20


class TestBollingerOscillation:
    def test_oscillating_score_nonzero(self):
        closes = [100 + 5 * math.sin(i * 0.5) for i in range(100)]
        score = _bollinger_oscillation_score(closes)
        assert score > 0.0

    def test_flat_line_low_score(self):
        closes = [100.0] * 100
        score = _bollinger_oscillation_score(closes)
        assert score == 0.0


class TestRangeConsistency:
    def test_tight_range(self):
        closes = [100 + 0.1 * i for i in range(50)]
        ratio, low, high = _range_consistency(closes)
        assert ratio > 0.5

    def test_wide_range_lower_consistency(self):
        closes = [100 + 50 * math.sin(i * 0.1) for i in range(100)]
        ratio, low, high = _range_consistency(closes)
        assert 0.0 < ratio <= 1.0


class TestSimulateGridProfit:
    def test_oscillating_gives_profit(self):
        closes = [100 + 5 * math.sin(i * 0.5) for i in range(200)]
        profit = _simulate_grid_profit(closes, 95, 105, 10)
        assert profit > 0.0

    def test_flat_line_no_profit(self):
        closes = [100.0] * 100
        profit = _simulate_grid_profit(closes, 95, 105, 10)
        assert profit == 0.0

    def test_invalid_range_no_profit(self):
        closes = [100.0] * 50
        assert _simulate_grid_profit(closes, 105, 95, 10) == 0.0
        assert _simulate_grid_profit(closes, 100, 100, 10) == 0.0


class TestAutoGridLevels:
    def test_returns_valid_range(self):
        closes = [100 + 3 * math.sin(i * 0.3) for i in range(100)]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        low, high, levels = _compute_auto_grid_levels(closes, highs, lows, 100.0)
        assert low < high
        assert low < 100.0
        assert high > 100.0
        assert 2 <= levels <= 25

    def test_current_price_within_range(self):
        closes = [50.0] * 100
        highs = [51.0] * 100
        lows = [49.0] * 100
        low, high, levels = _compute_auto_grid_levels(closes, highs, lows, 50.0)
        assert low < 50.0
        assert high > 50.0


class TestScoreSymbol:
    def test_ideal_symbol_high_score(self):
        # Low Hurst, low ADX, high oscillation, good backtest
        a = SymbolAnalysis(
            symbol="IDEAL",
            current_price=100,
            hurst_exponent=0.3,
            adx=15.0,
            volatility_pct=2.0,
            bb_oscillation_score=0.5,
            range_consistency=0.85,
            avg_volume_usdt=10_000_000,
            grid_backtest_profit_pct=5.0,
        )
        score = _score_symbol(a)
        assert score > 40  # should be a good score

    def test_trending_symbol_low_score(self):
        # High Hurst, high ADX = trending = bad for grid
        a = SymbolAnalysis(
            symbol="TREND",
            current_price=100,
            hurst_exponent=0.75,
            adx=45.0,
            volatility_pct=8.0,
            bb_oscillation_score=0.1,
            range_consistency=0.3,
            avg_volume_usdt=1_000_000,
            grid_backtest_profit_pct=0.1,
        )
        score = _score_symbol(a)
        assert score < 20  # should be a poor score

    def test_ideal_beats_trending(self):
        ideal = SymbolAnalysis(
            symbol="IDEAL", current_price=100, hurst_exponent=0.3,
            adx=15.0, volatility_pct=2.0, bb_oscillation_score=0.5,
            range_consistency=0.85, avg_volume_usdt=10_000_000,
            grid_backtest_profit_pct=5.0,
        )
        trend = SymbolAnalysis(
            symbol="TREND", current_price=100, hurst_exponent=0.75,
            adx=45.0, volatility_pct=8.0, bb_oscillation_score=0.1,
            range_consistency=0.3, avg_volume_usdt=1_000_000,
            grid_backtest_profit_pct=0.1,
        )
        assert _score_symbol(ideal) > _score_symbol(trend)
