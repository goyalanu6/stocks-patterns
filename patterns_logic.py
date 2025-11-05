import pandas as pd
from rbr_logic import fetch_for
from typing import Optional, Dict, Any, Tuple

def find_pattern(
    df: pd.DataFrame,
    direction: str = "bullish",
    max_bases: int = 4,
    body_threshold: float = 0.65,
    wick_threshold: float = 0.35
) -> pd.DataFrame:
    """
    Detect Rally-Base-Rally (RBR) or Drop-Base-Drop (DBD) patterns with
    dynamic body/wick thresholds.

    Candle Rules (default)
    -----------------------
    RBR (bullish):
        - Rally candles: body >= 65% of total candle, (upper+lower wicks) <= 35%
        - Base candles: body <= 35%, (upper+lower wicks) >= 65%
    DBD (bearish):
        - Drop candles: body >= 65%, wicks <= 35%
        - Base candles: body <= 35%, wicks >= 65%
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
            if not is_bullish(c1) or body1 / size1 < body_threshold or wick1 / size1 > wick_threshold:
                i += 1
                continue
        else:
            if not is_bearish(c1) or body1 / size1 < body_threshold or wick1 / size1 > wick_threshold:
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

            if body / size <= wick_threshold and wick / size >= body_threshold:
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
            if not is_bullish(c2) or body2 / size2 < body_threshold or wick2 / size2 > wick_threshold:
                i += 1
                continue
        else:
            if not is_bearish(c2) or body2 / size2 < body_threshold or wick2 / size2 > wick_threshold:
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


def analyze_security_patterns(
    security_id: str,
    direction: str,
    body_threshold: float = 0.65,
    wick_threshold: float = 0.35
) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
    """Fetch and analyze security for RBR or DBD patterns using dynamic thresholds."""
    try:
        df = fetch_for(security_id)
        if df is None or df.empty:
            print(f"No data returned for {security_id}")
            return None, pd.DataFrame()

        zones = find_pattern(
            df,
            direction,
            body_threshold=body_threshold,
            wick_threshold=wick_threshold
        )

        if zones is None or zones.empty:
            return df, pd.DataFrame()

        if direction == "bullish":
            retests = find_retests_rbr(df, zones)
        elif direction == "bearish":
            retests = find_retests_dbd(df, zones)
        else:
            retests = pd.DataFrame()

        return df, retests

    except Exception as e:
        print(f"Error analyzing {security_id}: {e}")
        return None, pd.DataFrame()


# --- Retest functions remain unchanged ---

def find_retests_rbr(df: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
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

        for idx in range(rally2_idx + 1, n):
            c = df.iloc[idx]
            low = float(c.low)

            if not buy_signal and (dz_low - tolerance) <= low <= (dz_high + tolerance):
                buy_signal = True
                buy_price = low
                retest_date = c.date

            if low < (dz_low - tolerance):
                invalidated = True
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

        for idx in range(drop2_idx + 1, n):
            c = df.iloc[idx]
            high = float(c.high)

            if not sell_signal and sz_low <= high <= sz_high:
                sell_signal = True
                sell_price = high
                retest_date = c.date

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
