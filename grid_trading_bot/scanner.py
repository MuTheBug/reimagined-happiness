"""Symbol scanner — analyzes all USDT pairs to find the best grid trading candidate.

Scoring methodology for maximum grid profitability:
1. Hurst exponent (< 0.5 = mean-reverting = ideal for grid)
2. ADX (< 25 = ranging market, not trending)
3. Volatility (high intra-range volatility = more grid fills = more profit)
4. Bollinger Band squeeze ratio (price oscillates within bands)
5. Range consistency (price stays within a predictable channel)
6. Volume (sufficient liquidity for fills)
7. Grid profit simulation (backtested profit from recent candles)
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

from binance.client import Client

logger = logging.getLogger(__name__)

# Analysis windows
KLINE_INTERVAL = Client.KLINE_INTERVAL_1HOUR
KLINE_LIMIT = 168  # 7 days of hourly candles
MIN_24H_VOLUME_USDT = 5_000_000  # filter illiquid pairs
TOP_SYMBOLS_TO_ANALYZE = 80  # scan the top N by volume


@dataclass
class SymbolAnalysis:
    """Full analysis result for a single symbol."""

    symbol: str
    current_price: float
    # Raw indicators
    hurst_exponent: float  # < 0.5 = mean-reverting
    adx: float  # < 25 = ranging
    volatility_pct: float  # std of returns as pct
    bb_oscillation_score: float  # how much price bounces within BBands
    range_consistency: float  # pct of candles within auto-detected range
    avg_volume_usdt: float  # average hourly volume in USDT
    grid_backtest_profit_pct: float  # simulated grid profit over the window
    # Computed
    overall_score: float = 0.0
    # Auto-computed grid levels
    recommended_lower: float = 0.0
    recommended_upper: float = 0.0
    recommended_levels: int = 10
    predicted_daily_profit_pct: float = 0.0


def _get_top_usdt_symbols(client: Client) -> list[dict]:
    """Get USDT trading pairs sorted by 24h quote volume descending."""
    tickers = client.get_ticker()
    usdt_tickers = [
        t for t in tickers
        if t["symbol"].endswith("USDT")
        and not t["symbol"].endswith("DOWNUSDT")
        and not t["symbol"].endswith("UPUSDT")
        and not t["symbol"].startswith("TUSD")
        and not t["symbol"].startswith("BUSD")
        and not t["symbol"].startswith("USDC")
        and float(t["quoteVolume"]) >= MIN_24H_VOLUME_USDT
    ]
    usdt_tickers.sort(key=lambda t: float(t["quoteVolume"]), reverse=True)
    return usdt_tickers[:TOP_SYMBOLS_TO_ANALYZE]


def _fetch_klines(client: Client, symbol: str) -> list[list]:
    """Fetch hourly klines for analysis."""
    return client.get_klines(
        symbol=symbol, interval=KLINE_INTERVAL, limit=KLINE_LIMIT
    )


def _extract_closes(klines: list[list]) -> list[float]:
    return [float(k[4]) for k in klines]


def _extract_highs(klines: list[list]) -> list[float]:
    return [float(k[2]) for k in klines]


def _extract_lows(klines: list[list]) -> list[float]:
    return [float(k[3]) for k in klines]


def _extract_volumes_usdt(klines: list[list]) -> list[float]:
    return [float(k[7]) for k in klines]  # quote asset volume


# ---------------------------------------------------------------------------
# Technical indicators (pure Python, no numpy dependency)
# ---------------------------------------------------------------------------

def _mean(data: list[float]) -> float:
    return sum(data) / len(data)


def _std(data: list[float]) -> float:
    m = _mean(data)
    return math.sqrt(sum((x - m) ** 2 for x in data) / len(data))


def _log_returns(closes: list[float]) -> list[float]:
    return [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]


def _hurst_exponent(closes: list[float]) -> float:
    """Estimate the Hurst exponent using the rescaled range (R/S) method.

    H < 0.5 → mean-reverting (IDEAL for grid trading)
    H = 0.5 → random walk
    H > 0.5 → trending (bad for grid)
    """
    returns = _log_returns(closes)
    n = len(returns)
    if n < 20:
        return 0.5

    # Use multiple sub-series lengths
    min_chunk = 8
    sizes = []
    rs_values = []

    chunk_size = min_chunk
    while chunk_size <= n // 2:
        num_chunks = n // chunk_size
        rs_list = []
        for i in range(num_chunks):
            chunk = returns[i * chunk_size:(i + 1) * chunk_size]
            m = _mean(chunk)
            deviations = [sum(chunk[:j + 1]) - (j + 1) * m for j in range(len(chunk))]
            r = max(deviations) - min(deviations)
            s = _std(chunk) if _std(chunk) > 0 else 1e-10
            rs_list.append(r / s)
        sizes.append(chunk_size)
        rs_values.append(_mean(rs_list))
        chunk_size *= 2

    if len(sizes) < 2:
        return 0.5

    # Linear regression of log(R/S) vs log(n)
    log_sizes = [math.log(s) for s in sizes]
    log_rs = [math.log(max(r, 1e-10)) for r in rs_values]
    n_pts = len(log_sizes)
    mean_x = _mean(log_sizes)
    mean_y = _mean(log_rs)
    num = sum((log_sizes[i] - mean_x) * (log_rs[i] - mean_y) for i in range(n_pts))
    den = sum((log_sizes[i] - mean_x) ** 2 for i in range(n_pts))
    if den == 0:
        return 0.5
    return max(0.0, min(1.0, num / den))


def _adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    """Average Directional Index — measures trend strength.

    ADX < 20: weak trend (ranging) — GOOD for grid
    ADX 20-25: possible trend emerging
    ADX > 25: strong trend — BAD for grid
    """
    n = len(closes)
    if n < period + 1:
        return 50.0

    plus_dm = []
    minus_dm = []
    tr_list = []

    for i in range(1, n):
        high_diff = highs[i] - highs[i - 1]
        low_diff = lows[i - 1] - lows[i]

        pdm = high_diff if high_diff > low_diff and high_diff > 0 else 0.0
        mdm = low_diff if low_diff > high_diff and low_diff > 0 else 0.0
        plus_dm.append(pdm)
        minus_dm.append(mdm)

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    # Smoothed averages (Wilder's smoothing)
    def wilder_smooth(data: list[float], p: int) -> list[float]:
        smoothed = [sum(data[:p])]
        for i in range(p, len(data)):
            smoothed.append(smoothed[-1] - smoothed[-1] / p + data[i])
        return smoothed

    atr = wilder_smooth(tr_list, period)
    smooth_pdm = wilder_smooth(plus_dm, period)
    smooth_mdm = wilder_smooth(minus_dm, period)

    length = min(len(atr), len(smooth_pdm), len(smooth_mdm))
    dx_values = []
    for i in range(length):
        if atr[i] == 0:
            continue
        pdi = 100 * smooth_pdm[i] / atr[i]
        mdi = 100 * smooth_mdm[i] / atr[i]
        denom = pdi + mdi
        if denom == 0:
            continue
        dx_values.append(100 * abs(pdi - mdi) / denom)

    if not dx_values:
        return 50.0

    # ADX is the smoothed average of DX
    adx_smooth = wilder_smooth(dx_values, period)
    return adx_smooth[-1] if adx_smooth else 50.0


def _bollinger_oscillation_score(closes: list[float], period: int = 20, num_std: float = 2.0) -> float:
    """Measure how much price oscillates between Bollinger Bands.

    Higher score = price bounces between bands more = better for grid.
    We count direction reversals relative to the moving average.
    """
    n = len(closes)
    if n < period:
        return 0.0

    reversals = 0
    prev_side = 0  # -1 = below MA, +1 = above MA

    for i in range(period, n):
        window = closes[i - period:i]
        ma = _mean(window)
        current = closes[i]
        side = 1 if current > ma else -1
        if prev_side != 0 and side != prev_side:
            reversals += 1
        prev_side = side

    max_possible = n - period
    return reversals / max_possible if max_possible > 0 else 0.0


def _range_consistency(closes: list[float], pct_band: float = 0.02) -> tuple[float, float, float]:
    """Detect the tightest price range that contains the most candles.

    Returns (consistency_ratio, range_low, range_high).
    consistency_ratio is the fraction of closes within the detected range.
    """
    sorted_closes = sorted(closes)
    n = len(sorted_closes)
    best_count = 0
    best_low = sorted_closes[0]
    best_high = sorted_closes[-1]

    # Sliding window on sorted prices — find densest band
    for i in range(n):
        low = sorted_closes[i]
        high = low * (1 + pct_band * 10)  # 20% band
        # Count how many prices fall within [low, high]
        count = 0
        for j in range(i, n):
            if sorted_closes[j] <= high:
                count += 1
            else:
                break
        if count > best_count:
            best_count = count
            best_low = low
            best_high = high

    return best_count / n, best_low, best_high


def _simulate_grid_profit(
    closes: list[float], lower: float, upper: float, num_levels: int = 10
) -> float:
    """Backtest a grid strategy on historical closes and return profit as pct of investment.

    Walk through price history and count how many grid levels get crossed
    (each crossing = one buy+sell cycle completed = grid spacing profit).
    """
    if upper <= lower or num_levels < 2:
        return 0.0

    step = (upper - lower) / (num_levels - 1)
    grid_prices = [lower + i * step for i in range(num_levels)]

    total_profit = 0.0
    per_level_invest = 1.0 / num_levels  # normalized

    # Track which level the price was last at
    def price_to_level(p: float) -> int:
        if p <= lower:
            return 0
        if p >= upper:
            return num_levels - 1
        return int((p - lower) / step)

    prev_level = price_to_level(closes[0])

    for close in closes[1:]:
        if close < lower or close > upper:
            continue
        curr_level = price_to_level(close)
        levels_crossed = abs(curr_level - prev_level)
        if levels_crossed > 0:
            # Each level crossed earns approximately (step / price) of per-level investment
            profit_per_cross = (step / close) * per_level_invest
            total_profit += profit_per_cross * levels_crossed
        prev_level = curr_level

    return total_profit * 100  # as percentage


def _compute_auto_grid_levels(
    closes: list[float], highs: list[float], lows: list[float], current_price: float
) -> tuple[float, float, int]:
    """Auto-compute optimal grid boundaries and level count.

    Uses recent support/resistance from price action to set tight,
    profitable grid bounds.
    """
    # Use the interquartile range of recent highs/lows for robust bounds
    sorted_lows = sorted(lows)
    sorted_highs = sorted(highs)
    n = len(sorted_lows)

    q1_idx = n // 4
    q3_idx = 3 * n // 4

    range_low = sorted_lows[q1_idx]   # Q1 of lows = strong support
    range_high = sorted_highs[q3_idx]  # Q3 of highs = strong resistance

    # Ensure current price is within range
    if current_price < range_low:
        range_low = current_price * 0.99
    if current_price > range_high:
        range_high = current_price * 1.01

    # Add small buffer (0.5%)
    range_low *= 0.995
    range_high *= 1.005

    # Optimal grid levels: more levels for wider ranges, fewer for tight ones
    range_pct = (range_high - range_low) / current_price
    if range_pct < 0.03:
        levels = 8
    elif range_pct < 0.06:
        levels = 12
    elif range_pct < 0.10:
        levels = 15
    else:
        levels = 20

    return range_low, range_high, levels


def _score_symbol(analysis: SymbolAnalysis) -> float:
    """Compute an overall profitability score (0-100).

    Weights are tuned to maximize grid trading profitability:
    - Mean-reversion (Hurst < 0.5) is the strongest signal
    - Low ADX confirms ranging behavior
    - High oscillation means more grid fills
    - Grid backtest profit is the empirical confirmation
    """
    # Hurst score: 0.0 → 100, 0.5 → 0, 1.0 → -100 (clamped to 0)
    hurst_score = max(0, (0.5 - analysis.hurst_exponent) * 200)

    # ADX score: 0 → 100, 25 → 0, 50+ → 0
    adx_score = max(0, (25 - analysis.adx) * 4)

    # Oscillation score: 0-1 mapped to 0-100
    osc_score = analysis.bb_oscillation_score * 100

    # Range consistency: higher is better
    range_score = analysis.range_consistency * 100

    # Volatility: moderate is best (too low = no profit, too high = breaks range)
    # Sweet spot around 1-4%
    if analysis.volatility_pct < 0.3:
        vol_score = analysis.volatility_pct / 0.3 * 30
    elif analysis.volatility_pct <= 4.0:
        vol_score = 30 + (analysis.volatility_pct - 0.3) / 3.7 * 70
    else:
        vol_score = max(0, 100 - (analysis.volatility_pct - 4.0) * 15)

    # Backtest profit: direct empirical measure, heavily weighted
    bt_score = min(100, analysis.grid_backtest_profit_pct * 10)

    # Volume bonus: prefer liquid markets (logarithmic scale)
    vol_usd = analysis.avg_volume_usdt
    volume_bonus = min(10, math.log10(max(vol_usd, 1)) - 5) if vol_usd > 100000 else 0

    score = (
        hurst_score * 0.25      # mean-reversion is king
        + adx_score * 0.20      # ranging confirmation
        + osc_score * 0.15      # oscillation frequency
        + bt_score * 0.25       # empirical profit
        + range_score * 0.05    # range stability
        + vol_score * 0.05      # volatility sweet spot
        + volume_bonus * 0.05   # liquidity bonus
    )

    return round(score, 2)


def scan_symbols(
    api_key: str, api_secret: str, testnet: bool = False, top_n: int = 10
) -> list[SymbolAnalysis]:
    """Scan Binance USDT pairs and return top N ranked by grid profitability.

    This is the main entry point for the scanner.
    """
    client = Client(api_key, api_secret, testnet=testnet)

    print("\n" + "=" * 70)
    print("  BINANCE GRID TRADING BOT — SYMBOL SCANNER")
    print("  Analyzing symbols for maximum grid profitability...")
    print("=" * 70)

    # Step 1: Get candidate symbols
    print("\n[1/3] Fetching top USDT pairs by volume...")
    tickers = _get_top_usdt_symbols(client)
    print(f"  Found {len(tickers)} liquid USDT pairs (>{MIN_24H_VOLUME_USDT/1e6:.0f}M daily volume)")

    # Step 2: Analyze each symbol
    print(f"\n[2/3] Analyzing {len(tickers)} symbols (Hurst, ADX, volatility, backtest)...")
    analyses: list[SymbolAnalysis] = []

    for i, ticker in enumerate(tickers):
        symbol = ticker["symbol"]
        current_price = float(ticker["lastPrice"])
        progress = f"  [{i + 1}/{len(tickers)}]"

        try:
            klines = _fetch_klines(client, symbol)
            if len(klines) < 50:
                print(f"{progress} {symbol}: skipped (insufficient data)")
                continue

            closes = _extract_closes(klines)
            highs = _extract_highs(klines)
            lows = _extract_lows(klines)
            volumes = _extract_volumes_usdt(klines)

            returns = _log_returns(closes)
            hurst = _hurst_exponent(closes)
            adx_val = _adx(highs, lows, closes)
            volatility = _std(returns) * 100
            osc = _bollinger_oscillation_score(closes)
            consistency, _, _ = _range_consistency(closes)
            avg_vol = _mean(volumes)

            auto_lower, auto_upper, auto_levels = _compute_auto_grid_levels(
                closes, highs, lows, current_price
            )
            bt_profit = _simulate_grid_profit(closes, auto_lower, auto_upper, auto_levels)

            # Daily profit estimate: backtest covers KLINE_LIMIT hours
            hours_in_window = len(closes)
            daily_profit = (bt_profit / hours_in_window) * 24 if hours_in_window > 0 else 0.0

            analysis = SymbolAnalysis(
                symbol=symbol,
                current_price=current_price,
                hurst_exponent=round(hurst, 4),
                adx=round(adx_val, 2),
                volatility_pct=round(volatility, 4),
                bb_oscillation_score=round(osc, 4),
                range_consistency=round(consistency, 4),
                avg_volume_usdt=round(avg_vol, 2),
                grid_backtest_profit_pct=round(bt_profit, 4),
                recommended_lower=round(auto_lower, 8),
                recommended_upper=round(auto_upper, 8),
                recommended_levels=auto_levels,
                predicted_daily_profit_pct=round(daily_profit, 4),
            )
            analysis.overall_score = _score_symbol(analysis)
            analyses.append(analysis)

            indicator = "***" if analysis.overall_score >= 50 else "  "
            print(
                f"{progress} {symbol:<12} Hurst={hurst:.3f}  ADX={adx_val:5.1f}  "
                f"Vol={volatility:5.2f}%  BT={bt_profit:6.2f}%  Score={analysis.overall_score:5.1f} {indicator}"
            )

            # Rate limit safety
            if (i + 1) % 10 == 0:
                time.sleep(0.5)

        except Exception as exc:
            print(f"{progress} {symbol}: error — {exc}")
            continue

    # Step 3: Rank
    analyses.sort(key=lambda a: a.overall_score, reverse=True)
    return analyses[:top_n]


def print_scanner_results(analyses: list[SymbolAnalysis]) -> None:
    """Print a detailed formatted report of scanner results."""
    if not analyses:
        print("\nNo symbols analyzed successfully.")
        return

    best = analyses[0]

    print("\n" + "=" * 70)
    print("  SCANNER RESULTS — TOP SYMBOLS FOR GRID TRADING")
    print("=" * 70)

    print(f"\n{'Rank':<5} {'Symbol':<12} {'Score':>6} {'Hurst':>6} {'ADX':>6} "
          f"{'Vol%':>6} {'Osc':>5} {'BT Profit%':>10} {'Daily%':>7}")
    print("-" * 70)

    for rank, a in enumerate(analyses, 1):
        marker = " <-- BEST" if rank == 1 else ""
        print(
            f"{rank:<5} {a.symbol:<12} {a.overall_score:>6.1f} {a.hurst_exponent:>6.3f} "
            f"{a.adx:>6.1f} {a.volatility_pct:>6.2f} {a.bb_oscillation_score:>5.2f} "
            f"{a.grid_backtest_profit_pct:>10.2f} {a.predicted_daily_profit_pct:>7.3f}{marker}"
        )

    print("\n" + "=" * 70)
    print(f"  RECOMMENDED SYMBOL: {best.symbol}")
    print("=" * 70)

    print(f"""
  Symbol:            {best.symbol}
  Current Price:     {best.current_price}
  Overall Score:     {best.overall_score}/100

  --- Ranging Indicators ---
  Hurst Exponent:    {best.hurst_exponent:.4f}  {'MEAN-REVERTING' if best.hurst_exponent < 0.45 else 'NEUTRAL' if best.hurst_exponent < 0.55 else 'TRENDING'}
  ADX:               {best.adx:.1f}       {'RANGING' if best.adx < 20 else 'WEAK TREND' if best.adx < 25 else 'TRENDING'}
  BB Oscillation:    {best.bb_oscillation_score:.4f}   (higher = more mean-reversion bounces)
  Range Consistency: {best.range_consistency:.1%}     (% of candles within detected range)
  Volatility:        {best.volatility_pct:.2f}%     (hourly return std — fuels profit)

  --- Profitability Forecast ---
  Backtest Profit:   {best.grid_backtest_profit_pct:.2f}%  (simulated over 7-day window)
  Est. Daily Profit: {best.predicted_daily_profit_pct:.3f}%
  Avg Hourly Volume: ${best.avg_volume_usdt:,.0f} USDT

  --- Recommended Grid Settings ---
  Lower Price:       {best.recommended_lower}
  Upper Price:       {best.recommended_upper}
  Grid Levels:       {best.recommended_levels}
""")

    print("  Interpretation:")
    if best.hurst_exponent < 0.45:
        print("  + Strong mean-reversion detected — price tends to bounce back")
    if best.adx < 20:
        print("  + Low ADX confirms no directional trend — ideal ranging market")
    if best.bb_oscillation_score > 0.3:
        print("  + High oscillation — price frequently crosses moving average")
    if best.grid_backtest_profit_pct > 1.0:
        print("  + Backtest shows strong historical grid profitability")
    print("=" * 70)
