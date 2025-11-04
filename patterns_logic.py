import pandas as pd
from rbr_logic import fetch_for
from typing import Optional, Dict, Any, Tuple

def find_pattern(df: pd.DataFrame, direction: str = "bullish", max_bases: int = 4) -> pd.DataFrame:
    """
    Detect Rally-Base-Rally (RBR) or Drop-Base-Drop (DBD) patterns.

    Candle Rules
    -------------
    RBR (bullish):
        - First & second rally candles (green):
            * body >= 65% of total candle
            * (upper + lower wicks) <= 35% of total candle
        - Base candles:
            * body <= 35% of total candle
            * (upper + lower wicks) >= 65% of total candle
    DBD (bearish):
        - First & second drop candles (red):
            * body >= 65% of total candle
            * (upper + lower wicks) <= 35% of total candle
        - Base candles:
            * body <= 35% of total candle
            * (upper + lower wicks) >= 65% of total candle

    Zone Definition
    ----------------
    - Bullish:
        zone_high = highest body high among bases (max(open, close))
        zone_low  = lowest low among bases
    - Bearish:
        zone_high = highest high among bases
        zone_low  = lowest body low among bases (min(open, close))
    """

    def candle_size(c):
        return max(c.high - c.low, 1e-9)

    def candle_body(c):
        return abs(c.close - c.open)

    def wick_sum(c):
        """Total wick size = (upper + lower)."""
        return (c.high - max(c.open, c.close)) + (min(c.open, c.close) - c.low)

    def is_bullish(c):
        return c.close > c.open

    def is_bearish(c):
        return c.open > c.close

    zones = []
    n = len(df)
    i = 0

    while i < n - 2:
        c1 = df.iloc[i]
        size1 = candle_size(c1)
        body1 = candle_body(c1)
        wick1 = wick_sum(c1)

        # --- First impulse (rally/drop) candle ---
        if direction == "bullish":
            if not is_bullish(c1) or body1 / size1 < 0.65 or wick1 / size1 > 0.35:
                i += 1
                continue
        else:
            if not is_bearish(c1) or body1 / size1 < 0.65 or wick1 / size1 > 0.35:
                i += 1
                continue

        # --- Base candles ---
        bases = []
        j = i + 1
        while j < n and len(bases) < max_bases:
            c = df.iloc[j]
            size = candle_size(c)
            body = candle_body(c)
            wick = wick_sum(c)

            if body / size <= 0.35 and wick / size >= 0.65:
                bases.append(c)
                j += 1
            else:
                break

        if not bases or j >= n:
            i += 1
            continue

        # --- Second impulse (rally/drop) candle ---
        c2 = df.iloc[j]
        size2 = candle_size(c2)
        body2 = candle_body(c2)
        wick2 = wick_sum(c2)

        if direction == "bullish":
            if not is_bullish(c2) or body2 / size2 < 0.65 or wick2 / size2 > 0.35:
                i += 1
                continue
        else:
            if not is_bearish(c2) or body2 / size2 < 0.65 or wick2 / size2 > 0.35:
                i += 1
                continue

        # --- Zone definition ---
        if direction == "bullish":
            zone_high = max(max(b.open, b.close) for b in bases)  # highest body high
            zone_low = min(b.low for b in bases)                  # lowest low
        else:
            zone_high = max(b.high for b in bases)                # highest high
            zone_low = min(min(b.open, b.close) for b in bases)   # lowest body low

        zone_height = abs(zone_high - zone_low)
        date_base = bases[0].date

        zones.append({
            "pattern_type": "RBR" if direction == "bullish" else "DBD",
            "date_base": date_base,
            "zone_low": float(zone_low),
            "zone_high": float(zone_high),
            "zone_height": float(zone_height),
            "num_base_candles": len(bases),
            "continuation_idx": j,
        })

        i = j + 1

    return pd.DataFrame(zones)

