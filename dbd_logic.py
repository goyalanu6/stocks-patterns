"""Drop-Base-Drop (DBD) detection logic.

This module mirrors the rally-base-rally logic but inverted: it looks for
two strong red drops separated by a small-body base (up to `max_bases`),
then defines a demand zone from the bases and scans for a "buy" retest.

Exports:
  - find_drop_base_drop(df, max_bases=4) -> pd.DataFrame
  - find_retests_dbd(df, zones) -> pd.DataFrame
  - analyze_security_dbd(security_id) -> (df, retests_df)

The returned columns try to match the RBR outputs so they can be used
similarly in downstream code / UIs.
"""

from typing import Optional, Tuple
import pandas as pd
from rbr_logic import fetch_for


def is_red(c) -> bool:
    return c.open > c.close


def overall(c) -> float:
    return max(c.high - c.low, 1e-9)


def wick_data(c) -> tuple[float, float, float]:
    """Return (upper_wick, lower_wick, body) consistent with RBR helpers.

    For a red candle (open>close) body = open-close (positive). For green
    it's close-open.
    """
    if is_red(c):
        upper = c.high - c.open
        lower = c.close - c.low
        body = c.open - c.close
    else:
        upper = c.high - c.close
        lower = c.open - c.low
        body = c.close - c.open
    return upper, lower, body


def find_drop_base_drop(df: pd.DataFrame, max_bases: int = 4) -> pd.DataFrame:
    """Detect Drop-Base-Drop patterns and return zone definitions.

    Rules implemented (per your spec):
      - First drop: red candle with body >= 65% of overall candle size
      - Bases: up to `max_bases` candles with body <= 35% of overall (small bodies)
      - Second drop: red candle with body >= 65% (same rule as first)
      - Demand zone: highest of base highs is dz_high;
        lowest of base body (min(open,close) across bases) is dz_low
      - Zone invalidated if any future candle.high > dz_high (zone broken upwards)

    Returns DataFrame with columns similar to RBR detector:
      date_base, demand_zone_low, demand_zone_high, zone_height,
      num_base_candles, drop2_idx
    """
    zones = []
    n = len(df)
    i = 0

    while i < n - 2:
        d1 = df.iloc[i]

        # First strong drop
        if not is_red(d1) or (d1.open - d1.close) / overall(d1) < 0.65:
            i += 1
            continue

        # collect bases (small-body candles)
        bases = []
        j = i + 1
        while j < n and len(bases) < max_bases:
            c = df.iloc[j]
            upper, lower, body = wick_data(c)
            body_ratio = abs(body) / overall(c)
            wick_ratio = (upper + lower) / overall(c)

            # base conditions: body <= 35%, wicks >= 65% (like RBR bases)
            if body_ratio <= 0.35 and wick_ratio >= 0.65:
                bases.append(c)
                j += 1
            else:
                break

        if not bases:
            i += 1
            continue

        # Ensure there's a second strong drop immediately after bases
        if j >= n:
            break

        d2 = df.iloc[j]
        if not is_red(d2) or (d2.open - d2.close) / overall(d2) < 0.65:
            i += 1
            continue

        # compute demand zone from bases
        base_highs = [b.high for b in bases]
        # lowest of base body's open/close
        base_body_lows = [min(b.open, b.close) for b in bases]

        dz_high = max(base_highs)
        dz_low = min(base_body_lows)
        zone_height = dz_high - dz_low

        # date_base is the date of the first base candle
        date_base = bases[0].date

        # Validate zone: ensure no future candle breaks the zone upward
        valid_zone = True
        for k in range(j + 1, n):
            if df.iloc[k].high > dz_high:
                valid_zone = False
                break

        if not valid_zone:
            i = j + 1
            continue

        zones.append({
            "date_base": date_base,
            "demand_zone_low": float(dz_low),
            "demand_zone_high": float(dz_high),
            "zone_height": float(zone_height),
            "num_base_candles": len(bases),
            "drop2_idx": j,
        })

        i = j + 1

    return pd.DataFrame(zones)


def find_retests_dbd(df: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """Scan for retests (buy signals) after the second drop for DBD zones.

    Buy rule (per spec): the high of any candle after the second drop touches the
    low of the demand zone (i.e., high >= dz_low) but the candle must not break
    the demand zone (we require candle.low >= dz_low). We record the first such
    candle as the buy. If any future candle breaks the zone (high > dz_high),
    the zone is invalidated.

    Returns zones DataFrame with columns: buy_signal, buy_price, retest_date, invalidated
    """
    if zones is None or len(zones) == 0:
        return pd.DataFrame(columns=[*(zones.columns if zones is not None else []),
                                     "buy_signal", "buy_price", "retest_date", "invalidated"])

    results = []
    n = len(df)

    for _, zone in zones.iterrows():
        dz_low = float(zone["demand_zone_low"])  # low of demand zone
        dz_high = float(zone["demand_zone_high"])  # high of demand zone
        drop2_idx = int(zone["drop2_idx"])  # index of 2nd drop

        buy_signal = False
        invalidated = False
        buy_price = None
        retest_date = None

        for idx in range(drop2_idx + 1, n):
            c = df.iloc[idx]

            # Invalidation: a candle that exceeds the zone high breaks it
            if float(c.high) > dz_high:
                invalidated = True
                break

            # Buy condition: candle.high touches or exceeds dz_low AND it doesn't break (low >= dz_low)
            if float(c.high) >= dz_low and float(c.low) >= dz_low:
                buy_signal = True
                # buy price is the zone low (entry when zone is touched)
                buy_price = float(dz_low)
                retest_date = c.date
                break

        out = zone.to_dict()
        out.update({
            "buy_signal": buy_signal,
            "buy_price": buy_price,
            "retest_date": pd.to_datetime(retest_date) if retest_date is not None else None,
            "invalidated": invalidated,
        })

        results.append(out)

    df_out = pd.DataFrame(results)
    return df_out.drop(columns=["zone_height", "drop2_idx"], errors="ignore")


def analyze_security_dbd(security_id: str) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
    """Fetch and analyze a single security for DBD patterns.

    Returns (df, retests_df) where df is the candle DataFrame and retests_df
    contains the DBD zones + retest/buy information.
    """
    df = fetch_for(security_id)
    if df is None or df.empty:
        return None, pd.DataFrame()

    zones = find_drop_base_drop(df)
    if zones.empty:
        return df, pd.DataFrame()

    retests = find_retests_dbd(df, zones)
    return df, retests