def analyze_security_patterns(security_id: str, direction: str) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
    """Fetch and analyze a single security for DBD patterns.

    Returns (df, retests_df) where df is the candle DataFrame and retests_df
    contains the DBD zones + retest/buy information.
    """
    try:
        df = fetch_for(security_id)
        # handle empty DataFrame
        if df is None or df.empty:
            print(f"No data returned for {security_id}")
            return None, pd.DataFrame()

        zones = find_pattern(df, direction)
        if zones is None or zones.empty:
            return df, pd.DataFrame()

        if direction == "bullish":
            retests = find_retests_rbr(df, zones)
        if direction == "bearish":
            retests = find_retests_dbd(df, zones)
        return df, retests
    except RuntimeError as e:
        # handle network/API errors explicitly
        print(f"❌ Error fetching data for {security_id}: {e}")
        return None, pd.DataFrame()
    except Exception as e:
        print(f"Error fetching data for {security_id}: {e}")
        return None, pd.DataFrame() # always return a tuple

def find_retests_rbr(df: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """
    Retest scanning after Rally-2 for demand zone validation.

    Rules:
      ✅ Buy when any future candle.low touches demand zone 
         (dz_low <= low <= dz_high)
      ❌ Invalidate when any future candle.low breaks below dz_low
      🕒 Continue scanning until an invalidation occurs 
         (even if a buy already happened)

    Returns: zones DataFrame with:
      'buy_signal', 'buy_price', 'retest_date', 'invalidated'
    """
    if zones is None or len(zones) == 0:
        return pd.DataFrame(columns=[
            *(zones.columns if zones is not None else []),
            "buy_signal", "buy_price", "retest_date", "invalidated"
        ])

    results = []
    n = len(df)
    tolerance = 1e-4

    for _, zone in zones.iterrows():
        dz_low = float(zone["zone_low"])
        dz_high = float(zone["zone_high"])
        rally2_idx = int(zone["continuation_idx"])

        buy_signal = False
        invalidated = False
        buy_price = None
        retest_date = None

        # ✅ scan all candles after Rally-2
        for idx in range(rally2_idx + 1, n):
            c = df.iloc[idx]
            low = float(c.low)

            # ✅ Buy condition — only record first occurrence
            if not buy_signal and (dz_low - tolerance) <= low <= (dz_high + tolerance):
                buy_signal = True
                buy_price = low
                retest_date = c.date

            # ❌ Invalidation — always check, even after buy
            if low < (dz_low - tolerance):
                invalidated = True
                # we can break now — once broken, zone is invalid
                break

        out = zone.to_dict()
        out.update({
            "buy_signal": buy_signal,
            "buy_price": buy_price,
            "retest_date": pd.to_datetime(retest_date) if retest_date else None,
            "invalidated": invalidated
        })
        results.append(out)

    df_out = pd.DataFrame(results)
    return df_out.drop(columns=["zone_height", "continuation_idx"], errors="ignore")

def find_retests_dbd(df: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """
    Retest scanning after Drop-2 for supply zone validation (bearish pattern).

    Rules:
      ✅ Sell when any future candle.high touches the supply zone 
         (sz_low <= high <= sz_high)
      ❌ Invalidate when any future candle.high breaks above sz_high
      🕒 Continue scanning even after a sell to detect invalidation.
    """
    if zones is None or len(zones) == 0:
        return pd.DataFrame(columns=[
            *(zones.columns if zones is not None else []),
            "sell_signal", "sell_price", "retest_date", "invalidated"
        ])

    results = []
    n = len(df)

    for _, zone in zones.iterrows():
        sz_low = float(zone["zone_low"])
        sz_high = float(zone["zone_high"])
        drop2_idx = int(zone["continuation_idx"])

        sell_signal = False
        invalidated = False
        sell_price = None
        retest_date = None

        # ✅ Scan all candles after Drop-2
        for idx in range(drop2_idx + 1, n):
            c = df.iloc[idx]
            high = float(c.high)

            # ✅ Retest (sell) condition — record once, but don’t break
            if not sell_signal and sz_low <= high <= sz_high:
                sell_signal = True
                sell_price = high
                retest_date = c.date

            # ❌ Invalidation condition — always check, even after sell
            if high > sz_high:
                invalidated = True
                break

        out = zone.to_dict()
        out.update({
            "sell_signal": sell_signal,
            "sell_price": sell_price,
            "retest_date": pd.to_datetime(retest_date) if retest_date else None,
            "invalidated": invalidated
        })

        results.append(out)

    df_out = pd.DataFrame(results)
    return df_out.drop(columns=["zone_height", "continuation_idx"], errors="ignore")
